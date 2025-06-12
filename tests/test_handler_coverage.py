import asyncio
import time
import pytest
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor

from premier.throttler.handler import DefaultHandler, AsyncDefaultHandler, Timer
from premier.throttler.errors import BucketFullError, QueueFullError


class TestDefaultHandler:
    def test_init_with_custom_timer(self):
        """Test DefaultHandler initialization with custom timer and counter"""
        custom_timer = Mock(return_value=100.0)
        custom_counter = {"test": (200.0, 5)}
        
        handler = DefaultHandler(counter=custom_counter, timer=custom_timer)
        
        assert handler._counter is custom_counter
        assert handler._timer is custom_timer
        assert isinstance(handler._executors, ThreadPoolExecutor)
        
    def test_sliding_window_quota_exceeded(self):
        """Test sliding window when quota is exceeded"""
        mock_timer = Mock()
        mock_timer.side_effect = [100.0, 100.0, 100.0, 101.0]  # Simulate time progression
        
        handler = DefaultHandler(timer=mock_timer)
        
        # Fill up quota
        for _ in range(3):
            result = handler.sliding_window("test_key", quota=3, duration=10)
            assert result == -1
        
        # Next call should be rate limited
        result = handler.sliding_window("test_key", quota=3, duration=10)
        assert result > 0  # Should return wait time
        
    def test_sliding_window_time_elapsed(self):
        """Test sliding window with time elapsed causing quota adjustment"""
        mock_timer = Mock()
        mock_timer.side_effect = [0.0, 15.0]  # More than one duration has passed
        
        handler = DefaultHandler(timer=mock_timer)
        
        # Set initial state
        handler._counter["test_key"] = (0.0, 5)  # High count at t=0
        
        # After time elapsed, should allow requests again
        result = handler.sliding_window("test_key", quota=3, duration=10)
        assert result == -1
        
    def test_token_bucket_insufficient_tokens(self):
        """Test token bucket when tokens are insufficient"""
        mock_timer = Mock()
        mock_timer.side_effect = [100.0, 100.5]  # Small time progression
        
        handler = DefaultHandler(timer=mock_timer)
        
        # Set state with no tokens
        handler._counter["test_key"] = (100.0, 0)
        
        result = handler.token_bucket("test_key", quota=10, duration=10)
        assert result > 0  # Should return wait time for next token
        
    def test_clear_with_empty_keyspace(self):
        """Test clear method with empty keyspace clears all"""
        handler = DefaultHandler()
        handler._counter = {"key1": (100, 1), "key2": (200, 2)}
        
        handler.clear("")
        
        assert len(handler._counter) == 0
        
    def test_clear_with_keyspace_prefix(self):
        """Test clear method with keyspace prefix"""
        handler = DefaultHandler()
        handler._counter = {
            "test:key1": (100, 1),
            "test:key2": (200, 2),
            "other:key3": (300, 3)
        }
        
        handler.clear("test")
        
        assert "test:key1" not in handler._counter
        assert "test:key2" not in handler._counter
        assert "other:key3" in handler._counter
        
    def test_close(self):
        """Test close method deletes counter"""
        handler = DefaultHandler()
        handler._counter = {"test": (100, 1)}
        
        handler.close()
        
        # Counter should be deleted
        with pytest.raises(AttributeError):
            _ = handler._counter
            
    def test_leaky_bucket_queue_full_error(self):
        """Test leaky bucket raises BucketFullError when queue is full"""
        handler = DefaultHandler()
        
        scheduler = handler.leaky_bucket("test_key", bucket_size=1, quota=1, duration=1)
        
        def dummy_func():
            return "result"
            
        # Fill the bucket
        scheduler(dummy_func)
        
        # Next call should raise BucketFullError
        with pytest.raises(BucketFullError):
            scheduler(dummy_func)
            
    def test_leaky_bucket_delay_calculation(self):
        """Test leaky bucket delay calculation"""
        mock_timer = Mock()
        mock_timer.side_effect = [0.0, 0.5, 1.5]  # Simulate delay progression
        
        handler = DefaultHandler(timer=mock_timer)
        
        scheduler = handler.leaky_bucket("test_key", bucket_size=5, quota=2, duration=1)
        
        def dummy_func():
            return "result"
            
        # First call should execute immediately
        scheduler(dummy_func)
        
        # Verify timer was called for delay calculation
        assert mock_timer.call_count >= 2


class TestAsyncDefaultHandler:
    @pytest.mark.asyncio
    async def test_init_with_custom_timer(self):
        """Test AsyncDefaultHandler initialization"""
        custom_timer = Mock(return_value=100.0)
        custom_counter = {"test": (200.0, 5)}
        
        handler = AsyncDefaultHandler(counter=custom_counter, timer=custom_timer)
        
        assert handler._counter is custom_counter
        assert handler._timer is custom_timer
        
    @pytest.mark.asyncio
    async def test_fixed_window_new_key_with_quota(self):
        """Test fixed window with new key and available quota"""
        mock_timer = Mock(return_value=100.0)
        handler = AsyncDefaultHandler(timer=mock_timer)
        
        result = await handler.fixed_window("new_key", quota=5, duration=10)
        
        assert result == -1  # Should be available
        assert "new_key" in handler._counter
        
    @pytest.mark.asyncio
    async def test_fixed_window_new_key_zero_quota(self):
        """Test fixed window with new key but zero quota"""
        mock_timer = Mock(return_value=100.0)
        handler = AsyncDefaultHandler(timer=mock_timer)
        
        # This should not create an entry when quota is 0
        result = await handler.fixed_window("new_key", quota=0, duration=10)
        
        # Implementation may vary, but typically should handle gracefully
        assert "new_key" not in handler._counter or result >= 0
        
    @pytest.mark.asyncio
    async def test_sliding_window_quota_exceeded(self):
        """Test async sliding window when quota is exceeded"""
        mock_timer = Mock()
        mock_timer.side_effect = [100.0, 100.0, 100.0, 101.0]
        
        handler = AsyncDefaultHandler(timer=mock_timer)
        
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
        
        handler = AsyncDefaultHandler(timer=mock_timer)
        
        # Set state with no tokens
        handler._counter["test_key"] = (100.0, 0)
        
        result = await handler.token_bucket("test_key", quota=10, duration=10)
        assert result > 0  # Should return wait time
        
    @pytest.mark.asyncio
    async def test_clear_with_empty_keyspace(self):
        """Test async clear method with empty keyspace"""
        handler = AsyncDefaultHandler()
        handler._counter = {"key1": (100, 1), "key2": (200, 2)}
        
        await handler.clear("")
        
        assert len(handler._counter) == 0
        
    @pytest.mark.asyncio
    async def test_clear_with_keyspace_prefix(self):
        """Test async clear method with keyspace prefix"""
        handler = AsyncDefaultHandler()
        handler._counter = {
            "test:key1": (100, 1),
            "test:key2": (200, 2),  
            "other:key3": (300, 3)
        }
        
        await handler.clear("test")
        
        assert "test:key1" not in handler._counter
        assert "test:key2" not in handler._counter
        assert "other:key3" in handler._counter
        
    @pytest.mark.asyncio
    async def test_close(self):
        """Test async close method"""
        handler = AsyncDefaultHandler()
        handler._counter = {"test": (100, 1)}
        
        await handler.close()
        
        # Counter should be deleted
        with pytest.raises(AttributeError):
            _ = handler._counter
            
    @pytest.mark.asyncio
    async def test_leaky_bucket_async_execution(self):
        """Test async leaky bucket scheduler execution"""
        mock_timer = Mock()
        mock_timer.side_effect = [0.0, 0.0, 1.0]  # Time progression for delay calculation
        
        handler = AsyncDefaultHandler(timer=mock_timer)
        
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
        handler = AsyncDefaultHandler()
        
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
    timer_func: Timer = custom_timer
    result = timer_func()
    assert isinstance(result, float)
    
    # Test with perf_counter
    timer_func = perf_counter
    result = timer_func()
    assert isinstance(result, float)


@pytest.mark.skipif(
    True,  # Skip Redis tests by default unless Redis is available
    reason="Redis tests require Redis server and redis-py package"
)
class TestRedisHandlers:
    """Tests for Redis-based handlers - these require Redis to be available"""
    
    def test_redis_handler_init(self):
        """Test RedisHandler initialization"""
        try:
            from redis import Redis
            from premier.throttler.handler import RedisHandler
            
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
            from premier.throttler.handler import AsyncRedisHandler
            
            mock_redis = Mock(spec=AIORedis)
            handler = AsyncRedisHandler(mock_redis)
            
            assert handler._redis is mock_redis
            assert handler._script_loader is not None
            
        except ImportError:
            pytest.skip("Redis not available")