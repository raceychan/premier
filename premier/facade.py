from typing import Optional

from premier.cache import Cache
from premier.providers import AsyncCacheProvider, AsyncInMemoryCache
from premier.retry import retry
from premier.throttler import Throttler, ThrottleAlgo, KeyMaker
from premier.throttler.handler import AsyncDefaultHandler
from premier.timer import timeout, timeit, ILogger


class Premier:
    """
    Facade class that provides a unified interface for all Premier functionality.
    
    This class follows the facade pattern to simplify the usage of caching,
    throttling, retry, and timing utilities by providing a single entry point
    with sensible defaults.
    """
    
    def __init__(
        self,
        cache_provider: Optional[AsyncCacheProvider] = None,
        throttler: Optional[Throttler] = None,
        cache: Optional[Cache] = None,
        keyspace: str = "premier",
    ):
        """
        Initialize Premier facade with optional components.
        
        Args:
            cache_provider: Cache provider for both caching and throttling
            throttler: Custom throttler instance
            cache: Custom cache instance  
            keyspace: Default keyspace prefix for all operations
        """
        self._keyspace = keyspace
        
        # Initialize cache provider (shared between cache and throttler)
        self._cache_provider = cache_provider or AsyncInMemoryCache()
        
        # Initialize cache
        self._cache = cache or Cache(
            cache_provider=self._cache_provider,
            keyspace=f"{keyspace}:cache"
        )
        
        # Initialize throttler
        if throttler:
            self._throttler = throttler
        else:
            handler = AsyncDefaultHandler(self._cache_provider)
            self._throttler = Throttler(
                handler=handler,
                keyspace=f"{keyspace}:throttler"
            )
    
    @property
    def cache(self) -> Cache:
        """Get the cache instance."""
        return self._cache
    
    @property
    def throttler(self) -> Throttler:
        """Get the throttler instance."""
        return self._throttler
    
    @property
    def cache_provider(self) -> AsyncCacheProvider:
        """Get the cache provider instance."""
        return self._cache_provider
    
    # Cache methods
    def cache_result(self, expire_s: Optional[int] = None, cache_key: Optional[str] = None):
        """
        Cache decorator for function results.
        
        Args:
            expire_s: Expiration time in seconds
            cache_key: Custom cache key
        """
        return self._cache.cache(expire_s=expire_s, cache_key=cache_key)
    
    async def clear_cache(self, keyspace: Optional[str] = None):
        """Clear cache entries."""
        await self._cache.clear(keyspace)
    
    # Throttling methods
    def fixed_window(self, quota: int, duration: int, keymaker: Optional[KeyMaker] = None):
        """Fixed window rate limiting decorator."""
        return self._throttler.fixed_window(quota, duration, keymaker)
    
    def sliding_window(self, quota: int, duration: int, keymaker: Optional[KeyMaker] = None):
        """Sliding window rate limiting decorator."""
        return self._throttler.sliding_window(quota, duration, keymaker)
    
    def token_bucket(self, quota: int, duration: int, keymaker: Optional[KeyMaker] = None):
        """Token bucket rate limiting decorator."""
        return self._throttler.token_bucket(quota, duration, keymaker)
    
    def leaky_bucket(self, bucket_size: int, quota: int, duration: int, keymaker: Optional[KeyMaker] = None):
        """Leaky bucket rate limiting decorator."""
        return self._throttler.leaky_bucket(quota, bucket_size, duration, keymaker)
    
    def throttle(
        self,
        algo: ThrottleAlgo,
        quota: int,
        duration: int,
        keymaker: Optional[KeyMaker] = None,
        bucket_size: int = -1,
    ):
        """
        Generic throttle decorator.
        
        Args:
            algo: Throttling algorithm to use
            quota: Number of requests allowed
            duration: Time window in seconds
            keymaker: Function to generate custom keys
            bucket_size: Bucket size for leaky bucket algorithm
        """
        return self._throttler.throttle(algo, quota, duration, keymaker, bucket_size)
    
    async def clear_throttle(self, keyspace: Optional[str] = None):
        """Clear throttling state."""
        await self._throttler.clear(keyspace)
    
    # Retry methods
    @staticmethod
    def retry(
        max_attempts: int = 3,
        wait: float = 1.0,
        exceptions: tuple = (Exception,),
        logger: Optional[ILogger] = None,
    ):
        """
        Retry decorator for functions.
        
        Args:
            max_attempts: Maximum number of retry attempts
            wait: Wait strategy (seconds)
            exceptions: Exceptions to retry on
            logger: Logger to log retry attempts
        """
        return retry(
            max_attempts=max_attempts,
            wait=wait,
            exceptions=exceptions,
            logger=logger,
        )
    
    # Timing methods
    @staticmethod
    def timeout(seconds: float, logger: Optional[ILogger] = None):
        """
        Timeout decorator for functions.
        
        Args:
            seconds: Timeout duration in seconds
            logger: Logger to log timeout events
        """
        return timeout(seconds, logger=logger)
    
    @staticmethod
    def timeit(
        logger: Optional[ILogger] = None,
        precision: int = 2,
        log_threshold: float = 0.1,
        with_args: bool = False,
        show_fino: bool = True,
    ):
        """
        Timing decorator for functions.
        
        Args:
            logger: Logger instance for timing output
            precision: Decimal precision for timing
            log_threshold: Minimum time to log
            with_args: Include function arguments in log
            show_fino: Show file info in log
        """
        return timeit(
            logger=logger,
            precision=precision,
            log_threshold=log_threshold,
            with_args=with_args,
            show_fino=show_fino,
        )
    
    async def close(self):
        """Close all resources."""
        await self._cache_provider.close()