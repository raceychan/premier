import inspect
from functools import wraps
from typing import Callable, Literal, cast, overload

from premier.interface import AsyncFunc, KeyMaker, P, R, SyncFunc, ThrottleAlgo, make_key
from premier.errors import QuotaExceedsError, UninitializedHandlerError
from premier.handler import AsyncThrottleHandler, DefaultHandler, ThrottleHandler


class Throttler:
    """
    This is a singleton, we might want to create sub instances
    with different configs
    """

    _handler: ThrottleHandler
    _keyspace: str
    _algo: ThrottleAlgo

    def __init__(self):
        self.__ready = False

    @property
    def ready(self):
        return self.__ready

    @property
    def default_algo(self):
        return self._algo

    def config(
        self,
        handler: ThrottleHandler | None = None,
        *,
        aiohandler: AsyncThrottleHandler | None = None,
        algo: ThrottleAlgo = ThrottleAlgo.FIXED_WINDOW,
        keyspace: str = "premier",
    ):
        self._handler = handler or DefaultHandler()
        self._aiohandler = aiohandler
        self._algo = algo
        self._keyspace = keyspace
        self.__ready = True
        return self

    def clear(self, keyspace: str | None = None):
        if not self._handler:
            return
        if keyspace is None:
            keyspace = self._keyspace
        self._handler.clear(keyspace)

    async def aclear(self, keyspace: str | None = None):
        if not self._aiohandler:
            return
        if keyspace is None:
            keyspace = self._keyspace
        await self._aiohandler.clear(keyspace)

    @overload
    def throttle(
        self,
        throttle_algo: (
            Literal[ThrottleAlgo.FIXED_WINDOW]
            | Literal[ThrottleAlgo.SLIDING_WINDOW]
            | Literal[ThrottleAlgo.TOKEN_BUCKET]
        ),
        quota: int,
        duration: int,
        keymaker: KeyMaker | None = None,
    ) -> Callable[[SyncFunc[P, R]], SyncFunc[P, R]]: ...

    @overload
    def throttle(
        self,
        throttle_algo: Literal[ThrottleAlgo.LEAKY_BUCKET],
        quota: int,
        duration: int,
        keymaker: KeyMaker | None = None,
        bucket_size: int = -1,
    ) -> Callable[[SyncFunc[P, R]], SyncFunc[P, R]]: ...

    def throttle(
        self,
        throttle_algo: ThrottleAlgo,
        quota: int,
        duration: int,
        keymaker: KeyMaker | None = None,
        bucket_size: int = -1,
    ) -> (
        Callable[[Callable[..., R]], Callable[..., R]]
        | Callable[[Callable[..., None]], Callable[..., None]]
    ):

        @overload
        def wrapper(func: SyncFunc[P, R]) -> SyncFunc[P, R]: ...

        @overload
        def wrapper(func: AsyncFunc[P, R]) -> AsyncFunc[P, R]: ...

        def wrapper(
            func: SyncFunc[P, R] | AsyncFunc[P, R],
        ) -> SyncFunc[P, R] | AsyncFunc[P, R]:
            if not inspect.iscoroutinefunction(func):
                func = cast(SyncFunc[P, R], func)

                @wraps(func)
                def inner(*args: P.args, **kwargs: P.kwargs) -> R | None:
                    key = make_key(
                        func,
                        algo=throttle_algo,
                        keyspace=self._keyspace,
                        args=args,
                        kwargs=kwargs,
                        keymaker=keymaker,
                    )
                    if throttle_algo is ThrottleAlgo.LEAKY_BUCKET:
                        scheduler = self._handler.leaky_bucket(
                            key, bucket_size=bucket_size, quota=quota, duration=duration
                        )
                        return scheduler(func, *args, **kwargs)
                    countdown = self._handler.dispatch(throttle_algo)(
                        key, quota=quota, duration=duration
                    )
                    if countdown != -1:
                        raise QuotaExceedsError(quota, duration, countdown)
                    return func(*args, **kwargs)

                return inner
            else:
                func = cast(AsyncFunc[P, R], func)

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
                        scheduler = self._aiohandler.leaky_bucket(
                            key, bucket_size=bucket_size, quota=quota, duration=duration
                        )
                        return await scheduler(func, *args, **kwargs)
                    countdown = await self._aiohandler.dispatch(throttle_algo)(
                        key, quota=quota, duration=duration
                    )
                    if countdown != -1:
                        raise QuotaExceedsError(quota, duration, countdown)
                    return await func(*args, **kwargs)

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


throttler = Throttler().config(DefaultHandler())
