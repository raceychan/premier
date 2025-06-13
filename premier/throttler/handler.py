import time

from premier._logs import logger as logger
from premier.providers import AsyncCacheProvider
from premier.throttler.errors import BucketFullError
from premier.throttler.interface import (
    AsyncThrottleHandler,
    CountDown,
)


class Timer:
    def __init__(self, timer_func=time.perf_counter):
        self._timer_func = timer_func

    def __call__(self) -> float:
        return self._timer_func()


class AsyncDefaultHandler(AsyncThrottleHandler):
    def __init__(self, cache: AsyncCacheProvider, timer: Timer | None = None):
        self._cache = cache
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

    async def leaky_bucket(
        self, key: str, bucket_size: int, quota: int, duration: int
    ) -> CountDown:
        """Simplified leaky bucket implementation without task queue.
        
        Returns -1 if request can proceed immediately, or delay in seconds if bucket is full.
        Raises BucketFullError if the bucket capacity is exceeded.
        """
        now = self._timer()
        bucket_key = f"{key}:bucket"
        
        # Get current bucket state: (last_leak_time, current_count)
        cached_value = await self._cache.get(bucket_key)
        last_leak_time, current_count = cached_value or (now, 0)
        
        # Calculate leak rate (requests per second)
        leak_rate = quota / duration
        elapsed = now - last_leak_time
        
        # Calculate how many tokens have leaked out
        leaked_tokens = int(elapsed * leak_rate)
        current_count = max(0, current_count - leaked_tokens)
        
        # Check if bucket is full
        if current_count >= bucket_size:
            raise BucketFullError("Bucket is full. Cannot add more tasks.")
        
        # Calculate delay until next token can be processed
        if current_count == 0:
            # Bucket is empty, can process immediately
            await self._cache.set(bucket_key, (now, 1))
            return -1
        
        # Add current request to bucket and calculate delay
        new_count = current_count + 1
        await self._cache.set(bucket_key, (now, new_count))
        
        # Delay is based on position in queue
        delay = (new_count - 1) / leak_rate
        return delay

    async def clear(self, keyspace: str = ""):
        await self._cache.clear(keyspace)

    async def close(self) -> None:
        await self._cache.close()


try:
    from redis.asyncio.client import Redis as AIORedis

    from premier.providers.redis import AsyncRedisCache


    class AsyncRedisHandler(AsyncDefaultHandler):
        def __init__(self, cache: AsyncRedisCache):
            super().__init__(cache)
            self._cache = cache

        @classmethod
        def from_url(cls, url: str) -> "AsyncRedisHandler":
            redis = AIORedis.from_url(url)
            cache = AsyncRedisCache(redis)
            return cls(cache)

        async def fixed_window(self, key: str, quota: int, duration: int) -> CountDown:
            """Redis Lua script implementation of fixed window algorithm."""
            return await self._cache.eval_script(
                "fixed_window", 
                keys=[key], 
                args=[str(quota), str(duration)]
            )

        async def sliding_window(self, key: str, quota: int, duration: int) -> CountDown:
            """Redis Lua script implementation of sliding window algorithm."""
            return await self._cache.eval_script(
                "sliding_window", 
                keys=[key], 
                args=[str(quota), str(duration)]
            )

        async def token_bucket(self, key: str, quota: int, duration: int) -> CountDown:
            """Redis Lua script implementation of token bucket algorithm."""
            return await self._cache.eval_script(
                "token_bucket", 
                keys=[key], 
                args=[str(quota), str(duration)]
            )

        async def leaky_bucket(self, key: str, bucket_size: int, quota: int, duration: int) -> CountDown:
            """Redis Lua script implementation of leaky bucket algorithm."""
            bucket_key = f"{key}:bucket"
            result = await self._cache.eval_script(
                "leaky_bucket", 
                keys=[bucket_key], 
                args=[str(bucket_size), str(quota), str(duration)]
            )
            
            # Handle bucket full error code from Lua script
            if result == -999:
                raise BucketFullError("Bucket is full. Cannot add more tasks.")
            
            return result

        async def close(self) -> None:
            await super().close()

except ImportError:
    pass
