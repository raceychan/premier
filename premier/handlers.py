import asyncio
import threading
import time
import typing as ty
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter as clock

from redis.asyncio.client import Redis as AIORedis
from redis.client import Redis
from redis.exceptions import ResponseError as RedisExceptionResponse

from premier._logs import logger
from premier._types import (
    AsyncTaskScheduler,
    AsyncThrottleHandler,
    CountDown,
    P,
    R,
    TaskScheduler,
    ThrottleHandler,
)

RedisClient = ty.TypeVar("RedisClient", Redis, AIORedis)

import queue


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
        self._queues: dict[ty.Hashable, queue.Queue[ty.Any]] = dict()
        self._executors = ThreadPoolExecutor()

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

        task_queue = self._queues.get(key, None)
        if not task_queue:
            task_queue = self._queues[key] = queue.Queue(maxsize=bucket_size)

        def _calculate_delay(key: ty.Hashable, quota: int, duration: int) -> CountDown:
            now = clock()
            last_execution_time = self._counter.get(key, None)
            if not last_execution_time:
                self._counter[key] = now
                return -1
            elapsed = now - last_execution_time
            leak_rate = quota / duration
            delay = (1 / leak_rate) - elapsed
            if delay <= 0:
                self._counter[key] = now
                return -1
            return delay

        def _poll_and_execute(func: ty.Callable[..., None]) -> None:
            while (delay := _calculate_delay(key, quota, duration)) > 0:
                time.sleep(delay)

            args, kwargs = task_queue.get(block=False)
            logger.debug(f"executing, {args=}, {kwargs=}")
            func(*args, **kwargs)

        def _schedule_task(
            func: ty.Callable[P, R], *args: P.args, **kwargs: P.kwargs
        ) -> None:
            try:
                task_queue.put((args, kwargs), block=False)
            except queue.Full:
                raise BucketFullError("Bucket is full. Cannot add more tasks.")

            self._executors.submit(_poll_and_execute, func)

        return _schedule_task

    def clear(self, keyspace: str = ""):
        if not keyspace:
            self._counter.clear()

        keys = [key for key in self._counter if key.startswith(keyspace)]  # type: ignore
        for k in keys:
            self._counter.pop(k, None)

    def close(self) -> None:
        del self._counter


class RedisScriptLoader(ty.Generic[RedisClient]):
    leaky_bucket_incr_lua: ty.ClassVar[
        str
    ] = """
    local waiting_key = KEYS[1] -- The key for tracking waiting tasks
    local bucket_size = ARGV[1] 

    local waiting_tasks = tonumber(redis.call('GET', waiting_key)) or 0

    if waiting_tasks == 0 then
        redis.set(waiting_key, 1)
        return

    if waiting_tasks + 1 > bucket_size then
        return redis.error_reply("Bucket is full. Cannot add more tasks. queue size: " .. waiting_tasks)
    end

    redis.call("INCR", waiting_key)
    """

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
        )
        self.sliding_window = redis.register_script(
            (self._script_path / "sliding_window.lua").read_text()
        )
        self.token_bucket = redis.register_script(
            (self._script_path / "token_bucket.lua").read_text()
        )
        self.leaky_bucket = redis.register_script(
            (self._script_path / "leaky_bucket.lua").read_text()
        )

        self.leaky_bucket_incr = redis.register_script(self.leaky_bucket_incr_lua)
        self.leaky_bucket_decr = redis.register_script(self.leaky_bucket_decr_lua)
        self.clear_keyspace = redis.register_script(self.clear_keyspace_lua)


class RedisHandler(ThrottleHandler):
    def __init__(
        self, redis: "Redis", script_loader: RedisScriptLoader[Redis] | None = None
    ):
        self._redis = redis
        self._script_loader = script_loader or RedisScriptLoader(redis)
        # self._executor = ThreadPoolExecutor(max_workers=5)

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
        arg = f"{keyspace}:*"
        self._script_loader.clear_keyspace(args=[arg])

    def close(self) -> None:
        self._redis.close()

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
        res = await self._script_loader.fixed_window_script(  # type: ignore
            keys=(key,), args=(quota, duration)
        )
        res = ty.cast(CountDown, res)
        return res

    async def sliding_window(self, key: str, quota: int, duration: int) -> CountDown:
        res = await self._script_loader.sliding_window(  # type: ignore
            keys=(key,), args=(quota, duration)
        )
        res = ty.cast(CountDown, res)
        return res

    async def token_bucket(self, key: str, quota: int, duration: int) -> CountDown:
        res = await self._script_loader.token_bucket(  # type: ignore
            keys=(key,), args=(quota, duration)
        )
        res = ty.cast(CountDown, res)
        return res

    def leaky_bucket(
        self, key: str, bucket_size: int, quota: int, duration: int
    ) -> AsyncTaskScheduler:
        """
        [redis-queue](https://redis.io/glossary/redis-queue/)
        -----
        Sometimes, you may want to add a task to the queue but delay its execution until a later time. While Redis does not directly support delayed tasks, you can implement them using sorted sets in combination with regular queues.

        Here’s how you can schedule a task to be added to the queue after a delay:

        Add the task to a sorted set with a score that represents the time when the task should be executed:
        ZADD delayedqueue 1633024800 "Task1"
        Have a consumer that periodically checks the sorted set and moves tasks that are due to the main queue:
        ZRANGEBYSCORE delayedqueue 0 <current_time>
        RPOPLPUSH tempqueue myqueue
        """

        """
        def schedule_task():
            self._queue.put(task) # if queue full raise exception
            while delay := get_delay() > 0:
                time.sleep(delay)
            execute(self._queue.pop(task))
        """

        def _waiting_key(key: ty.Hashable) -> str:
            return f"{key}:waiting_task"

        async def _decrase_level(key: ty.Hashable) -> None:
            wkey = _waiting_key(key)
            await self._script_loader.leaky_bucket_decr(keys=(wkey,), args=tuple())

        async def _incrase_level(key: ty.Hashable, size: int) -> None:
            wkey = _waiting_key(key)
            await self._script_loader.leaky_bucket_incr(keys=(wkey,), args=(size,))

        async def _get_delay(
            key: str, bucket_size: int, quota: int, duration: int
        ) -> float:
            delay = await self._script_loader.leaky_bucket(  # type: ignore
                keys=(key, _waiting_key(key)), args=(bucket_size, quota, duration)
            )
            delay = ty.cast(CountDown, delay)
            return delay

        async def _schedule_task(
            func: ty.Callable[P, ty.Awaitable[R]], *args: P.args, **kwargs: P.kwargs
        ) -> None:

            delay = await _get_delay(key, bucket_size, quota, duration)

            if delay == -1:
                try:  # ignore the result in current implementation
                    _ = await func(*args, **kwargs)
                    return None
                finally:
                    await _decrase_level(key)

            try:
                await _incrase_level(key, bucket_size)
            except RedisExceptionResponse as redis_exc_resp:
                _, wait_num = redis_exc_resp.args[0].split(": ")
                raise BucketFullError(
                    f"Bucket is full. Cannot add more tasks. {wait_num} tasks in queue"
                )

            await asyncio.sleep(delay)
            await _schedule_task(func, *args, **kwargs)

        return _schedule_task  # type: ignore

    async def close(self) -> None:
        await self._redis.aclose()

    async def clear(self, keyspace: str = "") -> None:
        await self._script_loader.clear_keyspace(keys=tuple(), args=(f"{keyspace}:*",))

    @classmethod
    def from_url(cls, url: str):
        redis = AIORedis.from_url(url)  # type: ignore
        return cls(redis=redis)
