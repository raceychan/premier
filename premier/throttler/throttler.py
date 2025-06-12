import threading
import typing as ty
from functools import wraps
from typing import Callable

from premier.throttler.handlers import (
    DefaultHandler,
    QuotaExceedsError,
    ThrottleHandler,
)
from premier.throttler.interface import (
    KeyMaker,
    LBThrottleInfo,
    P,
    R,
    ThrottleAlgo,
    ThrottleInfo,
)

AnyFunc = Callable[P, R]


class _Throttler:
    """
    This is a singleton, we might want to create sub instances
    with different configs
    """

    # _counter: QuotaCounter[ty.Hashable, ty.Any]
    _handler: ThrottleHandler
    _aiohanlder: ty.Any
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
        handler: ThrottleHandler,
        *,
        lock: threading.Lock = threading.Lock(),
        algo: ThrottleAlgo = ThrottleAlgo.FIXED_WINDOW,
        keyspace: str = "premier",
    ):
        self._handler = handler
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
        def wrapper(func: AnyFunc[P, None]):
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
    ) -> ty.Callable[[ty.Callable[..., R]], ty.Callable[..., R]]:
        def wrapper(func: AnyFunc[P, R]) -> AnyFunc[P, R]:
            info = ThrottleInfo(
                func=func,
                keyspace=self._keyspace,
                algo=throttle_algo,
            )

            @wraps(func)
            def inner(*args: P.args, **kwargs: P.kwargs) -> R:
                key = info.make_key(keymaker, args, kwargs)
                countdown = self._handler.dispatch(info.algo)(
                    key, quota=quota, duration=duration
                )
                if countdown != -1:
                    raise QuotaExceedsError(quota, duration, countdown)
                res = func(*args, **kwargs)
                return res

            return inner

        return wrapper


throttler = _Throttler().config(DefaultHandler(dict()))
