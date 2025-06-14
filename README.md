# Premier

Premier is a versatile Python toolkit that can be used in three main ways:

1. **Lightweight Standalone API Gateway** - Run as a dedicated gateway service
2. **ASGI App/Middleware** - Wrap existing ASGI applications or add as middleware
3. **Decorator Mode** - Use Premier decorators directly on functions for maximum flexibility

Premier transforms any Python web application into a full-featured API gateway with caching, rate limiting, retry logic, timeouts, and performance monitoring.

--- 
[![PyPI version](https://badge.fury.io/py/premier.svg)](https://badge.fury.io/py/premier)
[![Python Version](https://img.shields.io/pypi/pyversions/premier.svg)](https://pypi.org/project/premier/)
[![License](https://img.shields.io/github/license/raceychan/premier)](https://github.com/raceychan/premier/blob/master/LICENSE)

## Documentation

- **[Web Dashboard](docs/web-gui.md)** - Real-time monitoring and configuration management
- **[Examples](docs/examples.md)** - Complete examples and tutorials
- **[Configuration Guide](docs/configuration.md)** - YAML configuration reference


## Features

Premier provides enterprise-grade API gateway functionality with:

- **Response Caching** - Smart caching with TTL and custom cache keys
- **Rate Limiting** - Multiple algorithms (fixed/sliding window, token/leaky bucket), works with distributed app
- **Retry Logic** - Configurable retry strategies with exponential backoff
- **Request Timeouts** - Per-path timeout protection
- **WebSocket Support** - Full WebSocket proxying with rate limiting and monitoring
- **Path-Based Policies** - Different features per route with regex matching
- **Web Dashboard** - Built-in web GUI for monitoring and configuration management
- **YAML Configuration** - Declarative configuration with namespace support

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

**How it works:** Each app instance has its own Premier gateway wrapper

```
┌─────────────────────────────────────────────────────────────┐
│ App Instance 1                                              │
│ ┌─────────────────┐    ┌─────────────────────────────────┐  │
│ │   Premier       │────│       Your ASGI App            │  │
│ │   Gateway       │    │     (FastAPI/Django/etc)       │  │
│ │  ┌──────────┐   │    │                                 │  │
│ │  │Cache     │   │    │  @app.get("/api/users")        │  │
│ │  │RateLimit │   │    │  async def get_users():         │  │
│ │  │Retry     │   │    │      return users               │  │
│ │  │Timeout   │   │    │                                 │  │
│ │  └──────────┘   │    │                                 │  │
│ └─────────────────┘    └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

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

**How it works:** Single gateway handles all requests and forwards to backend services

```
                        ┌─────────────────────┐
    Client Request      │   Premier Gateway   │
         │              │  ┌──────────────┐   │
         │              │  │ Cache        │   │
         └──────────────►  │ RateLimit    │   │
                        │  │ Retry        │   │
                        │  │ Timeout      │   │
                        │  │ Monitoring   │   │
                        │  └──────────────┘   │
                        └─────┬──────┬────────┘
                              │      │
                    ┌─────────┘      └─────────┐
                    ▼                          ▼
            ┌───────────────┐          ┌───────────────┐
            │   Backend 1   │          │   Backend 2   │
            │ (Any Service) │          │ (Any Service) │
            │               │          │               │
            │ Node.js API   │          │  Python API   │
            │ Java Service  │          │  .NET Service │
            │ Static Files  │          │  Database     │
            └───────────────┘          └───────────────┘
```

```python
from premier.asgi import ASGIGateway, GatewayConfig

config = GatewayConfig.from_file("gateway.yaml")
gateway = ASGIGateway(config, servers=["http://backend:8000"])
```

```bash
uvicorn src:main
```

### Decorator Mode

**How it works:** Apply Premier features directly to individual functions with decorators - no ASGI app required


### WebSocket Support

Premier supports WebSocket connections with the same feature set:

```python
# WebSocket connections are automatically handled
# Configure WebSocket-specific policies in YAML:

premier:
  paths:
    - pattern: "/ws/chat/*"
      features:
        rate_limit:
          quota: 100  # Max 100 connections per minute
          duration: 60
        monitoring:
          log_threshold: 5.0  # Log connections lasting >5s
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
    
    - pattern: "/ws/*"
      features:
        rate_limit:
          quota: 50
          duration: 60
          algorithm: "sliding_window"
        monitoring:
          log_threshold: 1.0
  
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

## Function Resilience Decorators

Premier includes powerful decorators for adding resilience to individual functions:

### Retry Decorator

```python
from premier.retry import retry

@retry(max_attempts=3, wait=1.0, exceptions=(ConnectionError, TimeoutError))
async def api_call():
    # Your function with retry logic
    return await make_request()
```

### Timer Decorator

```python
from premier.timer import timeit, timeout

@timeit(log_threshold=0.1)  # Log calls taking >0.1s
async def slow_operation():
    return await heavy_computation()

@timeout(seconds=5)  # Timeout after 5 seconds
async def time_limited_task():
    return await long_running_operation()
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

## What's Next

- [x] Web GUI
- [x] Websocket Support
- [ ] Circuit Breaker
- [ ] Load Balancer
- [ ] Auth(OAuth, jwt, etc.)
- [ ] MCP integration


## License

MIT License