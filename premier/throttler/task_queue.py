from premier.providers import AsyncInMemoryQueue

# Main queue implementation - async only
AsyncQueue = AsyncInMemoryQueue

# For backward compatibility
IQueue = AsyncInMemoryQueue

# Redis queue
try:
    from premier.providers.redis import AsyncRedisQueueAdapter
    RedisQueue = AsyncRedisQueueAdapter
    AsyncRedisQueue = AsyncRedisQueueAdapter
except ImportError:
    pass