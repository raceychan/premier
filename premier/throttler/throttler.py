import asyncio
import inspect
from functools import wraps
from typing import Awaitable, Callable

from premier.providers import AsyncInMemoryCache
from premier.throttler.errors import QuotaExceedsError, UninitializedHandlerError
from premier.throttler.handler import AsyncDefaultHandler
from premier.throttler.interface import (
    AsyncThrottleHandler,
    KeyMaker,
    P,
    R,
    ThrottleAlgo,
    make_key,
)


class Throttler:
    """
    Async-only throttler for rate limiting functions
    """

    _aiohandler: AsyncThrottleHandler
    _keyspace: str
    _algo: ThrottleAlgo

    def __init__(
        self,
        handler: AsyncThrottleHandler | None = None,
        algo: ThrottleAlgo = ThrottleAlgo.FIXED_WINDOW,
        keyspace: str = "premier:throttler",
    ):
        self._aiohandler = handler or AsyncDefaultHandler(AsyncInMemoryCache())
        self._algo = algo
        self._keyspace = keyspace

    @property
    def default_algo(self):
        return self._algo

    async def clear(self, keyspace: str | None = None):
        if not self._aiohandler:
            return
        if keyspace is None:
            keyspace = self._keyspace
        await self._aiohandler.clear(keyspace)

    def throttle(
        self,
        throttle_algo: ThrottleAlgo,
        quota: int,
        duration: int,
        keymaker: KeyMaker | None = None,
        bucket_size: int = -1,
    ) -> Callable[[Callable[P, R]], Callable[P, Awaitable[R | None]]]:

        def wrapper(func: Callable[P, R]) -> Callable[P, Awaitable[R | None]]:
            @wraps(func)
            async def ainner(*args: P.args, **kwargs: P.kwargs) -> R | None:
                if not self._aiohandler:
                    raise UninitializedHandlerError("Async handler not configured")
                key = make_key(
                    func,
                    algo=throttle_algo,
                    keyspace=self._keyspace,
                    args=args,
                    kwargs=kwargs,
                    keymaker=keymaker,
                )
                if throttle_algo is ThrottleAlgo.LEAKY_BUCKET:
                    countdown = await self._aiohandler.leaky_bucket(
                        key, bucket_size=bucket_size, quota=quota, duration=duration
                    )
                    if countdown != -1:
                        # For leaky bucket, we sleep for the delay instead of raising error
                        await asyncio.sleep(countdown)

                    # Execute the function after delay
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                countdown = await self._aiohandler.dispatch(throttle_algo)(
                    key, quota=quota, duration=duration
                )
                if countdown != -1:
                    raise QuotaExceedsError(quota, duration, countdown)

                # Handle both sync and async functions
                if inspect.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            return ainner

        return wrapper

    def fixed_window(self, quota: int, duration: int, keymaker: KeyMaker | None = None):
        return self.throttle(
            quota=quota,
            duration=duration,
            keymaker=keymaker,
            throttle_algo=ThrottleAlgo.FIXED_WINDOW,
        )

    def sliding_window(
        self, quota: int, duration: int, keymaker: KeyMaker | None = None
    ):
        return self.throttle(
            quota=quota,
            duration=duration,
            keymaker=keymaker,
            throttle_algo=ThrottleAlgo.SLIDING_WINDOW,
        )

    def token_bucket(self, quota: int, duration: int, keymaker: KeyMaker | None = None):
        return self.throttle(
            quota=quota,
            duration=duration,
            keymaker=keymaker,
            throttle_algo=ThrottleAlgo.TOKEN_BUCKET,
        )

    def leaky_bucket(
        self,
        quota: int,
        bucket_size: int,
        duration: int,
        keymaker: KeyMaker | None = None,
    ):
        return self.throttle(
            bucket_size=bucket_size,
            quota=quota,
            duration=duration,
            keymaker=keymaker,
            throttle_algo=ThrottleAlgo.LEAKY_BUCKET,
        )

    async def get_countdown(
        self,
        throttle_algo: ThrottleAlgo,
        quota: int,
        duration: int,
        key: str | None = None,
    ):
        key = key or f"{self._keyspace}:"
        if not self._aiohandler:
            raise UninitializedHandlerError("Async handler not configured")
        countdown = await self._aiohandler.dispatch(throttle_algo)(
            key, quota=quota, duration=duration
        )
        if countdown == -1:  # func is ready to be executed
            return
        raise QuotaExceedsError(quota, duration, countdown)
