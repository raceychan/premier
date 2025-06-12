import asyncio
import functools
from typing import Any, Awaitable, Callable, TypeVar, Union

T = TypeVar('T')
WaitStrategy = Union[int, list[int], Callable[[int], Union[int, float]]]


def retry(
    max_attempts: int = 3,
    wait: WaitStrategy = 1,
    exceptions: tuple[type[Exception], ...] = (Exception,)
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Retry decorator for async functions with configurable wait strategies.
    
    Args:
        max_attempts: Maximum number of retry attempts
        wait: Wait strategy - int (fixed seconds), list[int] (per-attempt seconds), 
              or callable (function of attempt number)
        exceptions: Tuple of exception types to retry on
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        break
                    
                    wait_time = _calculate_wait_time(wait, attempt)
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
            
            if last_exception is not None:
                raise last_exception
            raise RuntimeError("Retry failed without capturing exception")
        
        return wrapper
    return decorator


def _calculate_wait_time(wait: WaitStrategy, attempt: int) -> float:
    """Calculate wait time based on strategy and attempt number."""
    if isinstance(wait, int):
        return float(wait)
    elif isinstance(wait, list):
        if attempt < len(wait):
            return float(wait[attempt])
        return float(wait[-1]) if wait else 0.0
    elif callable(wait):
        return float(wait(attempt))
    return 0.0