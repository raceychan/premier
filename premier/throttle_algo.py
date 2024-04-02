import typing as ty
from time import perf_counter as clock
from types import FunctionType, MethodType

from premier._types import Algorithm, QuotaCounter, ThrottleAlgo


def func_keymaker(func: ty.Callable, algo: ThrottleAlgo, keyspace: str):
    if isinstance(func, MethodType):
        # It's a method, get its class name and method name
        class_name = func.__self__.__class__.__name__
        func_name = func.__name__
        fid = f"{class_name}:{func_name}"
    elif isinstance(func, FunctionType):
        # It's a standalone function
        fid = func.__name__
    else:
        try:
            fid = func.__name__
        except AttributeError:
            fid = ""

    return f"{keyspace}:{func.__module__}:{fid}:{algo.value}"


class QuotaExceedsError(Exception):
    def __init__(self, quota: int, duration: int, next_availble: float):

        msg = f"You exceeds {quota} quota in {duration} seconds, available after {next_availble:.2f} s"
        super().__init__(msg)


class _AlgoRegistry:
    def __init__(self):
        self._registry: dict[ThrottleAlgo | str, type[Algorithm]] = dict()

    def __getitem__(self, _k):
        return self._registry[_k]

    def register(self, algo_id: ThrottleAlgo | str, algo: type[Algorithm]):
        self._registry[algo_id] = algo
        return algo

    def update(self, data: dict[ThrottleAlgo | str, type[Algorithm]]):
        self._registry.update(data)

    def get(self, k, default):
        return self._registry.get(k, default)


algo_registry = _AlgoRegistry()


class FixedWindow(Algorithm):
    def __init__(self, counter: QuotaCounter[str, tuple[float, int]]):
        self._counter = counter

    def _reset_window(self, key, duration):
        self._counter.set(key, (clock() + duration, 1))

    def get_token(self, key, quota: int, duration_s: int) -> ty.Literal[-1] | float:
        time, cnt = self._counter.get(key, (clock() + duration_s, 0))

        if (now := clock()) > time:
            self._counter.set(key, (now + duration_s, 1))
            return -1  # Available now

        if cnt >= quota:
            # Return time remaining until the next window starts
            return time - now

        self._counter.set(key, (time, cnt + 1))
        return -1  # Token was available, no wait needed


class SlidingWindow(Algorithm):
    def __init__(self, counter: QuotaCounter[str, tuple[float, int]]):
        self._counter = counter

    def get_token(self, key, quota: int, duration_s: int) -> ty.Literal[-1] | float:
        now = clock()
        time, cnt = self._counter.get(key, (now, 0))

        # Calculate remaining quota and adjust based on time passed
        elapsed = now - time
        window_progress = elapsed % duration_s
        sliding_window_start = now - window_progress
        adjusted_cnt = cnt - int((elapsed // duration_s) * quota)
        cnt = max(0, adjusted_cnt)

        if cnt >= quota:
            # Return the time until the window slides enough for one token
            remains = (duration_s - window_progress) + (
                (cnt - quota + 1) / quota
            ) * duration_s
            return remains

        self._counter.set(key, (sliding_window_start, cnt + 1))
        return -1


class LeakyBucket(Algorithm):
    def __init__(self, counter: QuotaCounter[str, float]):
        self._counter = counter

    def get_token(self, key, quota: int, duration_s: int) -> ty.Literal[-1] | float:
        now = clock()
        last_leak = self._counter.get(key, now)
        elapsed = now - last_leak
        leak_rate = quota / duration_s  # tokens per second

        # Calculate the current bucket level considering the leak
        leaked_tokens = elapsed * leak_rate
        new_level = max(0, leaked_tokens - 1)

        if new_level >= quota:
            # Return time remaining for 1 token to leak out
            return (1 / leak_rate) * (new_level - quota + 1)

        self._counter.set(key, now - (new_level / quota * duration_s))
        return -1


class TokenBucket(Algorithm):
    def __init__(self, counter: QuotaCounter[str, tuple[float, int]]):
        self._counter = counter

    def get_token(self, key, quota: int, duration_s: int) -> ty.Literal[-1] | float:
        now = clock()
        last_token_time, tokens = self._counter.get(key, (now, quota))

        # Refill tokens based on elapsed time
        refill_rate = quota / duration_s  # tokens per second
        elapsed = now - last_token_time
        new_tokens = min(quota, tokens + int(elapsed * refill_rate))

        if new_tokens < 1:
            # Return time remaining for the next token to refill
            return (1 - new_tokens) / refill_rate

        self._counter.set(key, (now, new_tokens - 1))
        return -1


algo_registry.update(
    {
        ThrottleAlgo.FIXED_WINDOW: FixedWindow,
        ThrottleAlgo.SLIDING_WINDOW: SlidingWindow,
        ThrottleAlgo.LEAKY_BUCEKT: LeakyBucket,
        ThrottleAlgo.TOKEN_BUCKET: TokenBucket,
    }
)
