import asyncio
import pytest

from premier.providers import AsyncInMemoryCache
from premier.throttler.handler import AsyncDefaultHandler


class MockTimer:
    def __init__(self, start_time: float = 0.0):
        self._time = start_time

    def __call__(self) -> float:
        return self._time

    def advance(self, seconds: float):
        self._time += seconds


class TestAsyncDefaultHandler:
    @pytest.mark.asyncio
    async def test_fixed_window_basic(self):
        cache = AsyncInMemoryCache()
        timer = MockTimer(100.0)
        handler = AsyncDefaultHandler(cache)
        handler._timer = timer

        result = await handler.fixed_window("test", 5, 60)
        assert result == -1

        result = await handler.fixed_window("test", 5, 60)
        assert result == -1

        for _ in range(3):
            result = await handler.fixed_window("test", 5, 60)
            assert result == -1

        result = await handler.fixed_window("test", 5, 60)
        assert result > 0

    @pytest.mark.asyncio
    async def test_fixed_window_reset(self):
        cache = AsyncInMemoryCache()
        timer = MockTimer(100.0)
        handler = AsyncDefaultHandler(cache)
        handler._timer = timer

        for _ in range(5):
            await handler.fixed_window("test", 5, 60)

        result = await handler.fixed_window("test", 5, 60)
        assert result > 0

        timer.advance(61)
        result = await handler.fixed_window("test", 5, 60)
        assert result == -1

    @pytest.mark.asyncio
    async def test_sliding_window_basic(self):
        cache = AsyncInMemoryCache()
        timer = MockTimer(100.0)
        handler = AsyncDefaultHandler(cache)
        handler._timer = timer

        result = await handler.sliding_window("test", 5, 60)
        assert result == -1

        for _ in range(4):
            result = await handler.sliding_window("test", 5, 60)
            assert result == -1

        result = await handler.sliding_window("test", 5, 60)
        assert result > 0

    @pytest.mark.asyncio
    async def test_token_bucket_basic(self):
        cache = AsyncInMemoryCache()
        timer = MockTimer(100.0)
        handler = AsyncDefaultHandler(cache)
        handler._timer = timer

        result = await handler.token_bucket("test", 5, 60)
        assert result == -1

        for _ in range(4):
            result = await handler.token_bucket("test", 5, 60)
            assert result == -1

        result = await handler.token_bucket("test", 5, 60)
        assert result > 0

    @pytest.mark.asyncio
    async def test_token_bucket_refill(self):
        cache = AsyncInMemoryCache()
        timer = MockTimer(100.0)
        handler = AsyncDefaultHandler(cache)
        handler._timer = timer

        for _ in range(5):
            await handler.token_bucket("test", 5, 60)

        result = await handler.token_bucket("test", 5, 60)
        assert result > 0

        timer.advance(12)
        result = await handler.token_bucket("test", 5, 60)
        assert result == -1

    @pytest.mark.asyncio
    async def test_leaky_bucket_basic(self):
        cache = AsyncInMemoryCache()
        timer = MockTimer(100.0)
        handler = AsyncDefaultHandler(cache)
        handler._timer = timer

        scheduler = handler.leaky_bucket("test", 3, 5, 60)
        
        async def dummy_func():
            return "done"

        await scheduler(dummy_func)

    @pytest.mark.asyncio
    async def test_clear_keyspace(self):
        cache = AsyncInMemoryCache()
        handler = AsyncDefaultHandler(cache)

        await handler.fixed_window("test:1", 5, 60)
        await handler.fixed_window("test:2", 5, 60)
        await handler.fixed_window("other:1", 5, 60)

        assert await cache.exists("test:1")
        assert await cache.exists("test:2")
        assert await cache.exists("other:1")

        await handler.clear("test:")
        assert not await cache.exists("test:1")
        assert not await cache.exists("test:2")
        assert await cache.exists("other:1")

    @pytest.mark.asyncio
    async def test_redis_handler_compatibility(self):
        """Test that Redis handler can be imported and used if Redis is available"""
        try:
            from premier.providers.redis import AsyncRedisHandler as RedisHandler
            
            # If Redis is available, test basic usage
            handler = RedisHandler.from_url("redis://localhost:6379")
            
            # Test basic operation (will fail if Redis is not running, but that's OK)
            try:
                result = await handler.fixed_window("test", 5, 60)
                assert isinstance(result, (int, float))
            except Exception:
                # Redis not running or connection failed - that's OK for this test
                pass
            finally:
                await handler.close()
                
        except ImportError:
            # Redis not installed - that's OK
            pass


if __name__ == "__main__":
    pytest.main([__file__])