"""
Resource-Aware Scheduler for API-Interleaved Parallel Car Processing

Implements token bucket rate limiting with priority-based task scheduling
to maximize throughput when processing multiple cars by interleaving
different API types (Gemini vs Custom Search).
"""
import asyncio
import heapq
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Awaitable

from vehicle_development_agent.async_config import rate_limit_config, interleaved_config

logger = logging.getLogger(__name__)


# ============================================================================
# RESOURCE TYPES
# ============================================================================

class ResourceType(Enum):
    """Types of rate-limited API resources."""
    GEMINI_FLASH = "gemini_flash"
    GEMINI_PRO = "gemini_pro"
    CUSTOM_SEARCH = "custom_search"
    IMAGE_SEARCH = "image_search"


# ============================================================================
# ENHANCED TOKEN BUCKET
# ============================================================================

class EnhancedTokenBucket:
    """
    Thread-safe token bucket rate limiter with capacity checking.

    Extends basic token bucket with non-blocking capacity checks
    and time-until-available calculations for smart scheduling.
    """

    def __init__(
        self,
        rate: float,  # tokens per second
        capacity: int,  # max tokens in bucket
        initial_tokens: Optional[int] = None
    ):
        self.rate = rate
        self.capacity = capacity
        self.tokens = initial_tokens if initial_tokens is not None else capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time (call within lock)."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.last_update = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

    def has_capacity(self, tokens: int = 1) -> bool:
        """
        Non-blocking capacity check.

        Returns True if tokens are available, False otherwise.
        Does NOT consume tokens.
        """
        # Quick check without lock for fast path
        now = time.monotonic()
        elapsed = now - self.last_update
        estimated_tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        return estimated_tokens >= tokens

    def time_until_available(self, tokens: int = 1) -> float:
        """
        Calculate seconds until requested tokens are available.

        Returns 0 if tokens are immediately available.
        """
        now = time.monotonic()
        elapsed = now - self.last_update
        current_tokens = min(self.capacity, self.tokens + elapsed * self.rate)

        if current_tokens >= tokens:
            return 0.0

        tokens_needed = tokens - current_tokens
        return tokens_needed / self.rate

    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens from the bucket, waiting if necessary.

        Returns the time waited in seconds.
        """
        async with self._lock:
            waited = 0.0
            while True:
                self._refill()

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return waited

                # Calculate wait time
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.rate
                await asyncio.sleep(wait_time)
                waited += wait_time

    async def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without waiting.

        Returns True if tokens were acquired, False otherwise.
        """
        async with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False


# ============================================================================
# PRIORITY TASK QUEUE
# ============================================================================

@dataclass(order=True)
class PrioritizedTask:
    """Task wrapper with priority for heap ordering."""
    priority: int
    insertion_order: int  # For FIFO within same priority
    task: Any = field(compare=False)


class PriorityTaskQueue:
    """
    Thread-safe priority queue for tasks with resource tagging.

    Lower priority values = higher priority (processed first).
    Uses heapq for O(log n) push/pop operations.
    """

    def __init__(self, max_size: int = 500):
        self._heap: List[PrioritizedTask] = []
        self._counter = 0
        self._lock = asyncio.Lock()
        self._max_size = max_size
        self._not_empty = asyncio.Event()

    async def push(self, priority: int, task: Any) -> bool:
        """
        Push a task onto the queue.

        Returns False if queue is full, True otherwise.
        """
        async with self._lock:
            if len(self._heap) >= self._max_size:
                return False

            entry = PrioritizedTask(priority, self._counter, task)
            self._counter += 1
            heapq.heappush(self._heap, entry)
            self._not_empty.set()
            return True

    async def pop(self) -> Optional[Any]:
        """Pop the highest priority task (lowest priority number)."""
        async with self._lock:
            if not self._heap:
                self._not_empty.clear()
                return None

            entry = heapq.heappop(self._heap)
            if not self._heap:
                self._not_empty.clear()
            return entry.task

    def peek(self) -> Optional[Any]:
        """Peek at the highest priority task without removing it."""
        if not self._heap:
            return None
        return self._heap[0].task

    def __len__(self) -> int:
        return len(self._heap)

    @property
    def is_empty(self) -> bool:
        return len(self._heap) == 0

    async def wait_for_task(self, timeout: Optional[float] = None) -> bool:
        """Wait until a task is available or timeout expires."""
        try:
            await asyncio.wait_for(self._not_empty.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False


# ============================================================================
# CAR TASK DEFINITION
# ============================================================================

@dataclass
class CarTask:
    """
    A unit of work for processing a car specification.

    Each task represents a single API call (search or extraction)
    tagged with its resource type for scheduling.
    """
    car_id: str  # Unique identifier (e.g., "mahindra_xuv700")
    car_name: str  # Display name (e.g., "Mahindra XUV700")
    phase: int  # 0=official, 1=search, 2=fallback
    spec_batch: List[str]  # List of spec names to process
    resource_type: ResourceType
    priority: int  # Lower = higher priority
    task_type: str  # "search" or "extract"
    callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.monotonic)

    def __post_init__(self):
        # Auto-assign priority based on phase if not set
        if self.priority == 0:
            self.priority = self.phase * 10


# ============================================================================
# RESOURCE SCHEDULER
# ============================================================================

class ResourceScheduler:
    """
    Main orchestrator for interleaved parallel processing.

    Manages multiple rate limiters and task queues, scheduling
    tasks based on resource availability to maximize throughput.
    """

    def __init__(self):
        # Initialize rate limiters for each resource type
        self.limiters: Dict[ResourceType, EnhancedTokenBucket] = {
            ResourceType.GEMINI_FLASH: EnhancedTokenBucket(
                rate=rate_limit_config.gemini_flash_requests_per_minute / 60.0,
                capacity=rate_limit_config.gemini_flash_max_concurrent,
            ),
            ResourceType.GEMINI_PRO: EnhancedTokenBucket(
                rate=rate_limit_config.gemini_pro_requests_per_minute / 60.0,
                capacity=rate_limit_config.gemini_pro_max_concurrent,
            ),
            ResourceType.CUSTOM_SEARCH: EnhancedTokenBucket(
                rate=rate_limit_config.custom_search_requests_per_second,
                capacity=rate_limit_config.custom_search_burst_limit,
            ),
            ResourceType.IMAGE_SEARCH: EnhancedTokenBucket(
                rate=rate_limit_config.custom_search_requests_per_second / 2,  # More conservative
                capacity=rate_limit_config.custom_search_burst_limit // 2,
            ),
        }

        # Initialize task queues for each resource type
        self.queues: Dict[ResourceType, PriorityTaskQueue] = {
            resource_type: PriorityTaskQueue(max_size=interleaved_config.task_queue_size)
            for resource_type in ResourceType
        }

        # Pending task tracking per car
        self._pending_tasks: Dict[str, int] = {}  # car_id -> count
        self._completed_tasks: Dict[str, int] = {}  # car_id -> count
        self._lock = asyncio.Lock()

        # Shutdown flag
        self._shutdown = False

        # Stats
        self._stats = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "rate_limit_waits": 0,
        }

    async def submit_task(self, task: CarTask) -> bool:
        """
        Submit a task to the appropriate queue.

        Returns False if queue is full, True otherwise.
        """
        queue = self.queues[task.resource_type]
        success = await queue.push(task.priority, task)

        if success:
            async with self._lock:
                self._pending_tasks[task.car_id] = self._pending_tasks.get(task.car_id, 0) + 1
                self._stats["tasks_submitted"] += 1

        return success

    async def submit_tasks(self, tasks: List[CarTask]) -> int:
        """Submit multiple tasks. Returns count of successfully submitted tasks."""
        submitted = 0
        for task in tasks:
            if await self.submit_task(task):
                submitted += 1
        return submitted

    def _get_available_resource(self) -> Optional[ResourceType]:
        """Find a resource type with available capacity and pending tasks."""
        # Priority order: Custom Search > Gemini Flash > Gemini Pro > Image Search
        priority_order = [
            ResourceType.CUSTOM_SEARCH,
            ResourceType.GEMINI_FLASH,
            ResourceType.GEMINI_PRO,
            ResourceType.IMAGE_SEARCH,
        ]

        for resource_type in priority_order:
            if (self.limiters[resource_type].has_capacity() and
                not self.queues[resource_type].is_empty):
                return resource_type

        return None

    async def schedule_next_task(self) -> Optional[CarTask]:
        """
        Pick next task based on resource availability.

        Returns None if all queues are empty or scheduler is shutdown.
        """
        if self._shutdown:
            return None

        # Check each resource in priority order
        resource_type = self._get_available_resource()

        if resource_type is not None:
            task = await self.queues[resource_type].pop()
            if task:
                # Acquire rate limit token
                await self.limiters[resource_type].acquire()
                return task

        # All resources exhausted - wait for shortest reset
        min_wait = float('inf')
        has_pending_tasks = False

        for resource_type in ResourceType:
            if not self.queues[resource_type].is_empty:
                has_pending_tasks = True
                wait_time = self.limiters[resource_type].time_until_available()
                min_wait = min(min_wait, wait_time)

        if not has_pending_tasks:
            return None

        if min_wait > 0 and min_wait != float('inf'):
            self._stats["rate_limit_waits"] += 1
            await asyncio.sleep(min(min_wait, 1.0))  # Cap wait at 1 second

        return await self.schedule_next_task()  # Retry

    async def mark_task_complete(self, task: CarTask, success: bool = True) -> None:
        """Mark a task as completed."""
        async with self._lock:
            car_id = task.car_id

            if car_id in self._pending_tasks:
                self._pending_tasks[car_id] = max(0, self._pending_tasks[car_id] - 1)

            self._completed_tasks[car_id] = self._completed_tasks.get(car_id, 0) + 1

            if success:
                self._stats["tasks_completed"] += 1
            else:
                self._stats["tasks_failed"] += 1

    def get_pending_count(self, car_id: str) -> int:
        """Get count of pending tasks for a car."""
        return self._pending_tasks.get(car_id, 0)

    def get_total_pending(self) -> int:
        """Get total pending tasks across all queues."""
        return sum(len(q) for q in self.queues.values())

    def is_car_complete(self, car_id: str) -> bool:
        """Check if all tasks for a car are complete."""
        return self._pending_tasks.get(car_id, 0) == 0

    def shutdown(self) -> None:
        """Signal scheduler to stop processing."""
        self._shutdown = True

    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        return {
            **self._stats,
            "pending_by_resource": {
                rt.value: len(self.queues[rt])
                for rt in ResourceType
            },
            "pending_by_car": dict(self._pending_tasks),
            "completed_by_car": dict(self._completed_tasks),
        }


# ============================================================================
# GLOBAL SCHEDULER INSTANCE
# ============================================================================

_scheduler: Optional[ResourceScheduler] = None


def get_scheduler() -> ResourceScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = ResourceScheduler()
    return _scheduler


def reset_scheduler() -> ResourceScheduler:
    """Reset and return a new scheduler instance."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown()
    _scheduler = ResourceScheduler()
    return _scheduler


logger.info("Resource scheduler module initialized")
