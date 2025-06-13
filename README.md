# Premier

A comprehensive Python library for building robust, production-ready applications with built-in **caching**, **rate limiting**, **retry logic**, **timeouts**, and **performance monitoring**.

Premier follows the facade pattern, providing a unified interface that makes it easy to add reliability patterns to your applications with minimal configuration.

## Features

- **Unified API** - Single facade interface for all functionality
- **Smart Caching** - Function result caching with TTL support
- **Rate Limiting** - Multiple algorithms (fixed window, sliding window, token bucket, leaky bucket)
- **Retry Logic** - Configurable retry strategies with backoff
- **Timeouts** - Async function timeout protection
- **Performance Monitoring** - Execution timing and logging
- **Multiple Backends** - In-memory and Redis support
- **Type Safe** - Full type hints and protocol-based interfaces
- **Well Tested** - Comprehensive test coverage

## Quick Start

```python
import asyncio
from premier import Premier

# Initialize Premier with default in-memory backend
premier = Premier()

# Cache expensive operations
@premier.cache_result(expire_s=300)  # Cache for 5 minutes
async def fetch_user_data(user_id: int):
    # Expensive database or API call
    return {"id": user_id, "name": "John Doe"}

# Add rate limiting
@premier.fixed_window(quota=100, duration=60)  # 100 requests per minute
async def api_endpoint(request_data):
    return await process_request(request_data)

# Implement retry logic
@premier.retry(max_attempts=3, wait=1.0)
async def unreliable_service():
    # Service that might fail occasionally
    return await external_api_call()

# Add timeout protection
@premier.timeout(5.0)  # 5 second timeout
async def slow_operation():
    # Operation that might hang
    return await long_running_task()

# Monitor performance
@premier.timeit()
def cpu_intensive_task(data):
    # Automatically log execution time
    return process_large_dataset(data)

async def main():
    # Use your decorated functions normally
    user = await fetch_user_data(123)
    result = await api_endpoint({"key": "value"})
    
    # Clean up resources
    await premier.close()

asyncio.run(main())
```

## Installation

```bash
pip install premier
```

For Redis support:
```bash
pip install premier[redis]
```

## Core Components

### 1. Caching

Cache function results to improve performance and reduce load on external services.

```python
from premier import Premier

premier = Premier()

# Basic caching
@premier.cache_result(expire_s=3600)  # 1 hour TTL
async def get_exchange_rate(from_currency: str, to_currency: str):
    # Expensive API call
    return await fetch_rate_from_api(from_currency, to_currency)

# Custom cache key
@premier.cache_result(
    expire_s=1800,
    cache_key=lambda user_id, include_details: f"user:{user_id}:{include_details}"
)
async def get_user_profile(user_id: int, include_details: bool = False):
    return await database.fetch_user(user_id, include_details)

# Clear cache when needed
await premier.clear_cache()  # Clear all
await premier.clear_cache("users:*")  # Clear specific pattern
```

### 2. Rate Limiting

Protect your services with multiple rate limiting algorithms.

```python
# Fixed Window - Simple and efficient
@premier.fixed_window(quota=1000, duration=3600)  # 1000 requests per hour
async def api_handler():
    return await process_request()

# Sliding Window - Smooth rate limiting
@premier.sliding_window(quota=100, duration=60)  # 100 requests per minute
async def search_api():
    return await perform_search()

# Token Bucket - Burst-friendly
@premier.token_bucket(quota=50, duration=60)  # 50 requests/min, allows bursts
async def upload_handler():
    return await handle_upload()

# Leaky Bucket - Smooth request processing
@premier.leaky_bucket(bucket_size=10, quota=5, duration=1)  # 5 req/sec, max 10 queued
async def message_processor():
    return await process_message()

# Custom key generation for user-specific limits
@premier.fixed_window(
    quota=100, 
    duration=3600,
    keymaker=lambda user_id, **kwargs: f"user:{user_id}"
)
async def user_api(user_id: int):
    return await process_user_request(user_id)
```

### 3. Retry Logic

Handle transient failures gracefully with intelligent retry strategies.

```python
import logging
from premier import Premier, ILogger

logger = logging.getLogger("myapp")

# Basic retry
@premier.retry(max_attempts=3, wait=1.0)
async def flaky_service():
    return await external_api_call()

# Retry with logging
@premier.retry(
    max_attempts=5,
    wait=2.0,
    exceptions=(ConnectionError, TimeoutError),
    logger=logger
)
async def critical_service():
    return await important_operation()

# Custom wait strategies
@premier.retry(max_attempts=3, wait=[1, 2, 4])  # Custom delays
async def service_with_backoff():
    return await another_service()
```

### 4. Timeouts

Prevent operations from hanging indefinitely.

```python
# Basic timeout
@premier.timeout(10.0)  # 10 second timeout
async def external_api_call():
    return await slow_service()

# Timeout with logging
@premier.timeout(30.0, logger=logger)
async def database_query():
    return await complex_query()
```

### 5. Performance Monitoring

Monitor and log function execution times.

```python
# Basic timing
@premier.timeit()
def data_processing():
    return process_large_file()

# Detailed timing with logging
@premier.timeit(
    logger=logger,
    precision=3,
    log_threshold=0.1,  # Only log if > 100ms
    with_args=True      # Include function arguments
)
async def critical_operation(data_id: str):
    return await process_data(data_id)
```

## Advanced Configuration

### Custom Backends

Use Redis for distributed applications:

```python
from premier import Premier
from premier.providers.redis import AsyncRedisCache
from redis.asyncio import Redis

# Redis backend for distributed caching and rate limiting
redis_client = Redis.from_url("redis://localhost:6379")
cache_provider = AsyncRedisCache(redis_client)

premier = Premier(
    cache_provider=cache_provider,
    keyspace="myapp"
)
```

### Logging Integration

Implement comprehensive logging:

```python
import logging
from premier import Premier, ILogger

# Set up structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class AppLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def info(self, msg: str):
        self.logger.info(msg)
    
    def exception(self, msg: str):
        self.logger.exception(msg)

app_logger = AppLogger("myapp")

# Use logger across all components
@premier.cache_result(expire_s=300)
@premier.retry(max_attempts=3, wait=1.0, logger=app_logger)
@premier.timeout(10.0, logger=app_logger)
@premier.timeit(logger=app_logger)
async def robust_api_call(endpoint: str):
    return await make_request(endpoint)
```

### Combining Decorators

Build robust functions by combining multiple decorators:

```python
@premier.cache_result(expire_s=600)      # Cache results for 10 minutes
@premier.fixed_window(quota=1000, duration=3600)  # Rate limit
@premier.retry(max_attempts=3, wait=2.0, logger=logger)  # Retry on failure
@premier.timeout(15.0, logger=logger)    # Timeout protection
@premier.timeit(logger=logger)           # Performance monitoring
async def mission_critical_service(request_id: str):
    """A service with all reliability patterns applied."""
    return await process_critical_request(request_id)
```

## Architecture

Premier follows the **Facade Pattern**, providing a unified interface over multiple subsystems:

```python
from premier import Premier

# The facade manages all components
premier = Premier(
    cache_provider=custom_cache,  # Shared between cache and throttling
    keyspace="myapp"              # Consistent namespacing
)

# Direct access to underlying components when needed
cache = premier.cache           # Cache instance
throttler = premier.throttler   # Throttler instance
provider = premier.cache_provider  # Cache provider
```

## Testing

Premier is designed to be test-friendly:

```python
import pytest
from premier import Premier
from premier.providers.memory import AsyncInMemoryCache

@pytest.fixture
async def test_premier():
    """Test fixture with in-memory backend."""
    premier = Premier(
        cache_provider=AsyncInMemoryCache(),
        keyspace="test"
    )
    yield premier
    await premier.close()

async def test_caching(test_premier):
    @test_premier.cache_result(expire_s=60)
    async def test_function(value):
        return value * 2
    
    result1 = await test_function(5)
    result2 = await test_function(5)  # From cache
    
    assert result1 == result2 == 10
```

## Production Deployment

### Resource Management

```python
# Proper resource cleanup
async def app_startup():
    global premier
    premier = Premier(
        cache_provider=redis_cache,
        keyspace=config.APP_NAME
    )

async def app_shutdown():
    await premier.close()

# FastAPI example
from fastapi import FastAPI

app = FastAPI()
app.add_event_handler("startup", app_startup)
app.add_event_handler("shutdown", app_shutdown)
```

### Configuration

```python
# Environment-based configuration
import os
from premier import Premier

def create_premier():
    if os.getenv("REDIS_URL"):
        # Production: Use Redis
        from redis.asyncio import Redis
        from premier.providers.redis import AsyncRedisCache
        
        redis_client = Redis.from_url(os.getenv("REDIS_URL"))
        cache_provider = AsyncRedisCache(redis_client)
    else:
        # Development: Use in-memory
        from premier.providers.memory import AsyncInMemoryCache
        cache_provider = AsyncInMemoryCache()
    
    return Premier(
        cache_provider=cache_provider,
        keyspace=os.getenv("APP_NAME", "myapp")
    )
```

## 📚 API Reference

### Premier Class

- `Premier(cache_provider=None, throttler=None, cache=None, keyspace="premier")`
- `cache_result(expire_s=None, cache_key=None)` - Cache decorator
- `fixed_window(quota, duration, keymaker=None)` - Fixed window rate limiting
- `sliding_window(quota, duration, keymaker=None)` - Sliding window rate limiting
- `token_bucket(quota, duration, keymaker=None)` - Token bucket rate limiting
- `leaky_bucket(bucket_size, quota, duration, keymaker=None)` - Leaky bucket rate limiting
- `retry(max_attempts=3, wait=1.0, exceptions=(Exception,), logger=None)` - Retry decorator
- `timeout(seconds, logger=None)` - Timeout decorator
- `timeit(logger=None, precision=2, log_threshold=0.1, with_args=False, show_fino=True)` - Timing decorator
- `clear_cache(keyspace=None)` - Clear cache entries
- `clear_throttle(keyspace=None)` - Clear throttling state
- `close()` - Clean up resources

### ILogger Interface

```python
class ILogger(Protocol):
    def info(self, msg: str): ...
    def exception(self, msg: str): ...
```

## Supported Backends

| Backend | Caching | Rate Limiting | Distributed |
|---------|---------|---------------|-------------|
| Memory  | ✅      | ✅            | ❌          |
| Redis   | ✅      | ✅            | ✅          |

## Rate Limiting Algorithms

| Algorithm      | Use Case | Characteristics |
|----------------|----------|-----------------|
| Fixed Window   | API quotas | Simple, efficient |
| Sliding Window | Smooth limiting | Precise, memory efficient |
| Token Bucket   | Burst tolerance | Allows temporary bursts |
| Leaky Bucket   | Smooth processing | Consistent rate, queuing |

## Requirements

- Python >= 3.10
- Optional: Redis >= 5.0.3 (for distributed backends)

## License

This project is licensed under the MIT License.

## Contributing

Contributions are welcome! Please see our contributing guidelines for details.

---

*Built with ❤️ for building reliable Python applications*