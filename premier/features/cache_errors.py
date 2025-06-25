from premier.errors import PremierError


class CacheError(PremierError):
    """Base class for cache-related errors."""
    pass


class CacheKeyError(CacheError):
    """Raised when there's an issue with cache key generation."""
    
    def __init__(self, key: str, message: str = ""):
        self.key = key
        super().__init__(message or f"Invalid cache key: {key}")


class CacheProviderError(CacheError):
    """Raised when there's an issue with the cache provider."""
    pass


class CacheSerializationError(CacheError):
    """Raised when encoding/decoding cache values fails."""
    
    def __init__(self, value, message: str = ""):
        self.value = value
        super().__init__(message or f"Failed to serialize cache value: {value}")


class CacheConnectionError(CacheError):
    """Raised when cache provider connection fails."""
    pass