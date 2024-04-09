import threading
import typing as ty
from time import perf_counter as clock

from premier._types import CountDown
from premier.quota_counter import MemoryCounter


class QuotaExceedsError(Exception):
    time_remains: float

    def __init__(self, quota: int, duration_s: int, time_remains: float):
        msg = f"You exceeds {quota} quota in {duration_s} seconds, available after {time_remains:.2f} s"
        self.time_remains = time_remains
        super().__init__(msg)


class BucketFullError(QuotaExceedsError):
    def __init__(self, msg: str):
        self.msg = msg


from abc import ABC, abstractmethod


class ThrottleHandler(ABC):

    @abstractmethod
    def fixed_window(self, key: str, quota: int, duration: int) -> CountDown:
        pass

    @abstractmethod
    def sliding_window(self, key: str, quota: int, duration: int) -> CountDown:
        pass

    @abstractmethod
    def token_bucket(self, key: str, quota: int, duration: int) -> CountDown:
        pass

    @abstractmethod
    def leaky_bucket(self, key: str, bucket_size: int, quota: int, duration: int):
        pass


P = ty.ParamSpec("P")
R = ty.TypeVar("R")


class DefaultHandler(ThrottleHandler):
    def __init__(self):
        self._counter = MemoryCounter[ty.Hashable, ty.Any]()

    def fixed_window(self, key: str, quota: int, duration: int) -> CountDown:
        time, cnt = self._counter.get(key, (clock() + duration, 0))

        if (now := clock()) > time:
            self._counter.set(key, (now + duration, 1))
            return -1  # Available now

        if cnt >= quota:
            # Return time remaining until the next window starts
            return time - now

        self._counter.set(key, (time, cnt + 1))
        return -1  # Token was available, no wait needed

    def sliding_window(self, key: str, quota: int, duration: int) -> CountDown:
        now = clock()
        time, cnt = self._counter.get(key, (now, 0))

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

    def token_bucket(self, key: str, quota: int, duration: int) -> CountDown:
        now = clock()

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

    def leaky_bucket(self, key: str, bucket_size: int, quota: int, duration: int):
        def _waiting_key(key: ty.Hashable) -> str:
            return f"{key}:waiting_task"

        def _execute(
            key: ty.Hashable,
            func: ty.Callable[P, R],
            *args: P.args,
            **kwargs: P.kwargs,
        ):
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                self._counter.set(key, clock())
                waiting_tasks = self._counter.get(_waiting_key(key), 0)
                if waiting_tasks:
                    self._counter.set(_waiting_key(key), waiting_tasks - 1)

        def _calculate_delay(key: ty.Hashable, quota: int, duration: int) -> CountDown:
            now = clock()
            last_execution_time = self._counter.get(key, None)
            if not last_execution_time:
                return -1
            elapsed = now - last_execution_time
            leak_rate = quota / duration
            delay = (1 / leak_rate) - elapsed
            return delay

        def _schedule_task(func: ty.Callable[P, R], *args: P.args, **kwargs: P.kwargs):
            delay = _calculate_delay(key, quota, duration)

            waiting_tasks = self._counter.get(_waiting_key(key), 0)
            if waiting_tasks >= bucket_size:
                raise BucketFullError("Bucket is full. Cannot add more tasks.")

            if delay <= 0:
                res = _execute(key, func, *args, **kwargs)
                return res

            timer = threading.Timer(delay, _execute, (key, func, args, kwargs))
            self._counter.set(_waiting_key(key), waiting_tasks + 1)
            timer.start()

        return _schedule_task
