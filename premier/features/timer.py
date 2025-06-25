import asyncio
from asyncio import wait_for as await_for
from contextlib import contextmanager
from functools import wraps
from inspect import iscoroutinefunction
from time import perf_counter
from typing import Any, Awaitable, Callable, Optional, Protocol, cast, overload

from premier.interface import FlexDecor, P, R
from premier.features.timer_errors import TimeoutError as PremierTimeoutError


class ILogger(Protocol):
    def exception(self, msg: str): ...

    def info(self, msg: str): ...


CustomLogger = Callable[[float], None]

ValidLogger = ILogger | CustomLogger


def timeit(
    func__: Callable[P, R] | None = None,
    *,
    logger: Optional[ValidLogger] = None,
    precision: int = 2,
    log_threshold: float = 0.1,
    with_args: bool = False,
    show_fino: bool = True,
) -> FlexDecor[P, R]:

    @overload
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, R]: ...

    @overload
    def decorator(func: Callable[P, R]) -> Callable[P, R]: ...

    def decorator(
        func: Callable[P, R] | Callable[P, Awaitable[R]],
    ) -> Callable[P, R] | Callable[P, Awaitable[R]]:
        def build_logmsg(
            timecost: float,
            func_args: tuple[Any, ...],
            func_kwargs: dict[Any, Any],
        ):

            func_repr = func.__qualname__
            if with_args:
                arg_repr = ", ".join(f"{arg}" for arg in func_args)
                kwargs_repr = ", ".join(f"{k}={v}" for k, v in func_kwargs.items())
                func_repr = f"{func_repr}({arg_repr}, {kwargs_repr})"

            msg = f"{func_repr} {timecost}s"

            if show_fino:
                func_code = func.__code__
                location = f"{func_code.co_filename}({func_code.co_firstlineno})"
                msg = f"{location} {msg}"

            return msg

        @contextmanager
        def log_callback(*args: P.args, **kwargs: P.kwargs):
            pre = perf_counter()
            yield
            aft = perf_counter()
            timecost = round(aft - pre, precision)

            if timecost < log_threshold:
                return

            if logger:
                if callable(logger):
                    logger(timecost)
                else:
                    logger.info(build_logmsg(timecost, args, kwargs))
            else:
                print(build_logmsg(timecost, args, kwargs))

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            f = cast(Callable[P, R], func)
            with log_callback(*args, **kwargs):
                res = f(*args, **kwargs)
            return res

        @wraps(func)
        async def awrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            f = cast(Callable[P, Awaitable[R]], func)
            with log_callback(*args, **kwargs):
                res = await f(*args, **kwargs)
            return res

        if iscoroutinefunction(func):
            return awrapper
        else:
            return wrapper

    if func__ is None:
        return decorator
    else:
        return decorator(func__)


def timeout(seconds: int, *, logger: ILogger | None = None):
    def decor_dispatch(func: Callable[..., Any]):
        if not iscoroutinefunction(func):
            raise ValueError("timeout decorator only supports async functions")

        async def async_timeout(*args: Any, **kwargs: Any):
            coro = func(*args, **kwargs)
            try:
                res = await await_for(coro, seconds)
            except asyncio.TimeoutError as te:
                timeout_error = PremierTimeoutError(seconds, func.__name__)
                if logger:
                    logger.exception(str(timeout_error))
                raise timeout_error from te
            return res

        return async_timeout

    return decor_dispatch
