import asyncio
import functools
import time
from collections.abc import Callable
from typing import Awaitable, Optional, TypeVar, Union

from typing_extensions import assert_never

from premier.interface import P
from premier.timer import ILogger

T = TypeVar("T")

N = float | int

WaitStrategy = Union[N, list[N], Callable[[int], N]]


def _wait_time_calculator_factory(wait: WaitStrategy) -> Callable[[int], float]:
    match wait:
        case int():

            def algo(_: int) -> float:
                return wait

        case float():

            def algo(_: int) -> float:
                return wait

        case list():

            def algo(attempts: int) -> float:
                return wait[attempts]

        case Callable():

            def algo(attempts: int) -> float:
                return wait(attempts)

        case _ as unreacheable:
            assert_never(unreacheable)
    return algo


# TODO: 1. add `on_fail` callback, receives *args, **kwargs, return R
# circuitbreaker: bool, if True, call on_fail without calling function


def retry(
    max_attempts: int = 3,
    wait: WaitStrategy = 1,
    exceptions: tuple[type[Exception], ...] = (Exception,),  # TODO: retry on, raise on
    on_fail: Callable[P, Awaitable[None]] | None = None,
    logger: Optional[ILogger] = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Retry decorator for async functions with configurable wait strategies.

    Args:
        max_attempts: Maximum number of retry attempts
        wait: Wait strategy - int (fixed seconds), list[int] (per-attempt seconds),
              or callable (function of attempt number)
        exceptions: Tuple of exception types to retry on
        on_fail: Optional callback to execute on failure
        logger: Optional logger to log retry attempts
    """
    get_wait_time = _wait_time_calculator_factory(wait)

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    if logger and attempt > 0:
                        logger.info(f"{func.__name__}: Retry attempt {attempt + 1}/{max_attempts}")
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        if logger:
                            logger.exception(f"{func.__name__}: All {max_attempts} retry attempts failed. Last error: {e}")
                        break

                    if logger:
                        wait_time = get_wait_time(attempt)
                        logger.info(f"{func.__name__}: Attempt {attempt + 1}/{max_attempts} failed with {type(e).__name__}: {e}. Retrying in {wait_time}s...")

                    if on_fail is not None:
                        await on_fail(*args, **kwargs)

                    wait_time = get_wait_time(attempt)
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)

            assert last_exception
            raise last_exception

        return wrapper

    return decorator


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type[Exception] = Exception,
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time in seconds before attempting to recover
            expected_exception: Exception type to track for failures
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def __call__(self, func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        """Decorate function with circuit breaker."""
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            if self.state == "OPEN":
                if self._should_attempt_reset():
                    self.state = "HALF_OPEN"
                else:
                    raise CircuitBreakerOpenException(
                        f"Circuit breaker is OPEN. Last failure: {self.last_failure_time}"
                    )
            
            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise e
        
        return wrapper
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful function call."""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self):
        """Handle failed function call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open."""
    pass
