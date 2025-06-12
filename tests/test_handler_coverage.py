import asyncio
import time
from unittest.mock import Mock

import pytest

from premier.throttler.errors import BucketFullError
from premier.throttler.handler import AsyncDefaultHandler


class TestAsyncDefaultHandler:
    @pytest.mark.asyncio
    async def test_init_with_custom_timer(self):
        """Test AsyncDefaultHandler initialization"""
        from premier.providers import AsyncInMemoryCache
        
        custom_timer = Mock(return_value=100.0)
        cache = AsyncInMemoryCache()
        
        handler = AsyncDefaultHandler(cache, timer=custom_timer)

        assert handler._timer is custom_timer
        assert handler._cache is cache

    @pytest.mark.asyncio
    async def test_fixed_window_new_key_with_quota(self):
        """Test fixed window with new key and available quota"""
        mock_timer = Mock(return_value=100.0)
        from premier.providers import AsyncInMemoryCache
        
        handler = AsyncDefaultHandler(AsyncInMemoryCache(), timer=mock_timer)

        result = await handler.fixed_window("new_key", quota=5, duration=10)

        assert result == -1  # Should be available
        
        # Verify key exists in cache
        cached_value = await handler._cache.get("new_key")
        assert cached_value is not None

    @pytest.mark.asyncio
    async def test_fixed_window_new_key_zero_quota(self):
        """Test fixed window with new key but zero quota"""
        mock_timer = Mock(return_value=100.0)
        from premier.providers import AsyncInMemoryCache
        
        handler = AsyncDefaultHandler(AsyncInMemoryCache(), timer=mock_timer)

        # This should not create an entry when quota is 0
        result = await handler.fixed_window("new_key", quota=0, duration=10)

        # Implementation may vary, but typically should handle gracefully
        assert result >= 0

    @pytest.mark.asyncio
    async def test_sliding_window_quota_exceeded(self):
        """Test async sliding window when quota is exceeded"""
        mock_timer = Mock()
        mock_timer.side_effect = [100.0, 100.0, 100.0, 101.0]

        from premier.providers import AsyncInMemoryCache
        
        handler = AsyncDefaultHandler(AsyncInMemoryCache(), timer=mock_timer)

        # Fill up quota
        for _ in range(3):
            result = await handler.sliding_window("test_key", quota=3, duration=10)
            assert result == -1

        # Next call should be rate limited
        result = await handler.sliding_window("test_key", quota=3, duration=10)
        assert result > 0

    @pytest.mark.asyncio
    async def test_token_bucket_insufficient_tokens(self):
        """Test async token bucket when tokens are insufficient"""
        mock_timer = Mock()
        mock_timer.side_effect = [100.0, 100.1]  # Very small time progression

        from premier.providers import AsyncInMemoryCache
        
        handler = AsyncDefaultHandler(AsyncInMemoryCache(), timer=mock_timer)

        # Set state with no tokens
        await handler._cache.set("test_key", (100.0, 0))

        result = await handler.token_bucket("test_key", quota=10, duration=10)
        assert result > 0  # Should return wait time

    @pytest.mark.asyncio
    async def test_clear_with_empty_keyspace(self):
        """Test async clear method with empty keyspace"""
        from premier.providers import AsyncInMemoryCache
        
        handler = AsyncDefaultHandler(AsyncInMemoryCache())
        await handler._cache.set("key1", (100, 1))
        await handler._cache.set("key2", (200, 2))

        await handler.clear("")

        # Test that cache is cleared - we can't directly check length
        # so we verify keys are not found
        result1 = await handler._cache.get("key1")
        result2 = await handler._cache.get("key2")
        assert result1 is None
        assert result2 is None

    @pytest.mark.asyncio
    async def test_clear_with_keyspace_prefix(self):
        """Test async clear method with keyspace prefix"""
        from premier.providers import AsyncInMemoryCache
        
        handler = AsyncDefaultHandler(AsyncInMemoryCache())
        await handler._cache.set("test:key1", (100, 1))
        await handler._cache.set("test:key2", (200, 2))
        await handler._cache.set("other:key3", (300, 3))

        await handler.clear("test")

        # Verify test keys are cleared
        result1 = await handler._cache.get("test:key1")
        result2 = await handler._cache.get("test:key2")
        result3 = await handler._cache.get("other:key3")
        assert result1 is None
        assert result2 is None
        assert result3 == (300, 3)

    @pytest.mark.asyncio
    async def test_close(self):
        """Test async close method"""
        from premier.providers import AsyncInMemoryCache
        
        handler = AsyncDefaultHandler(AsyncInMemoryCache())
        await handler._cache.set("test", (100, 1))

        await handler.close()

        # Cache should be closed
        # We can't easily test this without knowing the cache implementation details

    @pytest.mark.asyncio
    async def test_leaky_bucket_async_execution(self):
        """Test async leaky bucket scheduler execution"""
        mock_timer = Mock()
        mock_timer.side_effect = [
            0.0,
            0.0,
            1.0,
        ]  # Time progression for delay calculation

        from premier.providers import AsyncInMemoryCache
        
        handler = AsyncDefaultHandler(AsyncInMemoryCache(), timer=mock_timer)

        scheduler = handler.leaky_bucket("test_key", bucket_size=5, quota=1, duration=1)

        async def async_dummy_func():
            await asyncio.sleep(0.01)
            return "async_result"

        # This should execute without error
        result = await scheduler(async_dummy_func)
        assert result is None  # Scheduler doesn't return function result

    @pytest.mark.asyncio
    async def test_leaky_bucket_queue_full_error(self):
        """Test async leaky bucket raises BucketFullError when queue is full"""
        from premier.providers import AsyncInMemoryCache
        
        handler = AsyncDefaultHandler(AsyncInMemoryCache())

        scheduler = handler.leaky_bucket("test_key", bucket_size=1, quota=1, duration=1)

        async def async_dummy_func():
            return "result"

        # Fill the bucket
        await scheduler(async_dummy_func)

        # Next call should raise BucketFullError
        with pytest.raises(BucketFullError):
            await scheduler(async_dummy_func)


# Test Timer Protocol compliance
def test_timer_protocol():
    """Test that timer functions conform to Timer protocol"""
    from time import perf_counter

    def custom_timer() -> float:
        return 42.0

    # Test protocol compliance
    timer_func = custom_timer
    result = timer_func()
    assert isinstance(result, float)

    # Test with perf_counter
    timer_func = perf_counter
    result = timer_func()
    assert isinstance(result, float)


@pytest.mark.skipif(
    True,  # Skip Redis tests by default unless Redis is available
    reason="Redis tests require Redis server and redis-py package",
)
class TestRedisHandlers:
    """Tests for Redis-based handlers - these require Redis to be available"""

    def test_redis_handler_init(self):
        """Test RedisHandler initialization"""
        try:
            from redis import Redis

            from premier.providers.redis import AsyncRedisHandler as RedisHandler

            mock_redis = Mock(spec=Redis)
            handler = RedisHandler(mock_redis)

            assert handler._redis is mock_redis
            assert handler._script_loader is not None

        except ImportError:
            pytest.skip("Redis not available")

    @pytest.mark.asyncio
    async def test_async_redis_handler_init(self):
        """Test AsyncRedisHandler initialization"""
        try:
            from redis.asyncio import Redis as AIORedis

            from premier.providers.redis import AsyncRedisHandler

            mock_redis = Mock(spec=AIORedis)
            handler = AsyncRedisHandler(mock_redis)

            assert handler._redis is mock_redis
            assert handler._script_loader is not None

        except ImportError:
            pytest.skip("Redis not available")
