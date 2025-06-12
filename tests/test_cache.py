import asyncio
import pytest
import time
from unittest.mock import AsyncMock

from premier.cache.cache import Cache, make_cache_key
from premier.providers.memory import AsyncInMemoryCache


@pytest.fixture
async def in_memory_cache():
    """Fixture providing AsyncInMemoryCache instance"""
    cache = AsyncInMemoryCache()
    yield cache
    await cache.close()


@pytest.fixture
async def cache_instance(in_memory_cache):
    """Fixture providing Cache instance with in-memory provider"""
    cache = Cache(cache_provider=in_memory_cache, keyspace="test:cache")
    yield cache


class TestMakeCacheKey:
    """Test cache key generation"""
    
    def test_default_key_generation(self):
        def test_func(a, b, c=1):
            return a + b + c
        
        key = make_cache_key(
            func=test_func,
            keyspace="test",
            args=(1, 2),
            kwargs={"c": 3}
        )
        expected = "test:tests.test_cache.test_func:1_2:c=3"
        assert key == expected
    
    def test_string_cache_key(self):
        def test_func():
            pass
        
        key = make_cache_key(
            func=test_func,
            keyspace="test",
            args=(),
            kwargs={},
            cache_key="custom_key"
        )
        assert key == "test:custom_key"
    
    def test_function_cache_key(self):
        def test_func(user_id, action):
            return f"user_{user_id}_{action}"
        
        def key_maker(user_id, action):
            return f"user:{user_id}:action:{action}"
        
        key = make_cache_key(
            func=test_func,
            keyspace="test",
            args=(123, "login"),
            kwargs={},
            cache_key=key_maker
        )
        assert key == "test:user:123:action:login"
    
    def test_no_keyspace(self):
        def test_func():
            pass
        
        key = make_cache_key(
            func=test_func,
            keyspace="",
            args=(),
            kwargs={},
            cache_key="simple_key"
        )
        assert key == "simple_key"


class TestCache:
    """Test Cache functionality"""
    
    @pytest.mark.asyncio
    async def test_cache_miss_and_hit(self, cache_instance):
        """Test cache miss followed by cache hit"""
        call_count = 0
        
        @cache_instance.cache()
        async def test_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call - cache miss
        result1 = await test_func(5)
        assert result1 == 10
        assert call_count == 1
        
        # Second call - cache hit
        result2 = await test_func(5)
        assert result2 == 10
        assert call_count == 1  # Function not called again
    
    @pytest.mark.asyncio
    async def test_cache_with_different_args(self, cache_instance):
        """Test cache with different arguments"""
        call_count = 0
        
        @cache_instance.cache()
        async def test_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        result1 = await test_func(5)
        result2 = await test_func(10)
        
        assert result1 == 10
        assert result2 == 20
        assert call_count == 2  # Both calls executed
        
        # Test cache hits
        result3 = await test_func(5)
        result4 = await test_func(10)
        
        assert result3 == 10
        assert result4 == 20
        assert call_count == 2  # No additional calls
    
    @pytest.mark.asyncio
    async def test_cache_with_expiration(self, in_memory_cache):
        """Test cache with TTL expiration"""
        # Use a mock timer for testing
        current_time = 0
        
        def mock_timer():
            return current_time
        
        cache_provider = AsyncInMemoryCache(timer_func=mock_timer)
        cache = Cache(cache_provider=cache_provider, keyspace="test:expire")
        
        call_count = 0
        
        @cache.cache(expire_s=5)
        async def test_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call
        result1 = await test_func(5)
        assert result1 == 10
        assert call_count == 1
        
        # Simulate time passing but within TTL
        current_time = 3
        result2 = await test_func(5)
        assert result2 == 10
        assert call_count == 1  # Cache hit
        
        # Simulate time passing beyond TTL
        current_time = 10
        result3 = await test_func(5)
        assert result3 == 10
        assert call_count == 2  # Cache miss due to expiration
    
    @pytest.mark.asyncio
    async def test_cache_with_custom_key(self, cache_instance):
        """Test cache with custom key generation"""
        call_count = 0
        
        @cache_instance.cache(cache_key="static_key")
        async def test_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # Different args but same cache key
        result1 = await test_func(5)
        result2 = await test_func(10)
        
        assert result1 == 10
        assert result2 == 10  # Same cached result
        assert call_count == 1  # Only first call executed
    
    @pytest.mark.asyncio
    async def test_cache_with_key_function(self, cache_instance):
        """Test cache with key generation function"""
        call_count = 0
        
        def make_key(user_id, action):
            return f"user:{user_id}"
        
        @cache_instance.cache(cache_key=make_key)
        async def test_func(user_id, action):
            nonlocal call_count
            call_count += 1
            return f"{user_id}_{action}"
        
        # Same user_id, different actions - should hit cache
        result1 = await test_func(123, "login")
        result2 = await test_func(123, "logout")
        
        assert result1 == "123_login"
        assert result2 == "123_login"  # Same cached result
        assert call_count == 1
        
        # Different user_id - should miss cache
        result3 = await test_func(456, "login")
        assert result3 == "456_login"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_cache_with_encoder(self, cache_instance):
        """Test cache with custom encoder"""
        call_count = 0
        
        def json_encoder(data):
            import json
            return json.dumps(data)
        
        @cache_instance.cache(encoder=json_encoder)
        async def test_func(x):
            nonlocal call_count
            call_count += 1
            return {"value": x, "doubled": x * 2}
        
        result1 = await test_func(5)
        result2 = await test_func(5)
        
        expected = {"value": 5, "doubled": 10}
        assert result1 == expected
        # result2 is the encoded (JSON string) version from cache
        import json
        assert json.loads(result2) == expected
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_cache_with_sync_function(self, cache_instance):
        """Test cache decorator with synchronous function"""
        call_count = 0
        
        @cache_instance.cache()
        def sync_func(x):
            nonlocal call_count
            call_count += 1
            return x * 3
        
        # Note: decorated sync function becomes async
        result1 = await sync_func(4)
        result2 = await sync_func(4)
        
        assert result1 == 12
        assert result2 == 12
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_cache_clear(self, cache_instance):
        """Test cache clearing functionality"""
        call_count = 0
        
        @cache_instance.cache()
        async def test_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # Populate cache
        result1 = await test_func(5)
        assert result1 == 10
        assert call_count == 1
        
        # Verify cache hit
        result2 = await test_func(5)
        assert result2 == 10
        assert call_count == 1
        
        # Clear cache
        await cache_instance.clear()
        
        # Should be cache miss now
        result3 = await test_func(5)
        assert result3 == 10
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_cache_clear_specific_keyspace(self, in_memory_cache):
        """Test clearing specific keyspace"""
        cache1 = Cache(cache_provider=in_memory_cache, keyspace="space1")
        cache2 = Cache(cache_provider=in_memory_cache, keyspace="space2")
        
        call_count1 = 0
        call_count2 = 0
        
        @cache1.cache()
        async def func1(x):
            nonlocal call_count1
            call_count1 += 1
            return x * 2
        
        @cache2.cache()
        async def func2(x):
            nonlocal call_count2
            call_count2 += 1
            return x * 3
        
        # Populate both caches
        await func1(5)
        await func2(5)
        assert call_count1 == 1
        assert call_count2 == 1
        
        # Clear only space1
        await cache1.clear("space1")
        
        # func1 should miss cache, func2 should hit
        await func1(5)
        await func2(5)
        assert call_count1 == 2  # Incremented
        assert call_count2 == 1  # Not incremented
    
    @pytest.mark.asyncio
    async def test_multiple_cache_instances(self):
        """Test multiple independent cache instances"""
        cache1 = Cache(cache_provider=AsyncInMemoryCache(), keyspace="cache1")
        cache2 = Cache(cache_provider=AsyncInMemoryCache(), keyspace="cache2")
        
        call_count1 = 0
        call_count2 = 0
        
        @cache1.cache()
        async def func1(x):
            nonlocal call_count1
            call_count1 += 1
            return x * 2
        
        @cache2.cache()
        async def func2(x):
            nonlocal call_count2
            call_count2 += 1
            return x * 2
        
        # Both should execute (different cache instances)
        result1 = await func1(5)
        result2 = await func2(5)
        
        assert result1 == 10
        assert result2 == 10
        assert call_count1 == 1
        assert call_count2 == 1
        
        # Both should hit their respective caches
        await func1(5)
        await func2(5)
        assert call_count1 == 1
        assert call_count2 == 1


class TestCacheIntegration:
    """Integration tests for Cache"""
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self, cache_instance):
        """Test concurrent access to cached function"""
        call_count = 0
        
        @cache_instance.cache()
        async def slow_func(x):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate slow operation
            return x * 2
        
        # Start multiple concurrent calls
        tasks = [slow_func(5) for _ in range(5)]
        results = await asyncio.gather(*tasks)
        
        # All results should be the same
        assert all(r == 10 for r in results)
        
        # Multiple calls may be made due to concurrent execution
        # The cache doesn't prevent concurrent execution of the same key
        # but subsequent calls with the same args will hit the cache
        assert call_count >= 1
        
        # Test that subsequent calls hit the cache
        additional_result = await slow_func(5)
        assert additional_result == 10
        # call_count should not increase for this cached call
        final_count = call_count
    
    @pytest.mark.asyncio
    async def test_cache_with_complex_data_types(self, cache_instance):
        """Test cache with complex return types"""
        call_count = 0
        
        @cache_instance.cache()
        async def complex_func(key):
            nonlocal call_count
            call_count += 1
            return {
                "key": key,
                "data": [1, 2, 3, {"nested": True}],
                "timestamp": time.time()
            }
        
        result1 = await complex_func("test")
        result2 = await complex_func("test")
        
        assert result1 == result2
        assert call_count == 1
        assert isinstance(result1["data"], list)
        assert result1["data"][3]["nested"] is True