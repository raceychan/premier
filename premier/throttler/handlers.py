import threading
import typing as ty
from pathlib import Path
from time import perf_counter as clock

from premier.throttler.interface import (
    CountDown,
    P,
    R,
    ScriptFunc,
    TaskScheduler,
    ThrottleHandler,
)

ThrottlerScript = ScriptFunc[tuple[str], tuple[int, int], CountDown]
LeakyBucketScript = ScriptFunc[tuple[str], tuple[int, int, int], CountDown]


class QuotaExceedsError(Exception):
    time_remains: float

    def __init__(self, quota: int, duration_s: int, time_remains: float):
        msg = f"You exceeds {quota} quota in {duration_s} seconds, available after {time_remains:.2f} s"
        self.time_remains = time_remains
        super().__init__(msg)


class BucketFullError(QuotaExceedsError):
    def __init__(self, msg: str):
        self.msg = msg


class DefaultHandler(ThrottleHandler):
    def __init__(self, counter: dict[ty.Hashable, ty.Any]):
        self._counter = dict[ty.Hashable, ty.Any]()

    def fixed_window(self, key: str, quota: int, duration: int) -> CountDown:
        time, cnt = self._counter.get(key, (clock() + duration, 0))

        if (now := clock()) > time:
            self._counter[key] = (now + duration, 1)
            return -1  # Available now

        if cnt >= quota:
            # Return time remaining until the next window starts
            return time - now

        self._counter[key] = (time, cnt + 1)
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

        self._counter[key] = (sliding_window_start, cnt + 1)
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

        self._counter[key] = (now, new_tokens - 1)
        return -1

    def leaky_bucket(
        self, key: str, bucket_size: int, quota: int, duration: int
    ) -> TaskScheduler:
        def _waiting_key(key: ty.Hashable) -> str:
            return f"{key}:waiting_task"

        def _execute(
            key: ty.Hashable,
            func: ty.Callable[P, R],
            *args: P.args,
            **kwargs: P.kwargs,
        ):
            try:
                func(*args, **kwargs)
            finally:
                self._counter[key] = clock()
                waiting_tasks = self._counter.get(_waiting_key(key), 0)
                if waiting_tasks:
                    self._counter[_waiting_key(key)] = waiting_tasks - 1

        def _calculate_delay(key: ty.Hashable, quota: int, duration: int) -> CountDown:
            now = clock()
            last_execution_time = self._counter.get(key, None)
            if not last_execution_time:
                return -1
            elapsed = now - last_execution_time
            leak_rate = quota / duration
            delay = (1 / leak_rate) - elapsed
            return delay

        def _schedule_task(
            func: ty.Callable[P, R], *args: P.args, **kwargs: P.kwargs
        ) -> None:
            delay = _calculate_delay(key, quota, duration)

            waiting_tasks = self._counter.get(_waiting_key(key), 0)
            if waiting_tasks >= bucket_size:
                raise BucketFullError("Bucket is full. Cannot add more tasks.")

            if delay <= 0:
                _execute(key, func, *args, **kwargs)
            # NOTE: this is wrong, _execute should check for token when executed
            timer = threading.Timer(
                delay, _execute, args=(key, func, *args), kwargs=kwargs
            )
            self._counter[_waiting_key(key)] = waiting_tasks + 1
            timer.start()

        return _schedule_task

    def clear(self, keyspace: str = ""):
        self._counter.clear()


try:
    from redis.client import Redis
except ImportError:
    pass
else:

    class RedisHandler(ThrottleHandler):
        _fixed_window_script: ThrottlerScript
        _sliding_window: ThrottlerScript
        _token_bucket: ThrottlerScript
        _leaky_bucket: LeakyBucketScript
        _leaky_bucket_decr: ScriptFunc[tuple[str], tuple[ty.Any], ty.Any]

        def __init__(self, redis: Redis):
            self._redis = redis
            self._script_path = Path(__file__).parent / "lua"
            self._load_script()

        def _load_script(self):
            self._fixed_window_script = self._redis.register_script(
                (self._script_path / "fixed_window.lua").read_text()
            )  # type: ignore
            self._sliding_window = self._redis.register_script(
                (self._script_path / "sliding_window.lua").read_text()
            )  # type: ignore
            self._token_bucket = self._redis.register_script(
                (self._script_path / "token_bucket.lua").read_text()
            )  # type: ignore
            self._leaky_bucket = self._redis.register_script(
                (self._script_path / "leaky_bucket.lua").read_text()
            )  # type: ignore

            # Decrease the number of waiting tasks after execution
            LUA = """
            local waiting_key = KEYS[1] -- The key for tracking waiting tasks
    
            local waiting_tasks = tonumber(redis.call('GET', waiting_key)) or 0
            if waiting_tasks > 0 then
                redis.call('DECR', waiting_key)
            end
            """
            self._leaky_bucket_decr = self._redis.register_script(LUA)

        def fixed_window(self, key: str, quota: int, duration: int) -> CountDown:
            res = self._fixed_window_script(keys=(key,), args=(quota, duration))
            return res

        def sliding_window(self, key: str, quota: int, duration: int) -> CountDown:
            res = self._sliding_window(keys=(key,), args=(quota, duration))
            return res

        def token_bucket(self, key: str, quota: int, duration: int) -> CountDown:
            res = self._token_bucket(keys=(key,), args=(quota, duration))
            return res

        def leaky_bucket(
            self, key: str, bucket_size: int, quota: int, duration: int
        ) -> TaskScheduler:

            def _waiting_key(key: ty.Hashable) -> str:
                return f"{key}:waiting_task"

            def _decrase_level(key: ty.Hashable) -> None:
                wkey = _waiting_key(key)
                self._leaky_bucket_decr(keys=(wkey,), args=tuple())

            def _execute(
                key: ty.Hashable,
                func: ty.Callable[P, R],
                *args: P.args,
                **kwargs: P.kwargs,
            ):
                try:
                    func(*args, **kwargs)
                finally:
                    _decrase_level(key)

            def _schedule_task(
                func: ty.Callable[P, R], *args: P.args, **kwargs: P.kwargs
            ) -> None:
                try:
                    delay = self._leaky_bucket(
                        keys=(key,), args=(bucket_size, quota, duration)
                    )
                except Exception:
                    raise BucketFullError("Bucket is full. Cannot add more tasks.")

                if delay <= 0:
                    _execute(key, func, *args, **kwargs)

                timer = threading.Timer(
                    delay, _execute, args=(key, func, *args), kwargs=kwargs
                )
                timer.start()

            return _schedule_task

        def clear(self, keyspace: str = "") -> None:
            pass
            # raise NotImplementedError
