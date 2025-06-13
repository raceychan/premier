import asyncio
import pytest
from unittest.mock import AsyncMock

from premier import Premier
from premier.providers.memory import AsyncInMemoryCache
from premier.throttler.errors import QuotaExceedsError


class TestPremierFacade:
    
    @pytest.fixture
    def premier(self):
        """Create a Premier instance for testing."""
        return Premier(keyspace="test")
    
    @pytest.mark.asyncio
    async def test_premier_initialization(self, premier):
        """Test Premier facade initialization."""
        assert premier.cache is not None
        assert premier.throttler is not None
        assert premier.cache_provider is not None
        assert isinstance(premier.cache_provider, AsyncInMemoryCache)
    
    @pytest.mark.asyncio
    async def test_premier_with_custom_cache_provider(self):
        """Test Premier with custom cache provider."""
        custom_provider = AsyncInMemoryCache()
        premier = Premier(cache_provider=custom_provider)
        
        assert premier.cache_provider is custom_provider
    
    @pytest.mark.asyncio
    async def test_cache_functionality(self, premier):
        """Test caching functionality through facade."""
        
        @premier.cache_result(expire_s=60)
        async def expensive_function(x):
            return x * 2
        
        # First call should execute the function
        result1 = await expensive_function(5)
        assert result1 == 10
        
        # Second call should return cached result
        result2 = await expensive_function(5)
        assert result2 == 10
    
    @pytest.mark.asyncio
    async def test_throttling_functionality(self, premier):
        """Test throttling functionality through facade."""
        
        @premier.fixed_window(quota=2, duration=1)
        async def throttled_function():
            return "success"
        
        # First two calls should succeed
        result1 = await throttled_function()
        assert result1 == "success"
        
        result2 = await throttled_function()
        assert result2 == "success"
        
        # Third call should raise QuotaExceedsError
        with pytest.raises(QuotaExceedsError):
            await throttled_function()
    
    @pytest.mark.asyncio
    async def test_leaky_bucket_functionality(self, premier):
        """Test leaky bucket functionality through facade."""
        
        @premier.leaky_bucket(bucket_size=2, quota=1, duration=1)
        async def leaky_function():
            return "success"
        
        # First call should succeed immediately
        result = await leaky_function()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_functionality(self, premier):
        """Test retry functionality through facade."""
        call_count = 0
        
        @premier.retry(max_attempts=3, wait=0.1)
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"
        
        result = await flaky_function()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_with_logger(self, premier):
        """Test retry functionality with logger."""
        from unittest.mock import Mock
        
        logger_mock = Mock()
        logger_mock.info = Mock()
        logger_mock.exception = Mock()
        
        call_count = 0
        
        @premier.retry(max_attempts=3, wait=0.1, logger=logger_mock)
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"
        
        result = await flaky_function()
        assert result == "success"
        assert call_count == 3
        
        # Verify logger was called
        assert logger_mock.info.called
    
    def test_timeout_functionality(self, premier):
        """Test timeout functionality through facade."""
        
        @premier.timeout(0.1)
        async def slow_function():
            await asyncio.sleep(0.2)
            return "too slow"
        
        async def run_test():
            with pytest.raises(asyncio.TimeoutError):
                await slow_function()
        
        asyncio.run(run_test())
    
    def test_timeit_functionality(self, premier):
        """Test timing functionality through facade."""
        
        @premier.timeit()
        def timed_function():
            return "timed"
        
        result = timed_function()
        assert result == "timed"
    
    @pytest.mark.asyncio
    async def test_clear_cache(self, premier):
        """Test cache clearing through facade."""
        
        @premier.cache_result()
        async def cached_function(x):
            return x * 2
        
        # Cache a result
        await cached_function(5)
        
        # Clear cache
        await premier.clear_cache()
        
        # Should work without issues
        result = await cached_function(5)
        assert result == 10
    
    @pytest.mark.asyncio
    async def test_clear_throttle(self, premier):
        """Test throttle clearing through facade."""
        
        @premier.fixed_window(quota=1, duration=10)
        async def throttled_function():
            return "success"
        
        # Use up the quota
        await throttled_function()
        
        # Clear throttle state
        await premier.clear_throttle()
        
        # Should be able to call again
        result = await throttled_function()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_generic_throttle_method(self, premier):
        """Test generic throttle method through facade."""
        from premier.throttler import ThrottleAlgo
        
        @premier.throttle(
            algo=ThrottleAlgo.TOKEN_BUCKET,
            quota=2,
            duration=1
        )
        async def throttled_function():
            return "success"
        
        result = await throttled_function()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_close_resources(self, premier):
        """Test resource cleanup through facade."""
        await premier.close()
        
        # After closing, the cache provider should be closed
        # This is mainly to ensure no exceptions are raised
        assert True