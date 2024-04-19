import asyncio
import threading
import typing as ty
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter as clock

from redis.asyncio.client import Redis as AIORedis
from redis.client import Redis
from redis.exceptions import ResponseError as RedisExceptionResponse

from premier._types import (
    AsyncTaskScheduler,
    AsyncThrottleHandler,
    CountDown,
    P,
    R,
    ScriptFunc,
    TaskScheduler,
    ThrottleHandler,
)

FixedWindowScript = SlidingWindowScript = TokenBucketScript = ScriptFunc[
    tuple[str], tuple[int, int], CountDown
]
LeakyBucketScript = ScriptFunc[tuple[str, str], tuple[int, int, int], CountDown]


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
    def __init__(self, counter: dict[ty.Hashable, ty.Any] | None = None):
        self._counter = counter or dict[ty.Hashable, ty.Any]()

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
            # TODO: need to get delay
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

            if delay == -1:
                _execute(key, func, *args, **kwargs)

            # NOTE: this is wrong, _execute should check for token when executed
            timer = threading.Timer(
                delay, _execute, args=(key, func, *args), kwargs=kwargs
            )
            self._counter[_waiting_key(key)] = waiting_tasks + 1
            timer.start()

        return _schedule_task

    def clear(self, keyspace: str = ""):
        if not keyspace:
            self._counter.clear()

        keys = [key for key in self._counter if key.startswith(keyspace)]  # type: ignore
        for k in keys:
            self._counter.pop(k, None)


# class AsyncDefaultThrottler(AsyncThrottleHandler):
#     def __init__(self, handler: DefaultHandler):
#         self._hanlder = handler

#     async def fixed_window(self, key: str, quota: int, duration: int) -> CountDown:
#         return self._hanlder.fixed_window(key, quota, duration)

#     async def token_bucket(self, key: str, quota: int, duration: int) -> CountDown:
#         return self._hanlder.token_bucket(key, quota, duration)

#     async def leaky_bucket(  # type: ignore
#         self, key: str, bucket_size: int, quota: int, duration: int
#     ):
#         return self._hanlder.leaky_bucket(key, bucket_size, quota, duration)

#     async def clear(self, keyspace: str = ""):
#         self._hanlder.clear(keyspace)

#     async def sliding_window(self, key: str, quota: int, duration: int) -> CountDown:
#         return self._hanlder.sliding_window(key, quota, duration)


executor = ThreadPoolExecutor(max_workers=5)

RedisClient = ty.TypeVar("RedisClient", Redis, AIORedis)


class RedisScriptLoader(ty.Generic[RedisClient]):
    # fixed_window_script: FixedWindowScript
    # sliding_window: SlidingWindowScript
    # token_bucket: TokenBucketScript
    # leaky_bucket: LeakyBucketScript
    # leaky_bucket_decr: ScriptFunc[tuple[str], tuple[ty.Any], ty.Any]
    # clear_keyspace: ScriptFunc[tuple[ty.Any], tuple[str], None]

    leaky_bucket_decr_lua: ty.ClassVar[
        str
    ] = """
    local waiting_key = KEYS[1] -- The key for tracking waiting tasks

    local waiting_tasks = tonumber(redis.call('GET', waiting_key)) or 0
    if waiting_tasks > 0 then
        redis.call('DECR', waiting_key)
    end
    """

    clear_keyspace_lua: ty.ClassVar[
        str
    ] = """
    return redis.call('del', unpack(redis.call('keys', ARGV[1])))
    """

    def __init__(self, redis: RedisClient, *, script_path: Path | None = None):
        self._script_path = script_path or Path(__file__).parent / "lua"
        self._load_script(redis)

    def _load_script(self, redis: RedisClient):
        self.fixed_window_script = redis.register_script(
            (self._script_path / "fixed_window.lua").read_text()
        )  # type: ignore
        self.sliding_window = redis.register_script(
            (self._script_path / "sliding_window.lua").read_text()
        )  # type: ignore
        self.token_bucket = redis.register_script(
            (self._script_path / "token_bucket.lua").read_text()
        )  # type: ignore
        self.leaky_bucket = redis.register_script(
            (self._script_path / "leaky_bucket.lua").read_text()
        )  # type: ignore

        self.leaky_bucket_decr = redis.register_script(self.leaky_bucket_decr_lua)
        self.clear_keyspace = redis.register_script(self.clear_keyspace_lua)  # type: ignore


class RedisHandler(ThrottleHandler):
    def __init__(
        self, redis: "Redis", script_loader: RedisScriptLoader[Redis] | None = None
    ):
        self._redis = redis
        self._script_loader = script_loader or RedisScriptLoader(redis)

    def fixed_window(self, key: str, quota: int, duration: int) -> CountDown:
        res = self._script_loader.fixed_window_script(
            keys=(key,), args=(quota, duration)
        )
        res = ty.cast(CountDown, res)
        return res

    def sliding_window(self, key: str, quota: int, duration: int) -> CountDown:
        res = self._script_loader.sliding_window(keys=(key,), args=(quota, duration))
        res = ty.cast(CountDown, res)
        return res

    def token_bucket(self, key: str, quota: int, duration: int) -> CountDown:
        res = self._script_loader.token_bucket(keys=(key,), args=(quota, duration))
        res = ty.cast(CountDown, res)
        return res

    def leaky_bucket(
        self, key: str, bucket_size: int, quota: int, duration: int
    ) -> TaskScheduler:

        def _waiting_key(key: ty.Hashable) -> str:
            return f"{key}:waiting_task"

        def _decrase_level(key: ty.Hashable) -> None:
            wkey = _waiting_key(key)
            self._script_loader.leaky_bucket_decr(keys=(wkey,), args=tuple())

        def _get_delay(
            key: str, bucket_size: int, quota: int, duration: int
        ) -> CountDown:
            delay = self._script_loader.leaky_bucket(
                keys=(key, _waiting_key(key)), args=(bucket_size, quota, duration)
            )
            delay = ty.cast(CountDown, delay)
            return delay

        def _schedule_task(
            func: ty.Callable[P, R], *args: P.args, **kwargs: P.kwargs
        ) -> None:

            try:
                delay = _get_delay(key, bucket_size, quota, duration)
            except RedisExceptionResponse as redis_exc_resp:
                _, wait_num = redis_exc_resp.args[0].split(": ")
                raise BucketFullError(
                    f"Bucket is full. Cannot add more tasks. {wait_num} tasks in queue"
                )

            if delay == -1:
                try:  # ignore the result in current implementation
                    _ = func(*args, **kwargs)
                    return None
                finally:
                    _decrase_level(key)
            else:
                timer = threading.Timer(
                    delay, _schedule_task, args=(func, *args), kwargs=kwargs
                )
                timer.start()

        return _schedule_task

    def clear(self, keyspace: str = "") -> None:
        self._script_loader.clear_keyspace(keys=tuple(), args=(f"{keyspace}:*",))

    @classmethod
    def from_url(cls, url: str):
        redis = Redis.from_url(url)  # type: ignore
        return cls(redis=redis)


class AsyncRedisHandler(AsyncThrottleHandler):
    def __init__(
        self,
        redis: AIORedis,
        *,
        script_loader: RedisScriptLoader[AIORedis] | None = None,
    ):
        self._redis = redis
        self._script_loader = script_loader or RedisScriptLoader(redis)
        # self._loop = asyncio.get_event_loop()

    async def fixed_window(self, key: str, quota: int, duration: int) -> CountDown:
        res = await self._script_loader.fixed_window_script(
            keys=(key,), args=(quota, duration)
        )
        res = ty.cast(CountDown, res)
        return res

    async def sliding_window(self, key: str, quota: int, duration: int) -> CountDown:
        res = await self._script_loader.sliding_window(
            keys=(key,), args=(quota, duration)
        )
        res = ty.cast(CountDown, res)
        return res

    async def token_bucket(self, key: str, quota: int, duration: int) -> CountDown:
        res = await self._script_loader.token_bucket(
            keys=(key,), args=(quota, duration)
        )
        res = ty.cast(CountDown, res)
        return res

    def leaky_bucket(
        self, key: str, bucket_size: int, quota: int, duration: int
    ) -> AsyncTaskScheduler:
        def _waiting_key(key: ty.Hashable) -> str:
            return f"{key}:waiting_task"

        async def _decrase_level(key: ty.Hashable) -> None:
            wkey = _waiting_key(key)
            await self._script_loader.leaky_bucket_decr(keys=(wkey,), args=tuple())

        async def _get_delay(
            key: str, bucket_size: int, quota: int, duration: int
        ) -> float:
            delay = await self._script_loader.leaky_bucket(
                keys=(key, _waiting_key(key)), args=(bucket_size, quota, duration)
            )
            delay = ty.cast(CountDown, delay)
            return delay

        async def _schedule_task(
            func: ty.Callable[P, R], *args: P.args, **kwargs: P.kwargs
        ) -> None:

            try:
                delay = await _get_delay(key, bucket_size, quota, duration)
            except RedisExceptionResponse as redis_exc_resp:
                _, wait_num = redis_exc_resp.args[0].split(": ")
                raise BucketFullError(
                    f"Bucket is full. Cannot add more tasks. {wait_num} tasks in queue"
                )

            if delay == -1:
                try:  # ignore the result in current implementation
                    _ = func(*args, **kwargs)
                    return None
                finally:
                    await _decrase_level(key)
            else:
                await asyncio.sleep(delay)
                await _schedule_task(func, *args, **kwargs)

        return _schedule_task  # type: ignore

    async def clear(self, keyspace: str = "") -> None:
        await self._script_loader.clear_keyspace(keys=tuple(), args=(f"{keyspace}:*",))

    @classmethod
    def from_url(cls, url: str):
        redis = AIORedis.from_url(url)  # type: ignore
        return cls(redis=redis)
