import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter as clock
from typing import Any, Awaitable, Callable, ClassVar, Generic, Hashable, TypeVar, cast



from premier._logs import logger as logger
from premier.errors import BucketFullError, QueueFullError
from premier.interface import (
    AsyncTaskScheduler,
    AsyncThrottleHandler,
    CountDown,
    P,
    R,
    TaskQueue,
    TaskScheduler,
    ThrottleHandler,
)
from premier.task_queue import IQueue

# from redis.exceptions import ResponseError as RedisExceptionResponse

TaskArgs = tuple[tuple[Any, ...], dict[Any, Any]]


class DefaultHandler(ThrottleHandler):
    def __init__(self, counter: dict[str, Any] | None = None):
        self._counter = counter or dict[str, Any]()
        self._queue_registry: dict[Hashable, TaskQueue[TaskArgs]] = dict()
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
        task_queue = self._queue_registry.get(key, None)
        if not task_queue:
            task_queue = self._queue_registry[key] = IQueue[TaskArgs](
                maxsize=bucket_size
            )

        def _calculate_delay(key: str, quota: int, duration: int) -> CountDown:
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

        def _poll_and_execute(func: Callable[..., R]) -> None:
            while (delay := _calculate_delay(key, quota, duration)) > 0:
                time.sleep(delay)
            item = task_queue.get(block=False)
            args, kwargs = item or ((), {})
            _ = func(*args, **kwargs)

        def _schedule_task(
            func: Callable[P, R], *args: P.args, **kwargs: P.kwargs
        ) -> None:
            try:
                task_queue.put((args, kwargs))
            except QueueFullError:
                raise BucketFullError("Bucket is full. Cannot add more tasks.")

            self._executors.submit(_poll_and_execute, func)

        return _schedule_task

    def clear(self, keyspace: str):
        if not keyspace:
            self._counter.clear()

        keys = [key for key in self._counter if key.startswith(keyspace)]
        for k in keys:
            self._counter.pop(k, None)

    def close(self) -> None:
        del self._counter


class AsyncDefaultHandler(AsyncThrottleHandler):
    def __init__(self, counter: dict[str, Any] | None = None):
        self._counter = counter or dict[str, Any]()
        self._queue_registry: dict[Hashable, TaskQueue[TaskArgs]] = dict()
        self._executors = ThreadPoolExecutor()

    async def fixed_window(self, key: str, quota: int, duration: int) -> CountDown:
        if key not in self._counter and quota >= 1:
            self._counter[key] = (clock() + duration, 1)
            return -1

        time, cnt = self._counter[key]

        if (now := clock()) > time:
            self._counter[key] = (now + duration, 1)
            return -1  # Available now

        if cnt >= quota:
            # Return time remaining until the next window starts
            return time - now

        self._counter[key] = (time, cnt + 1)
        return -1  # Token was available, no wait needed

    async def sliding_window(self, key: str, quota: int, duration: int) -> CountDown:
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

    async def token_bucket(self, key: str, quota: int, duration: int) -> CountDown:
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
    ) -> AsyncTaskScheduler:
        task_queue = self._queue_registry.get(key, None)
        if not task_queue:
            task_queue = self._queue_registry[key] = IQueue[TaskArgs](
                maxsize=bucket_size
            )

        def _calculate_delay(key: str, quota: int, duration: int) -> CountDown:
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

        async def _poll_and_execute(func: Callable[..., Awaitable[R]]) -> None:
            while (delay := _calculate_delay(key, quota, duration)) > 0:
                await asyncio.sleep(delay)
            item = task_queue.get(block=False)
            args, kwargs = item or ((), {})
            await func(*args, **kwargs)

        async def _schedule_task(
            func: Callable[P, Awaitable[R]], *args: P.args, **kwargs: P.kwargs
        ) -> None:
            try:
                task_queue.put((args, kwargs))
            except QueueFullError:
                raise BucketFullError("Bucket is full. Cannot add more tasks.")

            await _poll_and_execute(func)

        return _schedule_task

    async def clear(self, keyspace: str = ""):
        if not keyspace:
            self._counter.clear()

        keys = [key for key in self._counter if key.startswith(keyspace)]
        for k in keys:
            self._counter.pop(k, None)

    async def close(self) -> None:
        del self._counter


# ====================== Redis ================================
try:
    from redis.asyncio.client import Redis as AIORedis
    from redis.client import Redis
    from premier.task_queue import RedisQueue, AsyncRedisQueue

    TRedisClient = TypeVar("TRedisClient", Redis, AIORedis)
except ImportError:
    pass
else:

    class RedisScriptLoader(Generic[TRedisClient]):
        clear_keyspace_lua: ClassVar[
            str
        ] = """
        local keys = redis.call('keys', ARGV[1])
        if #keys > 0 then
            return redis.call('del', unpack(keys))
        else
            return 0
        end
        """  # remove all keys that match the pattern, ignore if empty

        def __init__(self, redis: TRedisClient, *, script_path: Path | None = None):
            self._script_path = script_path or (Path(__file__).parent / "lua")
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

            self.clear_keyspace = redis.register_script(self.clear_keyspace_lua)


    class RedisHandler(ThrottleHandler):
        def __init__(
            self, redis: "Redis", script_loader: RedisScriptLoader[Redis] | None = None
        ):
            self._redis = redis
            self._script_loader = script_loader or RedisScriptLoader(redis)
            self._executor = ThreadPoolExecutor()
            self._queue_registry: dict[Hashable, RedisQueue[TaskArgs]] = {}

        def fixed_window(self, key: str, quota: int, duration: int) -> CountDown:
            res = self._script_loader.fixed_window_script(
                keys=(key,), args=(quota, duration)
            )
            res = cast(CountDown, res)
            return res

        def sliding_window(self, key: str, quota: int, duration: int) -> CountDown:
            res = self._script_loader.sliding_window(keys=(key,), args=(quota, duration))
            res = cast(CountDown, res)
            return res

        def token_bucket(self, key: str, quota: int, duration: int) -> CountDown:
            res = self._script_loader.token_bucket(keys=(key,), args=(quota, duration))
            res = cast(CountDown, res)
            return res

        def leaky_bucket(
            self, key: str, bucket_size: int, quota: int, duration: int
        ) -> TaskScheduler:
            task_queue = self._queue_registry.get(key, None)
            if task_queue is None:
                task_queue = self._queue_registry[key] = RedisQueue[TaskArgs](
                    self._redis, name=key, queue_size=bucket_size
                )

            def _calculate_delay(key: str, quota: int, duration: int) -> CountDown:
                delay = self._script_loader.leaky_bucket(keys=(key), args=(quota, duration))
                delay = cast(CountDown, delay)
                return delay

            def _poll_and_execute(func: Callable[..., R]) -> None:
                while (delay := _calculate_delay(key, quota, duration)) > 0:
                    time.sleep(delay)
                item = task_queue.get(block=False)
                args, kwargs = item or ((), {})
                _ = func(*args, **kwargs)

            def _schedule_task(
                func: Callable[P, R], *args: P.args, **kwargs: P.kwargs
            ) -> None:
                try:
                    task_queue.put((args, kwargs))
                except QueueFullError:
                    raise BucketFullError("Bucket is full. Cannot add more tasks.")

                self._executor.submit(_poll_and_execute, func)

            return _schedule_task

        def clear(self, keyspace: str) -> None:
            self._script_loader.clear_keyspace(args=(f"{keyspace}:*",))

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
            self._queue_registry: dict[Hashable, AsyncRedisQueue[TaskArgs]] = {}

        async def fixed_window(self, key: str, quota: int, duration: int) -> CountDown:
            res = await self._script_loader.fixed_window_script(  # type: ignore
                keys=(key,), args=(quota, duration)
            )
            res = cast(CountDown, res)
            return res

        async def sliding_window(self, key: str, quota: int, duration: int) -> CountDown:
            res = await self._script_loader.sliding_window(  # type: ignore
                keys=(key,), args=(quota, duration)
            )
            res = cast(CountDown, res)
            return res

        async def token_bucket(self, key: str, quota: int, duration: int) -> CountDown:
            res = await self._script_loader.token_bucket(  # type: ignore
                keys=(key,), args=(quota, duration)
            )
            res = cast(CountDown, res)
            return res

        def leaky_bucket(
            self, key: str, bucket_size: int, quota: int, duration: int
        ) -> AsyncTaskScheduler:
            task_queue = self._queue_registry.get(key, None)
            if not task_queue:
                task_queue = self._queue_registry[key] = AsyncRedisQueue[TaskArgs](
                    self._redis, name=key, queue_size=bucket_size
                )

            async def _calculate_delay(key: str, quota: int, duration: int) -> CountDown:
                delay = await self._script_loader.leaky_bucket(  # type: ignore
                    keys=(key), args=(quota, duration)
                )

                delay = cast(CountDown, delay)
                return delay

            async def _poll_and_execute(func: Callable[..., Awaitable[R]]) -> None:
                while (delay := await _calculate_delay(key, quota, duration)) > 0:
                    await asyncio.sleep(delay)

                item = await task_queue.get(block=False)
                args, kwargs = item or ((), {})
                _ = await func(*args, **kwargs)

            async def _schedule_task(
                func: Callable[P, Awaitable[R]], *args: P.args, **kwargs: P.kwargs
            ) -> None:

                try:
                    await task_queue.put((args, kwargs))
                except QueueFullError:
                    raise BucketFullError("Bucket is full. Cannot add more tasks.")
                await _poll_and_execute(func)

            return _schedule_task

        async def close(self) -> None:
            await self._redis.aclose()

        async def clear(self, keyspace: str = "") -> None:
            await self._script_loader.clear_keyspace(args=(f"{keyspace}:*",))

        @classmethod
        def from_url(cls, url: str):
            redis = AIORedis.from_url(url)  # type: ignore
            return cls(redis=redis)
