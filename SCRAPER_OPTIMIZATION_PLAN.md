# Scraper Optimization Plan: API-Interleaved Parallel Car Processing

**Target Agent**: `vehicle_development_agent` (only)
**Date**: 2026-03-25

---

## Context

**Problem**: Scraping 2 cars takes 7-10 minutes (3.5-5 min/car) which is unacceptable for production.

**Root Cause**: Cars are processed **sequentially** despite having internal parallelization. When Car A hits Gemini rate limits (15 RPM free tier), the system waits instead of utilizing that time for Custom Search calls on Car B.

**Solution**: Implement **API-type interleaved parallel processing** - when one car is blocked on Gemini API, another car processes Custom Search queries (and vice versa). This maximizes throughput without exceeding rate limits.

**Target**: Process 2 cars in ~2-3 minutes (down from 7-10 minutes).

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    RESOURCE-AWARE SCHEDULER                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ Gemini Flash │  │ Gemini Pro   │  │Custom Search │           │
│  │ TokenBucket  │  │ TokenBucket  │  │ TokenBucket  │           │
│  │ 15 RPM       │  │ 5 RPM        │  │ 10 RPS       │           │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘           │
│         │                 │                 │                    │
│  ┌──────▼─────────────────▼─────────────────▼───────┐           │
│  │              PRIORITY TASK QUEUES                 │           │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐           │           │
│  │  │Gemini Q │  │Search Q │  │Image Q  │           │           │
│  │  └────┬────┘  └────┬────┘  └────┬────┘           │           │
│  └───────┼────────────┼────────────┼────────────────┘           │
│          │            │            │                             │
│  ┌───────▼────────────▼────────────▼────────────────┐           │
│  │           WORKER POOL (asyncio TaskGroup)         │           │
│  │  Worker 1 │ Worker 2 │ Worker 3 │ ... │ Worker N │           │
│  └──────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   ┌─────────┐           ┌─────────┐           ┌─────────┐
   │  Car A  │           │  Car B  │           │  Car C  │
   │ Phase 1 │◄─────────►│ Phase 2 │◄─────────►│ Phase 3 │
   └─────────┘           └─────────┘           └─────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                    ┌─────────────────┐
                    │ Merged Results  │
                    └─────────────────┘
```

---

## Implementation Plan

### Step 1: Create Resource-Aware Scheduler

**File**: `vehicle_development_agent/core/resource_scheduler.py`

**Components**:
```python
# 1. ResourceType enum
class ResourceType(Enum):
    GEMINI_FLASH = "gemini_flash"
    GEMINI_PRO = "gemini_pro"
    CUSTOM_SEARCH = "custom_search"
    IMAGE_SEARCH = "image_search"

# 2. Enhanced TokenBucket with capacity check
class EnhancedTokenBucket(TokenBucket):
    def has_capacity(self, tokens: int = 1) -> bool:
        """Non-blocking capacity check."""
        ...

    def time_until_available(self, tokens: int = 1) -> float:
        """Returns seconds until tokens available."""
        ...

# 3. PriorityTaskQueue
class PriorityTaskQueue:
    """Heapq-based queue with resource tagging."""
    def push(self, priority: int, task: Task) -> None
    def pop(self) -> Optional[Task]
    def peek(self) -> Optional[Task]

# 4. ResourceScheduler (main orchestrator)
class ResourceScheduler:
    def __init__(self, limiters: Dict[ResourceType, RateLimiter])
    async def schedule_next_task(self) -> Task
    async def submit_task(self, task: Task) -> None
    async def run(self) -> None
```

### Step 2: Create Interleaved Car Processor

**File**: `vehicle_development_agent/core/interleaved_processor.py`

**Components**:
```python
@dataclass
class CarTask:
    car_id: str
    phase: int  # 0, 1, 2, 3
    spec_batch: List[str]
    resource_type: ResourceType
    priority: int
    callback: Callable  # Called with result

class InterleavedCarProcessor:
    def __init__(self, scheduler: ResourceScheduler)

    def generate_tasks_for_car(self, car: Dict) -> List[CarTask]:
        """Split car work into resource-typed tasks."""
        ...

    async def process_cars_interleaved(self, cars: List[Dict]) -> Dict:
        """Main entry point - processes multiple cars with interleaving."""
        ...

    async def task_worker(self, task: CarTask) -> Any:
        """Execute single task respecting rate limits."""
        ...
```

**Task Generation Strategy**:
```
Car A Phase 1: [Search Task 1-10, Search Task 11-20, ..., Gemini Extract 1, Gemini Extract 2, ...]
Car B Phase 1: [Search Task 1-10, Search Task 11-20, ..., Gemini Extract 1, Gemini Extract 2, ...]

All tasks merged into single priority queue, sorted by:
1. Phase priority (Phase 0 > Phase 1 > Phase 2)
2. Resource availability (if Gemini blocked, Search tasks promoted)
3. Car fairness (round-robin between cars)
```

### Step 3: Refactor scraper.py

**File**: `vehicle_development_agent/core/scraper.py`

**Changes**:
1. Add `scrape_cars_parallel()` function (new entry point for multi-car)
2. Refactor `phase1_per_spec_search()` to yield tasks instead of blocking
3. Refactor `phase2_cardekho_fallback()` to yield tasks
4. Keep single-car `scrape_car_data()` for backwards compatibility
5. Extract Gemini/Search calls into task-compatible async functions

### Step 4: Update Configuration

**File**: `vehicle_development_agent/async_config.py`

**Add**:
```python
@dataclass
class InterleavedConfig:
    enabled: bool = True
    max_concurrent_cars: int = 4
    task_queue_size: int = 500
    worker_count: int = 20

    # Resource budgets (prevents starvation)
    gemini_flash_max_pending: int = 15
    gemini_flash_priority_boost: int = 2
    custom_search_max_pending: int = 50
    custom_search_priority_boost: int = 1

interleaved_config = InterleavedConfig()
```

### Step 5: Add Monitoring & Metrics

**File**: `vehicle_development_agent/core/scraper_metrics.py`

```python
@dataclass
class ScraperMetrics:
    tasks_completed: Dict[ResourceType, int]
    queue_depths: Dict[ResourceType, int]
    rate_limit_hits: Dict[ResourceType, int]
    car_completion_times: Dict[str, float]
    resource_utilization: Dict[ResourceType, float]

    def log_summary(self) -> None
    def to_dict(self) -> Dict
```

---

## Critical Files to Modify

| File | Action | Purpose |
|------|--------|---------|
| `vehicle_development_agent/core/resource_scheduler.py` | CREATE | Token bucket + task scheduling |
| `vehicle_development_agent/core/interleaved_processor.py` | CREATE | Multi-car parallel orchestration |
| `vehicle_development_agent/core/scraper.py` | MODIFY | Integrate interleaved processor |
| `vehicle_development_agent/async_config.py` | MODIFY | Add interleaved config |
| `vehicle_development_agent/core/scraper_metrics.py` | CREATE | Performance monitoring |

---

## Existing Code to Reuse

The `async_utils.py` already has production-grade components we'll extend:

| Component | Location | Current State | Reuse Strategy |
|-----------|----------|---------------|----------------|
| `TokenBucket` | `async_utils.py:42-81` | Async-aware, lock-protected | Use directly, add `has_capacity()` method |
| `RateLimiter` | `async_utils.py:88-124` | Semaphore + TokenBucket combo | Use as-is for per-resource limiting |
| `CircuitBreaker` | `async_utils.py:131-208` | Full state machine | Use for Gemini fallback |
| `AsyncHTTPClient` | `async_utils.py:215-279` | Connection pooling, DNS cache | Use for all HTTP operations |
| `custom_search_limiter` | `async_utils.py:309-313` | Global instance (10 RPS) | Use directly |
| `gemini_flash_limiter` | `async_utils.py:315-319` | Global instance (15 RPM) | Use directly |
| `gemini_pro_limiter` | `async_utils.py:321-325` | Global instance (5 RPM) | Use directly |
| `async_retry` | `async_utils.py:285-301` | Tenacity-based | Use for retries |
| `exponential_backoff_retry` | `scraper.py:L147` | Sync version | Keep for backwards compat |
| `call_gemini_simple` | `scraper.py:L759` | Sync Gemini call | Wrap as async task |
| `google_custom_search` | `scraper.py:L1035` | Sync search | Wrap as async task |

---

## Interleaving Logic (Core Algorithm)

```python
async def schedule_next_task(self) -> Optional[CarTask]:
    """Pick next task based on resource availability."""

    # Check each resource in priority order
    for resource_type in [ResourceType.CUSTOM_SEARCH,
                          ResourceType.GEMINI_FLASH,
                          ResourceType.GEMINI_PRO]:
        if self.rate_limiters[resource_type].has_capacity():
            # Get highest priority task for this resource
            task = self.queues[resource_type].pop_highest_priority()
            if task:
                return task

    # All resources exhausted - wait for shortest reset
    min_wait = min(
        limiter.time_until_available()
        for limiter in self.rate_limiters.values()
    )
    await asyncio.sleep(min_wait)
    return await self.schedule_next_task()  # Retry
```

**Key Insight**: When Gemini hits 15 RPM limit, the scheduler automatically switches to Custom Search tasks (which have 10 RPS limit). This keeps workers busy instead of waiting.

---

## Expected Performance Improvement

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| 2 cars | 7-10 min | 2-3 min | **3-4x faster** |
| 10 cars | 35-50 min | 8-12 min | **4x faster** |
| Gemini utilization | ~30% | ~90% | **3x better** |
| Search utilization | ~40% | ~95% | **2.4x better** |

---

## Verification Plan

1. **Unit Tests**: Test resource scheduler with mock rate limiters
2. **Integration Test**: Process 2 cars, verify completion < 3 minutes
3. **Rate Limit Test**: Verify no 429 errors during processing
4. **Data Quality Test**: Compare output specs with sequential processing
5. **Load Test**: Process 10 cars, verify linear scaling

**Test Command**:
```bash
cd vehicle_development_agent
python -c "
import asyncio
from core.interleaved_processor import InterleavedCarProcessor

processor = InterleavedCarProcessor()
results = asyncio.run(processor.process_cars_interleaved([
    {'brand': 'Mahindra', 'model': 'XUV700'},
    {'brand': 'Tata', 'model': 'Nexon'}
]))
print(f'Completed in {results[\"total_time\"]}s')
"
```

---

## Implementation Order

1. **resource_scheduler.py** - Foundation (token buckets, queues)
2. **interleaved_processor.py** - Orchestration layer
3. **scraper.py modifications** - Integration
4. **async_config.py** - Configuration
5. **scraper_metrics.py** - Monitoring
6. **Testing** - Verify performance gains

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Race conditions | Use asyncio.Lock for shared state |
| Task starvation | Priority boost for long-waiting tasks |
| Memory bloat | Bounded queue sizes (500 max) |
| Partial failures | Per-car result aggregation with error isolation |
| Backwards compat | Keep `scrape_car_data()` unchanged |

---

## Notes for Implementation

- Start with `vehicle_development_agent` only
- Once verified, can apply same pattern to `benchmarking_agent` and `product_planning_agent`
- All 3 agents share identical scraper architecture, so code will be portable
