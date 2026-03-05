"""
Async Utilities for API Rate Limiting and HTTP Operations
Implements industry-standard patterns for async operations.
"""
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, ParamSpec

import aiohttp
from aiohttp import ClientSession, TCPConnector
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    before_sleep_log,
    after_log,
)

from benchmarking_agent.async_config import rate_limit_config

# Type variables for generic functions
P = ParamSpec('P')
T = TypeVar('T')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# RATE LIMITER - Token Bucket Algorithm
# ============================================================================

class TokenBucket:
    """
    Thread-safe token bucket rate limiter for async operations.
    Implements the token bucket algorithm for smooth rate limiting.
    """

    def __init__(
        self,
        rate: float,  # tokens per second
        capacity: int,  # max tokens in bucket
        initial_tokens: Optional[int] = None
    ):
        self.rate = rate
        self.capacity = capacity
        self.tokens = initial_tokens or capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens from the bucket, waiting if necessary."""
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now

                # Add tokens based on elapsed time
                self.tokens = min(
                    self.capacity,
                    self.tokens + elapsed * self.rate
                )

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return

                # Calculate wait time
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.rate
                await asyncio.sleep(wait_time)


# ============================================================================
# RATE LIMITER - Semaphore-based Concurrency Control
# ============================================================================

class RateLimiter:
    """
    Comprehensive rate limiter combining semaphore for concurrency
    and token bucket for request rate control.
    """

    def __init__(
        self,
        max_concurrent: int,
        requests_per_second: float,
        burst_limit: Optional[int] = None
    ):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.token_bucket = TokenBucket(
            rate=requests_per_second,
            capacity=burst_limit or int(requests_per_second * 2)
        )
        self._call_count = 0
        self._start_time = time.monotonic()

    @asynccontextmanager
    async def acquire(self):
        """Acquire both semaphore and token for rate-limited execution."""
        async with self.semaphore:
            await self.token_bucket.acquire()
            self._call_count += 1
            yield

    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        elapsed = time.monotonic() - self._start_time
        return {
            "total_calls": self._call_count,
            "elapsed_seconds": elapsed,
            "calls_per_second": self._call_count / elapsed if elapsed > 0 else 0,
            "available_tokens": self.token_bucket.tokens,
        }


# ============================================================================
# CIRCUIT BREAKER PATTERN
# ============================================================================

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """
    Circuit breaker pattern implementation to prevent cascading failures.
    Automatically opens circuit after threshold failures, preventing
    unnecessary calls to failing services.
    """

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 2
    state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    failure_count: int = field(default=0, init=False)
    success_count: int = field(default=0, init=False)
    last_failure_time: Optional[float] = field(default=None, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def call(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            # Check if circuit should transition from OPEN to HALF_OPEN
            if self.state == CircuitState.OPEN:
                if (
                    self.last_failure_time
                    and time.monotonic() - self.last_failure_time > self.recovery_timeout
                ):
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    raise Exception(
                        f"Circuit breaker is OPEN. "
                        f"Retry in {self.recovery_timeout - (time.monotonic() - self.last_failure_time):.1f}s"
                    )

        # Execute function
        try:
            result = await func(*args, **kwargs)

            # Record success
            async with self._lock:
                if self.state == CircuitState.HALF_OPEN:
                    self.success_count += 1
                    if self.success_count >= self.success_threshold:
                        logger.info("Circuit breaker closing after successful recovery")
                        self.state = CircuitState.CLOSED
                        self.failure_count = 0
                elif self.state == CircuitState.CLOSED:
                    self.failure_count = 0

            return result

        except Exception as e:
            # Record failure
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.monotonic()

                if self.state == CircuitState.HALF_OPEN:
                    logger.warning("Circuit breaker opening after failure in HALF_OPEN state")
                    self.state = CircuitState.OPEN
                elif (
                    self.state == CircuitState.CLOSED
                    and self.failure_count >= self.failure_threshold
                ):
                    logger.error(
                        f"Circuit breaker opening after {self.failure_count} failures"
                    )
                    self.state = CircuitState.OPEN

            raise e


# ============================================================================
# ASYNC HTTP CLIENT MANAGER
# ============================================================================

class AsyncHTTPClient:
    """
    Managed async HTTP client with connection pooling, timeouts,
    and automatic resource cleanup.
    """

    def __init__(
        self,
        max_connections: int = 100,
        max_connections_per_host: int = 30,
        timeout: int = 30
    ):
        self.max_connections = max_connections
        self.max_connections_per_host = max_connections_per_host
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[ClientSession] = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self):
        """Initialize the HTTP session with connection pooling."""
        if self._session is None or self._session.closed:
            connector = TCPConnector(
                limit=self.max_connections,
                limit_per_host=self.max_connections_per_host,
                ttl_dns_cache=300,  # DNS cache for 5 minutes
                enable_cleanup_closed=True,
            )
            self._session = ClientSession(
                connector=connector,
                timeout=self.timeout,
                raise_for_status=False,  # Handle status codes manually
            )
            logger.info(
                f"HTTP client started: max_connections={self.max_connections}, "
                f"per_host={self.max_connections_per_host}"
            )

    async def close(self):
        """Close the HTTP session and release resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            await asyncio.sleep(0.25)  # Allow time for connections to close
            logger.info("HTTP client closed")

    @property
    def session(self) -> ClientSession:
        """Get the active session or raise error."""
        if self._session is None or self._session.closed:
            raise RuntimeError("HTTP client not started. Use 'async with' or call start()")
        return self._session

    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Execute GET request."""
        return await self.session.get(url, **kwargs)

    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Execute POST request."""
        return await self.session.post(url, **kwargs)


# ============================================================================
# RETRY DECORATOR WITH EXPONENTIAL BACKOFF
# ============================================================================

def async_retry(
    max_attempts: int = 5,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for async functions with exponential backoff retry logic.
    Uses tenacity library for production-grade retry handling.
    """
    return AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=min_wait, max=max_wait),
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG),
    )


# ============================================================================
# GLOBAL RATE LIMITERS
# ============================================================================

# Create global rate limiters for different APIs
custom_search_limiter = RateLimiter(
    max_concurrent=rate_limit_config.custom_search_max_concurrent,
    requests_per_second=rate_limit_config.custom_search_requests_per_second,
    burst_limit=rate_limit_config.custom_search_burst_limit,
)

gemini_flash_limiter = RateLimiter(
    max_concurrent=rate_limit_config.gemini_flash_max_concurrent,
    requests_per_second=rate_limit_config.gemini_flash_requests_per_minute / 60.0,
    burst_limit=rate_limit_config.gemini_flash_max_concurrent * 2,
)

gemini_pro_limiter = RateLimiter(
    max_concurrent=rate_limit_config.gemini_pro_max_concurrent,
    requests_per_second=rate_limit_config.gemini_pro_requests_per_minute / 60.0,
    burst_limit=rate_limit_config.gemini_pro_max_concurrent * 2,
)

# Circuit breakers for each API
custom_search_circuit_breaker = CircuitBreaker(failure_threshold=10, recovery_timeout=120)
gemini_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)


logger.info("Async utilities initialized with rate limiters and circuit breakers")
