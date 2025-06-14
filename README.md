# Premier

A production-ready ASGI API Gateway that transforms any Python web application into a full-featured API gateway with caching, rate limiting, retry logic, timeouts, and performance monitoring.

## Features

Premier provides enterprise-grade API gateway functionality with:

- **Response Caching** - Smart caching with TTL and custom cache keys
- **Rate Limiting** - Multiple algorithms (fixed/sliding window, token/leaky bucket), works with distributed app
- **Retry Logic** - Configurable retry strategies with exponential backoff
- **Request Timeouts** - Per-path timeout protection
- **Performance Monitoring** - Request timing and analytics
- **Path-Based Policies** - Different features per route with regex matching
- **Backend Forwarding** - Route requests to multiple backend services
- **YAML Configuration** - Declarative configuration with namespace support
- **Type Safety** - Full type hints and structured configuration

... and more

## Why Premier

Premier is designed for **simplicity and accessibility** - perfect for simple applications that need API gateway functionality without introducing complex tech stacks like Kong, Ambassador, or Istio.

**Key advantages:**
- **Zero Code Changes** - Wrap existing ASGI apps without modifications
- **Simple Setup** - Single dependency, no external services required
- **Dual Mode Operation** - Plugin for existing apps OR standalone gateway
- **Python Native** - Built for Python developers, integrates seamlessly
- **Lightweight** - Minimal overhead, maximum performance
- **Hot Reloadable** - Update configurations without restarts

## Quick Start

### Plugin Mode (Recommended)

Wrap your existing ASGI application:

```python
from premier.asgi import ASGIGateway, GatewayConfig
from fastapi import FastAPI

# Your existing app - no changes needed
app = FastAPI()

@app.get("/api/users/{user_id}")
async def get_user(user_id: int):
    return await fetch_user_from_database(user_id)

# Load configuration and wrap app
config = GatewayConfig.from_file("gateway.yaml")
gateway = ASGIGateway(config, app=app)
```

### Standalone Mode

Use as a standalone gateway:

```python
from premier.asgi import ASGIGateway, GatewayConfig

config = GatewayConfig.from_file("gateway.yaml")
gateway = ASGIGateway(config, servers=["http://backend:8000"])
```

```bash
uvicorn src:main
```

### YAML Configuration

Configure gateway policies declaratively:

```yaml
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
          algorithm: "sliding_window"
        timeout:
          seconds: 5.0
        retry:
          max_attempts: 3
          wait: 1.0
        monitoring:
          log_threshold: 0.1
    
    - pattern: "/api/admin/*"
      features:
        rate_limit:
          quota: 10
          duration: 60
          algorithm: "token_bucket"
        timeout:
          seconds: 30.0
  
  default_features:
    timeout:
      seconds: 10.0
    monitoring:
      log_threshold: 0.5
```

## Installation

```bash
pip install premier
```

For Redis support (optional):
```bash
pip install premier[redis]
```

## Framework Integration

Works with any ASGI framework:

```python
# FastAPI
from fastapi import FastAPI
app = FastAPI()

# Starlette
from starlette.applications import Starlette
app = Starlette()

# Django ASGI
from django.core.asgi import get_asgi_application
app = get_asgi_application()

# Wrap with Premier
config = GatewayConfig.from_file("config.yaml")
gateway = ASGIGateway(config, app=app)
```

## Production Deployment

```python
# production.py
from premier.asgi import ASGIGateway, GatewayConfig
from premier.providers.redis import AsyncRedisCache
from redis.asyncio import Redis

# Redis backend for distributed caching
redis_client = Redis.from_url("redis://localhost:6379")
cache_provider = AsyncRedisCache(redis_client)

# Load configuration
config = GatewayConfig.from_file("production.yaml")

# Create production gateway
gateway = ASGIGateway(config, app=your_app, cache_provider=cache_provider)

# Deploy with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(gateway, host="0.0.0.0", port=8000, workers=4)
```

## Requirements

- Python >= 3.10
- Redis >= 5.0.3 (optional, for distributed deployments)
- PyYAML (for YAML configuration)
- aiohttp (optional, for standalone mode)

## License

MIT License