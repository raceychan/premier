import asyncio
import time
from typing import Any, Callable, Generic, Hashable, TypeVar

from premier._logs import logger as logger
from premier.providers import AsyncCacheProvider, AsyncQueueProvider
from premier.throttler.errors import BucketFullError, QueueFullError
from premier.throttler.interface import (
    AsyncTaskScheduler,
    AsyncThrottleHandler,
    CountDown,
    P,
    R,
)

TaskArgs = tuple[tuple[Any, ...], dict[Any, Any]]


class Timer:
    def __init__(self, timer_func=time.perf_counter):
        self._timer_func = timer_func

    def __call__(self) -> float:
        return self._timer_func()


class AsyncDefaultHandler(AsyncThrottleHandler):
    def __init__(self, cache: AsyncCacheProvider, timer: Timer | None = None):
        self._cache = cache
        self._queue_registry: dict[Hashable, AsyncQueueProvider[TaskArgs]] = dict()
        self._timer = timer or Timer()

    async def fixed_window(self, key: str, quota: int, duration: int) -> CountDown:
        cached_value = await self._cache.get(key)
        now = self._timer()

        if cached_value is None:
            if quota >= 1:
                await self._cache.set(key, (now + duration, 1))
                return -1
            else:
                await self._cache.set(key, (now + duration, 0))
                return duration

        time_val, cnt = cached_value

        if now > time_val:
            if quota >= 1:
                await self._cache.set(key, (now + duration, 1))
                return -1
            else:
                await self._cache.set(key, (now + duration, 0))
                return duration

        if cnt >= quota:
            return time_val - now

        await self._cache.set(key, (time_val, cnt + 1))
        return -1

    async def sliding_window(self, key: str, quota: int, duration: int) -> CountDown:
        now = self._timer()
        cached_value = await self._cache.get(key)
        time_val, cnt = cached_value or (now, 0)

        elapsed = now - time_val
        complete_durations = int(elapsed // duration)

        if complete_durations >= 1:
            await self._cache.set(key, (now, 1))
            return -1

        window_progress = elapsed % duration
        sliding_window_start = now - window_progress
        adjusted_cnt = cnt - int((elapsed // duration) * quota)
        cnt = max(0, adjusted_cnt)

        if cnt >= quota:
            remains = (duration - window_progress) + (
                (cnt - quota + 1) / quota
            ) * duration
            return remains

        await self._cache.set(key, (sliding_window_start, cnt + 1))
        return -1

    async def token_bucket(self, key: str, quota: int, duration: int) -> CountDown:
        now = self._timer()
        cached_value = await self._cache.get(key)
        last_token_time, tokens = cached_value or (now, quota)

        refill_rate = quota / duration
        elapsed = now - last_token_time
        new_tokens = min(quota, tokens + int(elapsed * refill_rate))

        if new_tokens < 1:
            return (1 - new_tokens) / refill_rate

        await self._cache.set(key, (now, new_tokens - 1))
        return -1

    def leaky_bucket(
        self, key: str, bucket_size: int, quota: int, duration: int
    ) -> AsyncTaskScheduler:
        from premier.providers import AsyncInMemoryQueue

        task_queue = self._queue_registry.get(key, None)
        if not task_queue:
            task_queue = self._queue_registry[key] = AsyncInMemoryQueue[TaskArgs](
                maxsize=bucket_size
            )

        async def _calculate_delay(key: str, quota: int, duration: int) -> CountDown:
            now = self._timer()
            last_execution_time = await self._cache.get(key)
            if not last_execution_time:
                await self._cache.set(key, now)
                return -1
            elapsed = now - last_execution_time
            leak_rate = quota / duration
            delay = (1 / leak_rate) - elapsed
            if delay <= 0:
                await self._cache.set(key, now)
                return -1
            return delay

        async def _poll_and_execute(func: Callable[..., R]) -> None:
            while (delay := await _calculate_delay(key, quota, duration)) > 0:
                await asyncio.sleep(delay)
            item = await task_queue.get(block=False)
            if item is None:
                args, kwargs = (), {}
            else:
                args, kwargs = item
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)

        async def _schedule_task(
            func: Callable[P, R], *args: P.args, **kwargs: P.kwargs
        ) -> None:
            try:
                await task_queue.put((args, kwargs))
            except QueueFullError:
                raise BucketFullError("Bucket is full. Cannot add more tasks.")

            asyncio.create_task(_poll_and_execute(func))

        return _schedule_task

    async def clear(self, keyspace: str = ""):
        await self._cache.clear(keyspace)

    async def close(self) -> None:
        await self._cache.close()


try:
    from redis.asyncio.client import Redis as AIORedis

    from premier.providers.redis import AsyncRedisCacheAdapter

    class AsyncRedisHandler(AsyncDefaultHandler):
        def __init__(self, redis: AIORedis):
            cache = AsyncRedisCacheAdapter(redis)
            super().__init__(cache)
            self._redis = redis

        @classmethod
        def from_url(cls, url: str) -> "AsyncRedisHandler":
            redis = AIORedis.from_url(url)
            return cls(redis)

        async def close(self) -> None:
            await super().close()
            await self._redis.aclose()

except ImportError:
    pass
