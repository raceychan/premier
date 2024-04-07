import inspect
import typing as ty
from functools import wraps
from inspect import isawaitable

from premier._types import (  # ThrottleInfo, Duration
    Algorithm,
    AnyAsyncFunc,
    AnyFunc,
    Duration,
    KeyMaker,
    P,
    QuotaCounter,
)
from premier.quota_counter import MemoryCounter
from premier.throttle_algo import (
    Bucket,
    QuotaExceedsError,
    ThrottleAlgo,
    algo_registry,
    func_keymaker,
)


class _Throttler:
    """
    This is a singleton, we might want to create sub instances
    with different configs
    """

    _algo_cache: ty.ClassVar[dict[str, Algorithm]] = dict()

    _counter: QuotaCounter
    _keyspace: str
    _algo: ThrottleAlgo

    def __init__(self):
        self.__ready = False

    @property
    def ready(self):
        return self.__ready

    def config(
        self,
        counter: QuotaCounter = MemoryCounter(),
        *,
        algo: ThrottleAlgo = ThrottleAlgo.FIXED_WINDOW,
        keyspace: str = "premier",
    ):
        self._counter = counter
        self._algo = algo
        self._keyspace = keyspace
        self.__ready = True
        return self

    def get_algorithm(self, key: str, algo_type: str):
        if not (algo := self._algo_cache.get(key, None)):
            algo = algo_registry[algo_type](self._counter)
            self._algo_cache[key] = algo
        return algo

    def get_token(
        self, key: str, algo_type: ThrottleAlgo, quota: int, duration_s: int
    ) -> None | ty.Awaitable[None]:
        if not self.__ready:
            raise Exception("not instantiated")
        algo = self.get_algorithm(key, algo_type)
        time_remains = algo.get_token(key, quota, duration_s)
        if time_remains != -1:
            raise QuotaExceedsError(quota, duration_s, time_remains)

    def clear(self):
        if not self._counter:
            return
        self._counter.clear(self._keyspace)

    def throttle(
        self,
        func,
        throttle_algo: ThrottleAlgo,
        keymaker: KeyMaker | None,
        bucket_size: int | None,
        quota: int,
        duration: int,
    ):
        funckey = func_keymaker(func, throttle_algo, self._keyspace)

        if throttle_algo is ThrottleAlgo.LEAKY_BUCKET:
            if not bucket_size:
                raise ValueError("leaky bucket without bucket size")
            bucket = Bucket(self._counter)
            return bucket(funckey, func, bucket_size, quota, duration)

        @wraps(func)
        def inner(*args: P.args, **kwargs: P.kwargs):
            key = f"{funckey}:{keymaker(*args, **kwargs)}" if keymaker else funckey
            self.get_token(key, throttle_algo, quota, duration)
            res = func(*args, **kwargs)
            return res

        return inner

    def athrottle(
        self,
        func,
        throttle_algo: ThrottleAlgo,
        keymaker: KeyMaker | None,
        bucket_size: int | None,
        quota: int,
        duration: int,
    ) -> AnyAsyncFunc:
        @wraps(func)
        async def async_inner(*args, **kwargs):
            raise NotImplementedError
            inner = self.throttle(
                func, throttle_algo, keymaker, bucket_size, quota, duration
            )
            res = await func(*args, **kwargs)

            return res

        return async_inner

    def limits(
        self,
        quota: int,
        duration_s: int | Duration,
        *,
        algo: ThrottleAlgo | None = None,
        keymaker: KeyMaker | None = None,
        bucket_size: int | None = None,
    ):
        @ty.overload
        def wrapper(
            func: AnyAsyncFunc,
        ) -> AnyAsyncFunc: ...

        @ty.overload
        def wrapper(func: AnyFunc) -> AnyFunc: ...

        def wrapper(func: AnyFunc | AnyAsyncFunc) -> AnyFunc | AnyAsyncFunc:
            duration = (
                duration_s
                if not isinstance(duration_s, Duration)
                else duration_s.as_seconds()
            )
            throttle_algo = algo or self._algo

            """
            return throttler.dispatch(func, algo, quota, duration, bucket_size)
            """

            if inspect.iscoroutinefunction(func):
                ainner = self.athrottle(
                    func, throttle_algo, keymaker, bucket_size, quota, duration
                )
                return ainner
            return self.throttle(
                func, throttle_algo, keymaker, bucket_size, quota, duration
            )

        return wrapper


throttler = _Throttler().config()
