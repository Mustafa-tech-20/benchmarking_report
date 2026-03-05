"""
Async Configuration for Rate Limiting and Concurrency Control
"""
from dataclasses import dataclass
from typing import Dict


@dataclass
class RateLimitConfig:
    """Configuration for API rate limiting."""

    # Google Custom Search API limits
    # Free tier: 100 queries/day, paid tier: 10,000 queries/day
    # Limit to 10 requests/second to be safe
    custom_search_max_concurrent: int = 10
    custom_search_requests_per_second: float = 10.0
    custom_search_burst_limit: int = 20

    # Gemini API limits
    # Gemini Flash: 15 RPM (requests per minute) free tier, 1000 RPM paid
    # Gemini Pro: 5 RPM free tier, 360 RPM paid
    gemini_flash_max_concurrent: int = 8
    gemini_flash_requests_per_minute: float = 15.0
    gemini_pro_max_concurrent: int = 3
    gemini_pro_requests_per_minute: float = 5.0

    # HTTP client settings
    max_connections: int = 100
    max_connections_per_host: int = 30
    connection_timeout: int = 30
    request_timeout: int = 60

    # Retry settings
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


# Global configuration instances
rate_limit_config = RateLimitConfig()
circuit_breaker_config = CircuitBreakerConfig()
