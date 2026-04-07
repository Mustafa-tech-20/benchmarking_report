"""
Async Configuration for Rate Limiting and Concurrency Control

Includes:
- RateLimitConfig: API rate limiting settings
- CircuitBreakerConfig: Circuit breaker pattern settings
- InterleavedConfig: Multi-car parallel processing settings
"""
from dataclasses import dataclass
from typing import Dict


@dataclass
class RateLimitConfig:
    """Configuration for API rate limiting - CSE has strict limits, Gemini is more relaxed."""

    # CSE rate limiting - Google CSE has strict per-second limits
    # Even paid tier hits 429s at high concurrency
    custom_search_max_concurrent: int = 5  # Only 5 concurrent CSE requests
    custom_search_requests_per_second: float = 5.0  # Max 5 requests/second
    custom_search_burst_limit: int = 10  # Small burst allowed

    # Gemini rate limiting - more relaxed
    gemini_flash_max_concurrent: int = 50
    gemini_flash_requests_per_minute: float = 1000.0
    gemini_pro_max_concurrent: int = 20
    gemini_pro_requests_per_minute: float = 200.0

    # HTTP client settings
    max_connections: int = 200
    max_connections_per_host: int = 100
    connection_timeout: int = 30
    request_timeout: int = 60

    # Retry settings (exponential backoff handles rate limits)
    max_retries: int = 5
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker pattern."""

    failure_threshold: int = 5  # Number of failures before opening circuit
    recovery_timeout: int = 60  # Seconds to wait before trying again
    success_threshold: int = 2  # Number of successes to close circuit


@dataclass
class InterleavedConfig:
    """Configuration for API-interleaved parallel car processing."""

    # Master switch
    enabled: bool = True

    # Car processing limits
    max_concurrent_cars: int = 6  # Max cars to process simultaneously

    # Task queue settings
    task_queue_size: int = 500  # Max tasks per resource queue
    worker_count: int = 30  # Concurrent asyncio workers (lightweight coroutines)

    # Resource budgets (prevents starvation and rate limits)
    gemini_flash_max_pending: int = 25  # Max pending Gemini Flash tasks
    gemini_flash_priority_boost: int = 2  # Priority boost when queue is low
    gemini_pro_max_pending: int = 8  # Max pending Gemini Pro tasks
    custom_search_max_pending: int = 20  # Max pending search tasks (reduced to avoid rate limits)
    custom_search_priority_boost: int = 1  # Priority boost when queue is low

    # Batching settings
    spec_batch_size: int = 10  # Specs per Gemini extraction call
    search_batch_size: int = 1  # Searches per batch (kept at 1 for accuracy)

    # Timeouts
    task_timeout: float = 60.0  # Single task timeout in seconds
    phase_timeout: float = 300.0  # Phase timeout in seconds

    # Car fairness
    round_robin_enabled: bool = True  # Alternate between cars


# Global configuration instances
rate_limit_config = RateLimitConfig()
circuit_breaker_config = CircuitBreakerConfig()
interleaved_config = InterleavedConfig()
