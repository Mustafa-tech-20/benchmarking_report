"""
Scraper Performance Metrics

Tracks and reports performance metrics for the interleaved car processor.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from vehicle_development_agent.core.resource_scheduler import ResourceType

logger = logging.getLogger(__name__)


@dataclass
class PhaseMetrics:
    """Metrics for a single processing phase."""
    phase_name: str
    start_time: float = 0.0
    end_time: float = 0.0
    tasks_submitted: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    specs_found: int = 0
    specs_total: int = 0

    @property
    def duration(self) -> float:
        if self.end_time == 0:
            return time.monotonic() - self.start_time if self.start_time > 0 else 0
        return self.end_time - self.start_time

    @property
    def success_rate(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        return self.tasks_completed / total if total > 0 else 0.0

    @property
    def spec_accuracy(self) -> float:
        return self.specs_found / self.specs_total if self.specs_total > 0 else 0.0


@dataclass
class CarMetrics:
    """Metrics for processing a single car."""
    car_id: str
    car_name: str
    start_time: float = field(default_factory=time.monotonic)
    end_time: float = 0.0
    phases: Dict[int, PhaseMetrics] = field(default_factory=dict)
    total_specs_found: int = 0
    total_specs_target: int = 87  # Default target

    def start_phase(self, phase: int, name: str) -> PhaseMetrics:
        metrics = PhaseMetrics(phase_name=name, start_time=time.monotonic())
        self.phases[phase] = metrics
        return metrics

    def end_phase(self, phase: int) -> None:
        if phase in self.phases:
            self.phases[phase].end_time = time.monotonic()

    @property
    def duration(self) -> float:
        if self.end_time == 0:
            return time.monotonic() - self.start_time
        return self.end_time - self.start_time

    @property
    def spec_accuracy(self) -> float:
        return self.total_specs_found / self.total_specs_target if self.total_specs_target > 0 else 0.0

    def complete(self) -> None:
        self.end_time = time.monotonic()


@dataclass
class ScraperMetrics:
    """
    Comprehensive metrics for the interleaved scraper.

    Tracks:
    - Per-resource task completion
    - Queue depths over time
    - Rate limit hits
    - Per-car completion times
    - Resource utilization
    """

    # Task tracking by resource type
    tasks_completed: Dict[str, int] = field(default_factory=lambda: {rt.value: 0 for rt in ResourceType})
    tasks_failed: Dict[str, int] = field(default_factory=lambda: {rt.value: 0 for rt in ResourceType})
    tasks_submitted: Dict[str, int] = field(default_factory=lambda: {rt.value: 0 for rt in ResourceType})

    # Rate limit tracking
    rate_limit_hits: Dict[str, int] = field(default_factory=lambda: {rt.value: 0 for rt in ResourceType})
    rate_limit_waits_seconds: Dict[str, float] = field(default_factory=lambda: {rt.value: 0.0 for rt in ResourceType})

    # Car metrics
    car_metrics: Dict[str, CarMetrics] = field(default_factory=dict)

    # Timing
    start_time: float = field(default_factory=time.monotonic)
    end_time: float = 0.0

    # Queue depth samples (for utilization calculation)
    _queue_samples: List[Dict[str, int]] = field(default_factory=list)
    _sample_interval: float = 1.0  # Sample every second
    _last_sample_time: float = field(default_factory=time.monotonic)

    def start_car(self, car_id: str, car_name: str) -> CarMetrics:
        """Start tracking a car."""
        metrics = CarMetrics(car_id=car_id, car_name=car_name)
        self.car_metrics[car_id] = metrics
        return metrics

    def end_car(self, car_id: str) -> None:
        """Mark a car as complete."""
        if car_id in self.car_metrics:
            self.car_metrics[car_id].complete()

    def record_task_submit(self, resource_type: ResourceType) -> None:
        """Record a task submission."""
        self.tasks_submitted[resource_type.value] += 1

    def record_task_complete(self, resource_type: ResourceType, success: bool = True) -> None:
        """Record a task completion."""
        if success:
            self.tasks_completed[resource_type.value] += 1
        else:
            self.tasks_failed[resource_type.value] += 1

    def record_rate_limit(self, resource_type: ResourceType, wait_seconds: float = 0.0) -> None:
        """Record a rate limit hit."""
        self.rate_limit_hits[resource_type.value] += 1
        self.rate_limit_waits_seconds[resource_type.value] += wait_seconds

    def sample_queue_depths(self, depths: Dict[str, int]) -> None:
        """Sample current queue depths for utilization calculation."""
        now = time.monotonic()
        if now - self._last_sample_time >= self._sample_interval:
            self._queue_samples.append(depths.copy())
            self._last_sample_time = now

    def complete(self) -> None:
        """Mark metrics collection as complete."""
        self.end_time = time.monotonic()

    @property
    def duration(self) -> float:
        if self.end_time == 0:
            return time.monotonic() - self.start_time
        return self.end_time - self.start_time

    @property
    def total_tasks_completed(self) -> int:
        return sum(self.tasks_completed.values())

    @property
    def total_tasks_failed(self) -> int:
        return sum(self.tasks_failed.values())

    @property
    def cars_completed(self) -> int:
        return sum(1 for m in self.car_metrics.values() if m.end_time > 0)

    def get_resource_utilization(self) -> Dict[str, float]:
        """
        Calculate resource utilization percentage.

        Utilization = (tasks completed) / (max possible given rate limits)
        """
        if self.duration == 0:
            return {rt.value: 0.0 for rt in ResourceType}

        # Theoretical max tasks per resource in the elapsed time
        from vehicle_development_agent.async_config import rate_limit_config

        max_tasks = {
            ResourceType.GEMINI_FLASH.value: self.duration * rate_limit_config.gemini_flash_requests_per_minute / 60.0,
            ResourceType.GEMINI_PRO.value: self.duration * rate_limit_config.gemini_pro_requests_per_minute / 60.0,
            ResourceType.CUSTOM_SEARCH.value: self.duration * rate_limit_config.custom_search_requests_per_second,
            ResourceType.IMAGE_SEARCH.value: self.duration * rate_limit_config.custom_search_requests_per_second / 2,
        }

        return {
            rt: (self.tasks_completed.get(rt, 0) / max_tasks[rt] * 100) if max_tasks.get(rt, 0) > 0 else 0.0
            for rt in max_tasks
        }

    def log_summary(self) -> None:
        """Log a summary of metrics."""
        utilization = self.get_resource_utilization()

        logger.info("=" * 60)
        logger.info("SCRAPER METRICS SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Duration: {self.duration:.1f}s")
        logger.info(f"Cars Processed: {len(self.car_metrics)}")
        logger.info(f"Cars Completed: {self.cars_completed}")
        logger.info("")
        logger.info("Task Completion by Resource:")
        for rt in ResourceType:
            completed = self.tasks_completed.get(rt.value, 0)
            failed = self.tasks_failed.get(rt.value, 0)
            submitted = self.tasks_submitted.get(rt.value, 0)
            util = utilization.get(rt.value, 0)
            logger.info(f"  {rt.value}: {completed}/{submitted} completed, {failed} failed, {util:.1f}% utilization")

        logger.info("")
        logger.info("Rate Limit Summary:")
        for rt in ResourceType:
            hits = self.rate_limit_hits.get(rt.value, 0)
            wait = self.rate_limit_waits_seconds.get(rt.value, 0)
            if hits > 0:
                logger.info(f"  {rt.value}: {hits} hits, {wait:.1f}s total wait")

        logger.info("")
        logger.info("Per-Car Completion Times:")
        for car_id, car_m in self.car_metrics.items():
            status = "DONE" if car_m.end_time > 0 else "IN PROGRESS"
            logger.info(f"  {car_m.car_name}: {car_m.duration:.1f}s ({status}), {car_m.total_specs_found} specs")

        logger.info("=" * 60)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for serialization."""
        return {
            "duration_seconds": self.duration,
            "total_tasks_completed": self.total_tasks_completed,
            "total_tasks_failed": self.total_tasks_failed,
            "tasks_by_resource": {
                "completed": dict(self.tasks_completed),
                "failed": dict(self.tasks_failed),
                "submitted": dict(self.tasks_submitted),
            },
            "rate_limits": {
                "hits": dict(self.rate_limit_hits),
                "wait_seconds": dict(self.rate_limit_waits_seconds),
            },
            "resource_utilization": self.get_resource_utilization(),
            "cars": {
                car_id: {
                    "name": m.car_name,
                    "duration_seconds": m.duration,
                    "specs_found": m.total_specs_found,
                    "specs_target": m.total_specs_target,
                    "accuracy": m.spec_accuracy,
                    "completed": m.end_time > 0,
                }
                for car_id, m in self.car_metrics.items()
            },
        }

    def print_summary(self) -> None:
        """Print a human-readable summary to stdout."""
        utilization = self.get_resource_utilization()

        print(f"\n{'=' * 60}")
        print("INTERLEAVED SCRAPER METRICS")
        print(f"{'=' * 60}")
        print(f"  Total Duration: {self.duration:.1f}s")
        print(f"  Cars: {self.cars_completed}/{len(self.car_metrics)} completed")
        print(f"  Tasks: {self.total_tasks_completed} completed, {self.total_tasks_failed} failed")
        print("")
        print("  Resource Utilization:")
        for rt in ResourceType:
            util = utilization.get(rt.value, 0)
            bar_len = int(util / 5)  # 20 chars = 100%
            bar = "#" * bar_len + "-" * (20 - bar_len)
            print(f"    {rt.value:15s}: [{bar}] {util:.0f}%")

        print("")
        print("  Per-Car Results:")
        for car_id, car_m in self.car_metrics.items():
            status = "+" if car_m.end_time > 0 else "..."
            acc = car_m.spec_accuracy * 100
            print(f"    {status} {car_m.car_name}: {car_m.duration:.1f}s, {car_m.total_specs_found}/{car_m.total_specs_target} specs ({acc:.0f}%)")

        print(f"{'=' * 60}\n")


# Global metrics instance
_metrics: Optional[ScraperMetrics] = None


def get_metrics() -> ScraperMetrics:
    """Get or create the global metrics instance."""
    global _metrics
    if _metrics is None:
        _metrics = ScraperMetrics()
    return _metrics


def reset_metrics() -> ScraperMetrics:
    """Reset and return a new metrics instance."""
    global _metrics
    _metrics = ScraperMetrics()
    return _metrics


logger.info("Scraper metrics module initialized")
