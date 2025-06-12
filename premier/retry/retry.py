import asyncio
import functools
from collections.abc import Callable
from typing import Any, Awaitable, TypeVar, Union

from typing_extensions import assert_never

T = TypeVar("T")

N = float | int

WaitStrategy = Union[N, list[N], Callable[[int], N]]


def wait_time_calculator_factory(wait: WaitStrategy) -> Callable[[int], float]:
    match wait:
        case int():

            def algo(attempts: int) -> float:
                return wait

        case float():

            def algo(attempts: int) -> float:
                return wait

        case list():

            def algo(attemps: int) -> float:
                return wait[attemps]

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
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Retry decorator for async functions with configurable wait strategies.

    Args:
        max_attempts: Maximum number of retry attempts
        wait: Wait strategy - int (fixed seconds), list[int] (per-attempt seconds),
              or callable (function of attempt number)
        exceptions: Tuple of exception types to retry on
    """
    get_wait_time = wait_time_calculator_factory(wait)

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

                    wait_time = get_wait_time(attempt)
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)

            if last_exception is not None:
                raise last_exception
            raise RuntimeError("Retry failed without capturing exception")

        return wrapper

    return decorator
