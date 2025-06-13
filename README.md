# Premier

A **pluggable API gateway** that transforms any Python web framework into a full-featured API gateway with **caching**, **rate limiting**, **retry logic**, **timeouts**, and **performance monitoring**.

Premier provides a unified, pluggable architecture that makes it easy to add enterprise-grade API gateway functionality to your existing applications with minimal configuration.

## Features

- **Framework Agnostic** - Works with FastAPI, Flask, Django, Starlette, and any Python web framework
- **Pluggable Architecture** - Modular components that can be mixed and matched
- **Smart Caching** - Function result caching with TTL support
- **Rate Limiting** - Multiple algorithms (fixed window, sliding window, token bucket, leaky bucket)
- **Retry Logic** - Configurable retry strategies with backoff
- **Timeouts** - Async function timeout protection
- **Performance Monitoring** - Execution timing and request analytics
- **Multiple Backends** - In-memory and Redis support for scalability
- **Type Safe** - Full type hints and protocol-based interfaces
- **Production Ready** - Comprehensive test coverage and battle-tested

## Quick Start

Transform any web framework into an API gateway in minutes:

```python
import asyncio
from fastapi import FastAPI
from premier import Premier

# Initialize Premier API Gateway
gateway = Premier()

# Create your web application
app = FastAPI()

# Add API Gateway features to your endpoints
@app.get("/users/{user_id}")
@gateway.cache_result(expire_s=300)  # Cache responses
@gateway.fixed_window(quota=100, duration=60)  # Rate limit requests
@gateway.retry(max_attempts=3, wait=1.0)  # Retry failures
@gateway.timeout(5.0)  # Timeout protection
@gateway.timeit()  # Monitor performance
async def get_user(user_id: int):
    # Your existing business logic
    return await fetch_user_from_database(user_id)

# Gateway middleware for request/response processing
@app.middleware("http")
async def gateway_middleware(request, call_next):
    # Add gateway-level processing here
    response = await call_next(request)
    return response

# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown():
    await gateway.close()
```

## Installation

```bash
pip install premier
```

For Redis support (recommended for production):
```bash
pip install premier[redis]
```

## Architecture

Premier transforms your application into an API gateway through its pluggable architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    Premier API Gateway                      │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Caching   │  │Rate Limiting│  │ Monitoring  │        │
│  │   Layer     │  │   Layer     │  │   Layer     │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Retry     │  │  Timeout    │  │ Load Balancer│        │
│  │   Layer     │  │   Layer     │  │   (Future)  │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
├─────────────────────────────────────────────────────────────┤
│              Your Web Framework (FastAPI, Flask, etc.)      │
└─────────────────────────────────────────────────────────────┘
```

## API Gateway Patterns

### 1. Request Caching
Reduce backend load and improve response times:

```python
# Basic response caching
@gateway.cache_result(expire_s=3600)  # 1 hour TTL
async def get_product_catalog():
    return await expensive_database_query()

# User-specific caching
@gateway.cache_result(
    expire_s=1800,
    cache_key=lambda user_id, filters: f"search:{user_id}:{hash(str(filters))}"
)
async def search_products(user_id: int, filters: dict):
    return await personalized_search(user_id, filters)
```

### 2. Rate Limiting & Throttling
Protect your services from abuse and ensure fair usage:

```python
# API endpoint protection
@gateway.fixed_window(quota=1000, duration=3600)  # 1000 requests/hour
async def public_api_endpoint():
    return await process_request()

# User-specific rate limiting
@gateway.sliding_window(
    quota=100, 
    duration=60,
    keymaker=lambda user_id, **kwargs: f"user:{user_id}"
)
async def user_api(user_id: int):
    return await process_user_request(user_id)

# Burst-friendly limits for file uploads
@gateway.token_bucket(quota=10, duration=60)  # 10 uploads/min with bursts
async def upload_file():
    return await handle_file_upload()
```

### 3. Reliability Patterns
Build resilient services that handle failures gracefully:

```python
# Retry transient failures
@gateway.retry(
    max_attempts=3, 
    wait=2.0,
    exceptions=(ConnectionError, TimeoutError)
)
async def external_service_call():
    return await third_party_api()

# Circuit breaker pattern (coming soon)
@gateway.circuit_breaker(failure_threshold=5, recovery_timeout=30)
async def fragile_service():
    return await unreliable_backend()
```

### 4. Request Timeout Management
Prevent cascading failures from slow services:

```python
@gateway.timeout(10.0)  # 10 second timeout
async def slow_database_query():
    return await complex_analytics_query()
```

### 5. Performance Monitoring
Monitor and optimize your API performance:

```python
@gateway.timeit(
    log_threshold=0.1,  # Log requests > 100ms
    with_args=True      # Include request parameters
)
async def monitored_endpoint(request_id: str):
    return await process_request(request_id)
```

## Framework Integration

### FastAPI
```python
from fastapi import FastAPI
from premier import Premier

app = FastAPI()
gateway = Premier()

@app.get("/api/data")
@gateway.cache_result(expire_s=300)
@gateway.fixed_window(quota=100, duration=60)
async def get_data():
    return {"data": "value"}
```

### Flask
```python
from flask import Flask
from premier import Premier

app = Flask(__name__)
gateway = Premier()

@app.route("/api/data")
@gateway.cache_result(expire_s=300)
@gateway.fixed_window(quota=100, duration=60)
def get_data():
    return {"data": "value"}
```

### Django
```python
from django.http import JsonResponse
from premier import Premier

gateway = Premier()

@gateway.cache_result(expire_s=300)
@gateway.fixed_window(quota=100, duration=60)
def api_view(request):
    return JsonResponse({"data": "value"})
```

## Production Deployment

### Distributed Setup with Redis
```python
from premier import Premier
from premier.providers.redis import AsyncRedisCache
from redis.asyncio import Redis

# Redis backend for distributed API gateway
redis_client = Redis.from_url("redis://localhost:6379")
cache_provider = AsyncRedisCache(redis_client)

gateway = Premier(
    cache_provider=cache_provider,
    keyspace="api-gateway"
)
```

### Environment Configuration
```python
import os
from premier import Premier

def create_gateway():
    if os.getenv("REDIS_URL"):
        # Production: Distributed gateway
        from redis.asyncio import Redis
        from premier.providers.redis import AsyncRedisCache
        
        redis_client = Redis.from_url(os.getenv("REDIS_URL"))
        cache_provider = AsyncRedisCache(redis_client)
    else:
        # Development: Single-node gateway
        from premier.providers.memory import AsyncInMemoryCache
        cache_provider = AsyncInMemoryCache()
    
    return Premier(
        cache_provider=cache_provider,
        keyspace=os.getenv("SERVICE_NAME", "api-gateway")
    )
```

### Full-Stack API Gateway Example
```python
from fastapi import FastAPI, HTTPException, Depends
from premier import Premier
import logging

# Initialize API Gateway
gateway = Premier(keyspace="ecommerce-api")
logger = logging.getLogger("api-gateway")

app = FastAPI(title="E-commerce API Gateway")

# Gateway-level middleware
@app.middleware("http")
async def gateway_middleware(request, call_next):
    # Add request ID, logging, etc.
    response = await call_next(request)
    return response

# Product catalog with full gateway features
@app.get("/products/{product_id}")
@gateway.cache_result(expire_s=1800)  # 30min cache
@gateway.fixed_window(quota=1000, duration=3600)  # Rate limiting
@gateway.retry(max_attempts=3, wait=1.0, logger=logger)  # Retry
@gateway.timeout(5.0, logger=logger)  # Timeout
@gateway.timeit(logger=logger)  # Monitoring
async def get_product(product_id: int):
    """Gateway-protected product endpoint"""
    return await fetch_product_details(product_id)

# User-specific endpoints with custom rate limiting
@app.get("/users/{user_id}/orders")
@gateway.cache_result(expire_s=300)
@gateway.sliding_window(
    quota=50, 
    duration=60,
    keymaker=lambda user_id, **kwargs: f"user:{user_id}"
)
async def get_user_orders(user_id: int):
    """User-specific rate limited endpoint"""
    return await fetch_user_orders(user_id)

# Resource cleanup
@app.on_event("shutdown")
async def shutdown_gateway():
    await gateway.close()
```

## Roadmap

Premier is evolving into a comprehensive API gateway solution:

### Current Features ✅
- Request/Response Caching
- Rate Limiting & Throttling  
- Retry Logic & Circuit Breakers
- Timeout Management
- Performance Monitoring
- Multiple Backend Support

### Coming Soon 🚧
- Load Balancing
- Request/Response Transformation
- Authentication & Authorization Plugins
- Request Routing & Path Rewriting
- WebSocket Gateway Support
- GraphQL Gateway Features
- Metrics & Analytics Dashboard

## 📚 API Reference

### Premier Gateway Class

- `Premier(cache_provider=None, throttler=None, cache=None, keyspace="premier")`
- `cache_result(expire_s=None, cache_key=None)` - Response caching
- `fixed_window(quota, duration, keymaker=None)` - Fixed window rate limiting
- `sliding_window(quota, duration, keymaker=None)` - Sliding window rate limiting  
- `token_bucket(quota, duration, keymaker=None)` - Token bucket rate limiting
- `leaky_bucket(bucket_size, quota, duration, keymaker=None)` - Leaky bucket rate limiting
- `retry(max_attempts=3, wait=1.0, exceptions=(Exception,), logger=None)` - Retry logic
- `timeout(seconds, logger=None)` - Request timeout
- `timeit(logger=None, precision=2, log_threshold=0.1, with_args=False)` - Performance monitoring
- `clear_cache(keyspace=None)` - Cache management
- `clear_throttle(keyspace=None)` - Rate limit management
- `close()` - Resource cleanup

## Supported Backends

| Backend | Caching | Rate Limiting | Distributed | Production Ready |
|---------|---------|---------------|-------------|------------------|
| Memory  | ✅      | ✅            | ❌          | Development      |
| Redis   | ✅      | ✅            | ✅          | Production       |

## Requirements

- Python >= 3.10
- Optional: Redis >= 5.0.3 (for distributed deployments)

## License

This project is licensed under the MIT License.

## Contributing

Contributions are welcome! Help us build the most developer-friendly API gateway for Python.

---

*Transform any Python web application into a production-ready API gateway* 🚀