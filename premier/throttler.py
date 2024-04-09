import threading
import typing as ty
from functools import wraps

from premier._types import (
    KeyMaker,
    LBThrottleInfo,
    P,
    QuotaCounter,
    R,
    SyncFunc,
    ThrottleAlgo,
    ThrottleInfo,
)
from premier.handlers import QuotaExceedsError
from premier.quota_counter import MemoryCounter


class _Throttler:
    """
    This is a singleton, we might want to create sub instances
    with different configs
    """

    _counter: QuotaCounter[ty.Hashable, ty.Any]
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
        counter: QuotaCounter[ty.Hashable, ty.Any] = MemoryCounter(),
        *,
        lock: threading.Lock = threading.Lock(),
        algo: ThrottleAlgo = ThrottleAlgo.FIXED_WINDOW,
        keyspace: str = "premier",
    ):
        self._counter = counter
        self._lock = lock
        self._algo = algo
        self._keyspace = keyspace
        self.__ready = True
        return self

    def clear(self):
        if not self._counter:
            return
        self._counter.clear(self._keyspace)

    def leaky_bucket(
        self,
        bucket_size: int,
        quota: int,
        duration_s: int,
        *,
        keymaker: KeyMaker | None = None,
    ):
        def wrapper(func: SyncFunc[P, R]):
            info = LBThrottleInfo(
                func=func,
                algo=ThrottleAlgo.LEAKY_BUCKET,
                keyspace=self._keyspace,
                bucket_size=bucket_size,
            )
            handler = LeakyBucketHandler(self._counter, self._lock, info)

            @wraps(func)
            def inner(*args: P.args, **kwargs: P.kwargs):
                key = info.make_key(keymaker, args, kwargs)
                return handler.schedule_task(
                    key,
                    quota=quota,
                    duration=duration_s,
                    func=func,
                    args=args,
                    kwargs=kwargs,
                )

            return inner

        return wrapper

    def throttle(
        self,
        throttle_algo: ThrottleAlgo,
        quota: int,
        duration: int,
        keymaker: KeyMaker | None = None,
    ):
        def wrapper(func: SyncFunc[P, R]) -> SyncFunc[P, R]:
            info = ThrottleInfo(
                func=func,
                keyspace=self._keyspace,
                algo=throttle_algo,
            )
            handler = algo_registry[info.algo](self._counter, self._lock, info)

            @wraps(func)
            def inner(*args: P.args, **kwargs: P.kwargs) -> R:
                key = info.make_key(keymaker, args, kwargs)
                cnt_down = handler.acquire(key, quota=quota, duration=duration)
                if cnt_down != -1:
                    raise QuotaExceedsError(quota, duration, cnt_down)
                res = func(*args, **kwargs)
                return res

            return inner

        return wrapper


throttler = _Throttler().config()
