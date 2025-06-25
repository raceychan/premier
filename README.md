# Premier

[![PyPI version](https://badge.fury.io/py/premier.svg)](https://badge.fury.io/py/premier)
[![Python Version](https://img.shields.io/pypi/pyversions/premier.svg)](https://pypi.org/project/premier/)
[![License](https://img.shields.io/github/license/raceychan/premier)](https://github.com/raceychan/premier/blob/master/LICENSE)

---

Premier is a versatile Python toolkit that can be used in three main ways:

1. **Lightweight Standalone API Gateway** - Run as a dedicated gateway service
2. **ASGI App/Middleware** - Wrap existing ASGI applications or add as middleware
3. **Decorator Mode** - Use Premier decorators directly on functions for maximum flexibility

Premier transforms any Python web application into a full-featured API gateway with caching, rate limiting, retry logic, timeouts, and performance monitoring.

Premier comes with a nice dashboard for you to monitor your requests

![image](/docs/images/dashboard.png)

## Documentation

📚 **[Complete Documentation Site](https://raceychan.github.io/premier)** - Full documentation with examples, tutorials, and API reference

Quick links:
- **[Installation & Quick Start](https://raceychan.github.io/premier/quickstart/)** - Get started in minutes
- **[Configuration Guide](https://raceychan.github.io/premier/configuration/)** - Complete YAML configuration reference
- **[Web Dashboard](https://raceychan.github.io/premier/web-gui/)** - Real-time monitoring and configuration management
- **[Examples](https://raceychan.github.io/premier/examples/)** - Complete examples and tutorials

## Features

Premier provides enterprise-grade API gateway functionality with:

- **API Gateway Features** - caching, rate limiting, retry logic, and timeout, etc.
- **Path-Based Policies** - Different features per route with regex matching
- **Load Balancing & Circuit Breaker** - Round robin load balancing with fault tolerance
- **WebSocket Support** - Full WebSocket proxying with rate limiting and monitoring
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
│ │   Premier       │────│       Your ASGI App             │  │
│ │   Gateway       │    │     (FastAPI/Django/etc)        │  │
│ │  ┌──────────┐   │    │                                 │  │
│ │  │Cache     │   │    │  @app.get("/api/users")         │  │
│ │  │RateLimit │   │    │  async def get_users():         │  │
│ │  │Retry     │   │    │      return users               │  │
│ │  │Timeout   │   │    │                                 │  │
│ │  └──────────┘   │    │                                 │  │
│ └─────────────────┘    └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

You can keep your existing app.py file untouched

```python
# app.py
from premier.asgi import ASGIGateway, GatewayConfig
from fastapi import FastAPI

# Your existing app - no changes needed
app = FastAPI()

@app.get("/api/users/{user_id}")
async def get_user(user_id: int):
    return await fetch_user_from_database(user_id)
```

Next, import your app instance and wrap it with ASGIGateway:

```python
# gateway.py
from .app import app
# Load configuration and wrap app
config = GatewayConfig.from_file("gateway.yaml")
app = ASGIGateway(config=config, app=app)
```

Then, instead of serving the original app directly, serve the one wrapped with ASGIGateway.

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
# main.py
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

## Configuration Reference

Premier supports extensive configuration options for path-based policies. Here's a complete reference of all available configuration fields:

### Top-Level Configuration

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `keyspace` | string | Namespace for cache keys and throttling | `"asgi-gateway"` |
| `paths` | array | Path-specific configuration rules | `[]` |
| `default_features` | object | Default features applied to all paths | `null` |
| `servers` | array | Backend server URLs for standalone mode | `null` |

### Path Configuration

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `pattern` | string | Path pattern (regex or glob-style) | `"/api/users/*"`, `"^/admin/.*$"` |
| `features` | object | Features to apply to this path | See feature configuration below |

### Feature Configuration

#### Cache Configuration

| Field | Type | Description | Default | Example |
|-------|------|-------------|---------|---------|
| `expire_s` | integer | Cache expiration in seconds | `null` (no expiration) | `300` |
| `cache_key` | string/function | Custom cache key | Auto-generated | `"user:{user_id}"` |

#### Rate Limiting Configuration

| Field | Type | Description | Default | Example |
|-------|------|-------------|---------|---------|
| `quota` | integer | Number of requests allowed | Required | `100` |
| `duration` | integer | Time window in seconds | Required | `60` |
| `algorithm` | string | Rate limiting algorithm | `"fixed_window"` | `"sliding_window"`, `"token_bucket"`, `"leaky_bucket"` |
| `bucket_size` | integer | Bucket size (for leaky_bucket) | Same as quota | `50` |
| `error_status` | integer | HTTP status code for rate limit errors | `429` | `503` |
| `error_message` | string | Error message for rate limit errors | `"Rate limit exceeded"` | `"Too many requests"` |

#### Timeout Configuration

| Field | Type | Description | Default | Example |
|-------|------|-------------|---------|---------|
| `seconds` | float | Timeout duration in seconds | Required | `5.0` |
| `error_status` | integer | HTTP status code for timeout errors | `504` | `408` |
| `error_message` | string | Error message for timeout errors | `"Request timeout"` | `"Request took too long"` |

#### Retry Configuration

| Field | Type | Description | Default | Example |
|-------|------|-------------|---------|---------|
| `max_attempts` | integer | Maximum retry attempts | `3` | `5` |
| `wait` | float/array/function | Wait time between retries | `1.0` | `[1, 2, 4]` |
| `exceptions` | array | Exception types to retry on | `[Exception]` | Custom exceptions |

#### Circuit Breaker Configuration

| Field | Type | Description | Default | Example |
|-------|------|-------------|---------|---------|
| `failure_threshold` | integer | Failures before opening circuit | `5` | `10` |
| `recovery_timeout` | float | Seconds before attempting recovery | `60.0` | `120.0` |
| `expected_exception` | string | Exception type that triggers circuit | `"Exception"` | `"ConnectionError"` |

#### Monitoring Configuration

| Field | Type | Description | Default | Example |
|-------|------|-------------|---------|---------|
| `log_threshold` | float | Log requests taking longer than this (seconds) | `0.1` | `1.0` |

### Complete Configuration Example

```yaml
premier:
  keyspace: "production-api"
  servers: ["http://backend1:8000", "http://backend2:8000"]
  
  paths:
    - pattern: "/api/users/*"
      features:
        cache:
          expire_s: 300
        rate_limit:
          quota: 1000
          duration: 60
          algorithm: "sliding_window"
          error_status: 429
          error_message: "Rate limit exceeded for user API"
        timeout:
          seconds: 5.0
          error_status: 504
          error_message: "User API timeout"
        retry:
          max_attempts: 3
          wait: [1, 2, 4]  # Exponential backoff
        circuit_breaker:
          failure_threshold: 5
          recovery_timeout: 60.0
        monitoring:
          log_threshold: 0.1
          
    - pattern: "/api/admin/*"
      features:
        rate_limit:
          quota: 10
          duration: 60
          algorithm: "token_bucket"
          error_status: 403
          error_message: "Admin API rate limit exceeded"
        timeout:
          seconds: 30.0
          error_status: 408
          error_message: "Admin operation timeout"
        monitoring:
          log_threshold: 0.5
          
  default_features:
    timeout:
      seconds: 10.0
    rate_limit:
      quota: 100
      duration: 60
      algorithm: "fixed_window"
    monitoring:
      log_threshold: 1.0
```

### Algorithm Options

- **`fixed_window`**: Simple time-based windows
- **`sliding_window`**: Smooth rate limiting over time
- **`token_bucket`**: Burst capacity with steady refill rate
- **`leaky_bucket`**: Queue-based rate limiting with controlled draining

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
- [x] Load Balancer
- [x] Circuit Breaker
- [ ] Auth(OAuth, jwt, etc.)
- [ ] Authorization, Access control(RBAC, ABAC, Whitelist, etc.)
- [ ] MCP integration

## License

MIT License
