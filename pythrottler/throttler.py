import inspect
import typing as ty

from pythrottler._types import Algorithm, Duration, P, QuotaCounter, R, ThrottleInfo
from pythrottler.throttle_algo import (
    QuotaExceedsError,
    ThrottleAlgo,
    algo_registry,
    key_maker,
)


class _Throttler:
    """
    This is a singleton, we might want to create sub instances
    with different configs
    """

    _throttle_info: dict[str, ThrottleInfo] = dict()
    _algo_cache: dict[str, Algorithm] = dict()

    def __init__(
        self,
        counter: QuotaCounter | None = None,
        *,
        algo: ThrottleAlgo = ThrottleAlgo.FIXED_WINDOW,
        keyspace: str = "",
    ):

        self._counter = counter
        # === config ===
        self._algo = algo
        self._keyspace = keyspace
        # === config ===
        self.__ready = False

    def config(
        self,
        counter: QuotaCounter,
        *,
        algo: ThrottleAlgo = ThrottleAlgo.FIXED_WINDOW,
        keyspace: str = "",
    ):
        self._counter = counter
        self._algo = algo
        self._keyspace = keyspace
        self.__ready = True

    def register(self, key: str, quota: int, duration: Duration, algo: ThrottleAlgo):
        self._throttle_info[key] = ThrottleInfo(
            key,
            quota=quota,
            duration=duration,
            algorithm=algo,
        )

    def get_token(self, key: str):
        if not self.__ready:
            raise Exception("not instantiated")

        throttle_info = self._throttle_info[key]
        if (algo := self._algo_cache.get(key, None)) is None:
            algo = algo_registry[throttle_info.algorithm](self._counter)
            self._algo_cache[key] = algo

        duration_s = throttle_info.duration.as_seconds()
        time_remains = algo.get_token(
            throttle_info.key, throttle_info.quota, duration_s
        )

        if time_remains != -1:
            raise QuotaExceedsError(throttle_info.quota, duration_s, time_remains)

    async def async_get_token(self, key: str):
        raise NotImplementedError


def custom_keymaker(*args, **kwargs) -> str: ...


def limits(
    quota: int = 3,
    duration_s: int | Duration = 5,
    *,
    algo: ThrottleAlgo | None = None,
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
        throttler_key = key_maker(func, throttler_algo, throttler._keyspace)
        throttler.register(throttler_key, quota, duration, throttler_algo)

        def inner(*args: P.args, **kwargs: P.kwargs):
            # TODO: make key receives args and kwargs
            throttler.get_token(throttler_key)
            return func(*args, **kwargs)

        if not inspect.iscoroutinefunction(func):
            return inner
        else:

            async def async_inner(*args: P.args, **kwargs: P.kwargs):
                await throttler.async_get_token(throttler_key)
                return await func(*args, **kwargs)

            return async_inner

    return wrapper


throttler = _Throttler()
