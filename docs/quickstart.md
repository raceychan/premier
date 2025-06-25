# Quick Start Guide

This guide will help you get started with Premier in just a few minutes.

## Choose Your Integration Mode

Premier supports three different integration modes:

1. **[Plugin Mode](#plugin-mode)** - Recommended for wrapping existing ASGI applications
2. **[Standalone Mode](#standalone-mode)** - For creating a dedicated API gateway
3. **[Decorator Mode](#decorator-mode)** - For adding features to individual functions

## Plugin Mode

Perfect for adding gateway features to existing FastAPI, Django, or other ASGI applications.

### Step 1: Create Your ASGI Application

```python
# app.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/api/users/{user_id}")
async def get_user(user_id: int):
    return {"id": user_id, "name": f"User {user_id}"}

@app.get("/api/posts")
async def get_posts():
    return [{"id": 1, "title": "Hello World"}]
```

### Step 2: Create Gateway Configuration

```yaml
# gateway.yaml
premier:
  keyspace: "my-api"
  
  paths:
    - pattern: "/api/users/*"
      features:
        cache:
          expire_s: 300
        rate_limit:
          quota: 100
          duration: 60
        timeout:
          seconds: 5.0
        
    - pattern: "/api/posts"
      features:
        cache:
          expire_s: 600
        rate_limit:
          quota: 200
          duration: 60
```

### Step 3: Wrap Your Application

```python
# gateway.py
from premier.asgi import ASGIGateway, GatewayConfig
from .app import app

# Load configuration and wrap your app
config = GatewayConfig.from_file("gateway.yaml")
gateway_app = ASGIGateway(config=config, app=app)
```

### Step 4: Run Your Gateway

```bash
uvicorn gateway:gateway_app --reload
```

That's it! Your application now has caching, rate limiting, and timeout protection.

## Standalone Mode

Create a dedicated API gateway that forwards requests to backend services.

### Step 1: Create Gateway Configuration

```yaml
# gateway.yaml
premier:
  keyspace: "gateway"
  servers:
    - "http://backend1:8000"
    - "http://backend2:8000"
  
  paths:
    - pattern: "/api/*"
      features:
        cache:
          expire_s: 300
        rate_limit:
          quota: 1000
          duration: 60
        timeout:
          seconds: 10.0
        retry:
          max_attempts: 3
          wait: 1.0
```

### Step 2: Create Gateway Service

```python
# gateway.py
from premier.asgi import ASGIGateway, GatewayConfig

config = GatewayConfig.from_file("gateway.yaml")
app = ASGIGateway(config)
```

### Step 3: Run Your Gateway

```bash
uvicorn gateway:app
```

The gateway will load balance requests between your backend servers with full gateway features.

## Decorator Mode

Add Premier features directly to individual functions.

### Step 1: Use Premier Decorators

```python
from premier.features.retry import retry
from premier.features.timer import timeit, timeout
from premier.features.cache import cache

@cache(expire_s=300)
@retry(max_attempts=3, wait=1.0)
@timeout(seconds=5.0)
@timeit(log_threshold=0.1)
async def fetch_user_data(user_id: int):
    # Your function with retry, timeout, caching, and timing
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/users/{user_id}")
        return response.json()
```

### Step 2: Use Your Functions

```python
# Automatic retry on failure, caching, timeout protection
user_data = await fetch_user_data(123)
```

## Accessing the Web Dashboard

Premier includes a built-in web dashboard for monitoring and configuration.

Add this to your configuration:

```yaml
premier:
  dashboard:
    enabled: true
    path: "/premier/dashboard"
```

Then visit `http://localhost:8000/premier/dashboard` to see:

- Real-time request metrics
- Cache statistics
- Rate limiting status
- Configuration management
- Performance analytics

## Production Configuration

For production deployments, consider using Redis for distributed caching:

```python
from premier.asgi import ASGIGateway, GatewayConfig
from premier.providers.redis import AsyncRedisCache
from redis.asyncio import Redis

# Redis backend for distributed caching
redis_client = Redis.from_url("redis://localhost:6379")
cache_provider = AsyncRedisCache(redis_client)

# Load configuration
config = GatewayConfig.from_file("production.yaml")

# Create production gateway
app = ASGIGateway(config, app=your_app, cache_provider=cache_provider)
```

## Next Steps

- **[Configuration Guide](configuration.md)** - Learn about all configuration options
- **[Web Dashboard](web-gui.md)** - Explore the monitoring interface
- **[Examples](examples.md)** - See complete working examples