import threading
import typing as ty
from time import perf_counter as clock

from premier._types import (
    AnySyncFunc,
    CountDown,
    LBThrottleInfo,
    QuotaCounter,
    ThrottleAlgo,
    ThrottleHandler,
)


class QuotaExceedsError(Exception):
    time_remains: float

    def __init__(self, quota: int, duration_s: int, time_remains: float):
        msg = f"You exceeds {quota} quota in {duration_s} seconds, available after {time_remains:.2f} s"
        self.time_remains = time_remains
        super().__init__(msg)


class BucketFullError(QuotaExceedsError):
    def __init__(self, msg: str):
        self.msg = msg


class _HandlerRegistry:
    def __init__(self):
        self._registry: dict[ThrottleAlgo | str, type[ThrottleHandler]] = dict()

    def __getitem__(self, _k: ThrottleAlgo):
        return self._registry[_k]

    def register(self, algo_id: ThrottleAlgo | str):
        def cls_receiver(cls: type[ThrottleHandler]) -> type[ThrottleHandler]:
            self._registry[algo_id] = cls
            return cls

        return cls_receiver

    def update(self, data: dict[ThrottleAlgo | str, type[ThrottleHandler]]):
        self._registry.update(data)

    def get(self, k: ThrottleAlgo, default: ty.Any):
        return self._registry.get(k, default)


algo_registry = _HandlerRegistry()


@algo_registry.register(ThrottleAlgo.FIXED_WINDOW)
class FixedWindowHandler(ThrottleHandler):
    def acquire(self, key: ty.Hashable) -> CountDown:
        quota, duration = self._info.quota, self._info.duration

        time, cnt = self._counter.get(key, (clock() + duration, 0))

        if (now := clock()) > time:
            self._counter.set(key, (now + duration, 1))
            return -1  # Available now

        if cnt >= quota:
            # Return time remaining until the next window starts
            return time - now

        self._counter.set(key, (time, cnt + 1))
        return -1  # Token was available, no wait needed


@algo_registry.register(ThrottleAlgo.SLIDING_WINDOW)
class SlidingWindow(ThrottleHandler):
    def acquire(self, key: ty.Hashable) -> CountDown:
        now = clock()
        time, cnt = self._counter.get(key, (now, 0))
        quota, duration = self._info.quota, self._info.duration

        # Calculate remaining quota and adjust based on time passed
        elapsed = now - time
        window_progress = elapsed % duration
        sliding_window_start = now - window_progress
        adjusted_cnt = cnt - int((elapsed // duration) * quota)
        cnt = max(0, adjusted_cnt)

        if cnt >= quota:
            # Return the time until the window slides enough for one token
            remains = (duration - window_progress) + (
                (cnt - quota + 1) / quota
            ) * duration
            return remains

        self._counter.set(key, (sliding_window_start, cnt + 1))
        return -1


@algo_registry.register(ThrottleAlgo.TOKEN_BUCKET)
class TokenBucketHandler(ThrottleHandler):
    # TODO: make this async, to support AsyncCounter, such as AsyncRedisCounter
    def acquire(self, key: ty.Hashable) -> CountDown:
        now = clock()
        quota, duration = self._info.quota, self._info.duration

        last_token_time, tokens = self._counter.get(key, (now, quota))

        # Refill tokens based on elapsed time
        refill_rate = quota / duration  # tokens per second
        elapsed = now - last_token_time
        new_tokens = min(quota, tokens + int(elapsed * refill_rate))

        if new_tokens < 1:
            # Return time remaining for the next token to refill
            return (1 - new_tokens) / refill_rate

        self._counter.set(key, (now, new_tokens - 1))
        return -1


class LeakyBucketHandler(ThrottleHandler):
    def __init__(
        self,
        counter: QuotaCounter[ty.Any, ty.Any],
        lock: threading.Lock,
        throttle_info: LBThrottleInfo,
    ):
        super().__init__(counter, lock, throttle_info)
        self._bucket_size = throttle_info.bucket_size
        self._leaky_rate = throttle_info.quota / throttle_info.duration

    def waiting_key(self, key: ty.Hashable) -> str:
        return f"{key}:waiting_task"

    def _execute(
        self,
        key: ty.Hashable,
        func: AnySyncFunc,
        args: tuple[ty.Any | object, ...],
        kwargs: dict[ty.Any, ty.Any],
    ):
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            with self._lock:
                self._counter.set(key, clock())
                waiting_tasks = self._counter.get(self.waiting_key(key), 0)
                if waiting_tasks:
                    self._counter.set(self.waiting_key(key), waiting_tasks - 1)

    def acquire(self, key: ty.Hashable) -> CountDown:
        now = clock()
        last_execution_time = self._counter.get(key, None)
        if not last_execution_time:
            return -1
        elapsed = now - last_execution_time
        delay = (1 / self._leaky_rate) - elapsed
        return delay

    def schedule_task(
        self,
        key: ty.Hashable,
        func: AnySyncFunc,
        args: tuple[ty.Any | object, ...],
        kwargs: dict[ty.Any, ty.Any],
    ):
        with self._lock:
            delay = self.acquire(key)

        waiting_tasks = self._counter.get(self.waiting_key(key), 0)
        if waiting_tasks >= self._bucket_size:
            raise BucketFullError("Bucket is full. Cannot add more tasks.")

        if delay <= 0:
            res = self._execute(key, func, args, kwargs)
            return res

        timer = threading.Timer(delay, self._execute, (key, func, args, kwargs))
        self._counter.set(self.waiting_key(key), waiting_tasks + 1)
        timer.start()
        # instead of value, return a future
