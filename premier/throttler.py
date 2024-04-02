import inspect
import typing as ty

from premier._types import Algorithm, Duration, P, QuotaCounter, R, ThrottleInfo
from premier.throttle_algo import (
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

    _throttle_info: ty.ClassVar[dict[str, ThrottleInfo]] = dict()
    _algo_cache: ty.ClassVar[dict[str, Algorithm]] = dict()

    _counter: QuotaCounter
    _keyspace: str
    _algo: ThrottleAlgo

    def __init__(self):
        self.__ready = False

    def config(
        self,
        counter: QuotaCounter,
        *,
        algo: ThrottleAlgo = ThrottleAlgo.FIXED_WINDOW,
        keyspace: str = "premier",
    ):
        # self._counter = counter
        # # === config ===
        # self._algo = algo
        # self._keyspace = keyspace
        # # === config ===
        self._counter = counter
        self._algo = algo
        self._keyspace = keyspace
        self.__ready = True

    def register(
        self, funckey: str, quota: int, duration: Duration, algo: ThrottleAlgo
    ):
        self._throttle_info[funckey] = ThrottleInfo(
            funckey,
            quota=quota,
            duration=duration,
            algorithm=algo,
        )

    def get_throttle_info(self, funckey: str):
        return self._throttle_info[funckey]

    def get_token(self, throttle_key: str, throttle_info: ThrottleInfo):
        if not self.__ready:
            raise Exception("not instantiated")

        funckey = throttle_info.funckey
        duration_s = throttle_info.duration.as_seconds()

        if (algo := self._algo_cache.get(funckey, None)) is None:
            algo = algo_registry[throttle_info.algorithm](self._counter)
            self._algo_cache[funckey] = algo

        time_remains = algo.get_token(throttle_key, throttle_info.quota, duration_s)

        if time_remains != -1:
            raise QuotaExceedsError(throttle_info.quota, duration_s, time_remains)

    def clear(self):
        if not self._counter:
            return
        self._counter.clear()

    async def async_get_token(self, throttle_key: str, throttler_info):
        self.get_token(throttle_key, throttle_info=throttler_info)


def limits(
    quota: int = 3,
    duration_s: int | Duration = 5,
    *,
    algo: ThrottleAlgo | None = None,
    keymaker: ty.Callable | None = None,
):
    "Register the function to be throttled"

    @ty.overload
    def wrapper(
        func: ty.Callable[P, ty.Awaitable[R]]
    ) -> ty.Callable[P, ty.Awaitable[R]]: ...

    @ty.overload
    def wrapper(func: ty.Callable[P, R]) -> ty.Callable[P, R]: ...

    def wrapper(func: ty.Callable[P, R] | ty.Callable[P, ty.Awaitable[R]]):
        duration = (
            duration_s
            if isinstance(duration_s, Duration)
            else Duration.from_seconds(duration_s)
        )
        throttler_algo = algo or throttler._algo
        funckey = func_keymaker(func, throttler_algo, throttler._keyspace)
        throttler.register(funckey, quota, duration, throttler_algo)

        def inner(*args: P.args, **kwargs: P.kwargs):
            key = f"{funckey}:{keymaker(*args, **kwargs)}" if keymaker else funckey
            throttler.get_token(key, throttler.get_throttle_info(funckey))
            return func(*args, **kwargs)

        if not inspect.iscoroutinefunction(func):
            return inner

        async def async_inner(*args: P.args, **kwargs: P.kwargs):
            key = f"{funckey}:{keymaker(*args, **kwargs)}" if keymaker else funckey
            await throttler.async_get_token(key, throttler.get_throttle_info(funckey))
            return await func(*args, **kwargs)

        return async_inner

    return wrapper


throttler = _Throttler()
