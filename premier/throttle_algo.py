import threading
import typing as ty
from collections import deque
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
    time_remains: float

    def __init__(self, quota: int, duration: int, time_remains: float):
        msg = f"You exceeds {quota} quota in {duration} seconds, available after {time_remains:.2f} s"
        self.time_remains = time_remains
        super().__init__(msg)


class BucketFullError(QuotaExceedsError):
    def __init__(self, msg: str):
        self.msg = msg


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
    def __init__(self, counter: QuotaCounter[ty.Hashable, tuple[float, int]]):
        self._counter = counter

    def get_token(
        self, key: ty.Hashable, quota: int, duration_s: int
    ) -> ty.Literal[-1] | float:
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
    def __init__(self, counter: QuotaCounter[ty.Hashable, tuple[float, int]]):
        self._counter = counter

    def get_token(
        self, key: ty.Hashable, quota: int, duration_s: int
    ) -> ty.Literal[-1] | float:
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
    def __init__(self, counter: QuotaCounter[ty.Hashable, tuple[float, float]]):
        self._counter = counter

    def get_token(
        self, key: ty.Hashable, quota: int, duration_s: int
    ) -> ty.Union[ty.Literal[-1], float]:
        now = clock()
        # Get the current level of the bucket (default to 0 if key doesn't exist)
        current_level, last_checked = self._counter.get(key, (0, now))

        # Calculate the leaked amount since last checked
        elapsed = now - last_checked
        leak_rate = quota / duration_s
        leaked_amount = elapsed * leak_rate

        # Update the current level based on the leaked amount
        current_level = max(0, current_level - leaked_amount)

        if current_level < quota:
            # There's room for a token, update the bucket level and timestamp
            self._counter.set(key, (current_level + 1, now))
            return -1  # Token is issued immediately

        # Bucket is full, calculate the time until the next token can be issued
        time_until_next_token = (current_level + 1 - quota) / leak_rate
        return time_until_next_token


class Bucket:
    def __init__(self, counter: QuotaCounter):
        self._counter = counter
        self.lock = threading.Lock()
        self.waiting_tasks = deque()

    def get_last_execution_time(self, key: str):
        last_execution_time = self._counter.get(key, clock())
        return last_execution_time

    def set_last_execution_time(self, key: str, last_execution_time: float):
        self._counter.set(key, last_execution_time)

    def __call__(self, key, func, bucket_size: int, quota: int, duration: int):
        def inner(*args, **kwargs):
            return self.leak(key, func, bucket_size, quota, duration, args, kwargs)

        return inner

    def calculate_delay(self, key: str, leaky_rate: float):
        with self.lock:
            now = clock()
            last_execution_time = self.get_last_execution_time(key)
            return max(0, 1 / leaky_rate - (now - last_execution_time))

    def delayed_execution(self, key, func, args, kwargs):
        """
        with self.acquire_token():
            result = func(*args, **kwargs)
        """
        try:
            result = func(*args, **kwargs)
        finally:
            with self.lock:
                self.set_last_execution_time(key, clock())
                # Ensure the timer is removed from the queue once executed
                if self.waiting_tasks:
                    self.waiting_tasks.popleft()

    def schedule_task(self, key, func, bucket_size: int, delay: float, args, kwargs):
        with self.lock:
            if len(self.waiting_tasks) >= bucket_size:
                raise BucketFullError("Bucket is full. Cannot add more tasks.")
            # Schedule the function execution with necessary_delay
            if delay > 0:
                timer = threading.Timer(
                    delay, self.delayed_execution, (key, func, args, kwargs)
                )
                self.waiting_tasks.append(timer)
                timer.start()
            else:
                self.delayed_execution(key, func, args, kwargs)

    def leak(
        self, key: str, func, bucket_size: int, quota: int, duration: int, args, kwargs
    ):
        # Calculate the necessary delay to maintain the leaky rate
        delay = self.calculate_delay(key, quota / duration)
        self.schedule_task(key, func, bucket_size, delay, args, kwargs)


class TokenBucket(Algorithm):
    def __init__(self, counter: QuotaCounter[ty.Hashable, tuple[float, int]]):
        self._counter = counter

    # TODO: make this async, to support AsyncCounter, such as AsyncRedisCounter
    def get_token(
        self, key: ty.Hashable, quota: int, duration_s: int
    ) -> ty.Literal[-1] | float:
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
        ThrottleAlgo.LEAKY_BUCKET: LeakyBucket,
        ThrottleAlgo.TOKEN_BUCKET: TokenBucket,
    }
)
