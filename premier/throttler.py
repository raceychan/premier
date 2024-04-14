import threading
import typing as ty
from functools import wraps

from premier._types import (
    KeyMaker,
    LBThrottleInfo,
    P,
    R,
    SyncFunc,
    ThrottleAlgo,
    make_key,
)
from premier.handlers import (
    AsyncThrottleHandler,
    DefaultHandler,
    QuotaExceedsError,
    ThrottleHandler,
)


class _Throttler:
    """
    This is a singleton, we might want to create sub instances
    with different configs
    """

    _handler: ThrottleHandler
    _keyspace: str
    _algo: ThrottleAlgo
    _lock: threading.Lock

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
        aiohandler: AsyncThrottleHandler | None = None,
        *,
        lock: threading.Lock = threading.Lock(),
        algo: ThrottleAlgo = ThrottleAlgo.FIXED_WINDOW,
        keyspace: str = "premier",
    ):
        self._handler = handler or DefaultHandler()
        self._lock = lock
        self._algo = algo
        self._keyspace = keyspace
        self.__ready = True
        return self

    def clear(self):
        if not self._handler:
            return
        self._handler.clear(self._keyspace)

    def leaky_bucket(
        self,
        bucket_size: int,
        quota: int,
        duration_s: int,
        *,
        keymaker: KeyMaker | None = None,
    ) -> ty.Callable[[ty.Callable[..., None]], ty.Callable[..., None]]:
        def wrapper(func: SyncFunc[P, None]):
            info = LBThrottleInfo(
                func=func,
                algo=ThrottleAlgo.LEAKY_BUCKET,
                keyspace=self._keyspace,
                bucket_size=bucket_size,
            )

            @wraps(func)
            def inner(*args: P.args, **kwargs: P.kwargs) -> None:
                key = info.make_key(keymaker, args, kwargs)
                schedule_task = self._handler.leaky_bucket(
                    key, bucket_size, quota, duration_s
                )
                return schedule_task(func, *args, **kwargs)  # type: ignore

            return inner

        return wrapper

    def throttle(
        self,
        throttle_algo: ThrottleAlgo,
        quota: int,
        duration: int,
        keymaker: KeyMaker | None = None,
        bucket_size: int = None,  # type: ignore
    ) -> (
        ty.Callable[[ty.Callable[..., R]], ty.Callable[..., R]]
        | ty.Callable[[ty.Callable[..., None]], ty.Callable[..., None]]
    ):
        def wrapper(func: SyncFunc[P, R]) -> SyncFunc[P, R] | SyncFunc[P, None]:
            @wraps(func)
            def inner(*args: P.args, **kwargs: P.kwargs) -> R:
                key = make_key(
                    func,
                    algo=throttle_algo,
                    keyspace=self._keyspace,
                    args=args,
                    kwargs=kwargs,
                    keymaker=keymaker,
                )
                countdown = self._handler.dispatch(throttle_algo)(
                    key, quota=quota, duration=duration
                )
                if countdown != -1:
                    raise QuotaExceedsError(quota, duration, countdown)
                res = func(*args, **kwargs)
                return res

            @wraps(func)
            def lb_inner(*args: P.args, **kwargs: P.kwargs) -> None:
                key = make_key(
                    func,
                    algo=throttle_algo,
                    keyspace=self._keyspace,
                    args=args,
                    kwargs=kwargs,
                    keymaker=keymaker,
                )
                schedule_task = self._handler.leaky_bucket(
                    key, bucket_size, quota, duration
                )
                return schedule_task(func, *args, **kwargs)  # type: ignore

            if throttle_algo is ThrottleAlgo.LEAKY_BUCKET:
                return lb_inner
            else:
                return inner

        return wrapper


throttler = _Throttler().config(DefaultHandler(dict()))
