import inspect
import typing as ty
from functools import wraps

from premier._types import AsyncFunc, KeyMaker, P, R, SyncFunc, ThrottleAlgo, make_key
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

    @ty.overload
    def throttle(
        self,
        throttle_algo: (
            ty.Literal[ThrottleAlgo.FIXED_WINDOW]
            | ty.Literal[ThrottleAlgo.SLIDING_WINDOW]
            | ty.Literal[ThrottleAlgo.TOKEN_BUCKET]
        ),
        quota: int,
        duration: int,
        keymaker: KeyMaker | None = None,
    ) -> ty.Callable[[SyncFunc[P, R]], SyncFunc[P, R]]: ...

    @ty.overload
    def throttle(
        self,
        throttle_algo: ty.Literal[ThrottleAlgo.LEAKY_BUCKET],
        quota: int,
        duration: int,
        keymaker: KeyMaker | None = None,
        bucket_size: int = -1,
    ) -> ty.Callable[[SyncFunc[P, R]], SyncFunc[P, R]]: ...

    def throttle(
        self,
        throttle_algo: ThrottleAlgo,
        quota: int,
        duration: int,
        keymaker: KeyMaker | None = None,
        bucket_size: int = -1,
    ) -> (
        ty.Callable[[ty.Callable[..., R]], ty.Callable[..., R]]
        | ty.Callable[[ty.Callable[..., None]], ty.Callable[..., None]]
    ):

        @ty.overload
        def wrapper(func: SyncFunc[P, R]) -> SyncFunc[P, R | None]: ...

        @ty.overload
        def wrapper(func: AsyncFunc[P, R]) -> AsyncFunc[P, R | None]: ...

        def wrapper(
            func: SyncFunc[P, R] | AsyncFunc[P, R]
        ) -> SyncFunc[P, R | None] | AsyncFunc[P, R | None]:
            @wraps(func)
            def inner(*args: P.args, **kwargs: P.kwargs) -> R | None:
                nonlocal func
                func = ty.cast(SyncFunc[P, R], func)
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

            @wraps(func)
            async def ainner(*args: P.args, **kwargs: P.kwargs) -> R | None:
                nonlocal func
                func = ty.cast(AsyncFunc[P, R], func)
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

            return ainner if inspect.iscoroutinefunction(func) else inner

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


throttler = Throttler().config(DefaultHandler())
