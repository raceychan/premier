# Examples

This directory contains practical examples demonstrating Premier API Gateway features.

## Complete Example Application

The `example/` directory contains a full-featured demonstration with:

- **FastAPI Backend** (`app.py`) - Complete API with users, products, admin endpoints
- **Premier Configuration** (`gateway.yaml`) - Production-ready gateway policies  
- **Dashboard Integration** (`main.py`) - Gateway with web UI
- **Documentation** (`README.md`) - Detailed setup and testing guide

## Quick Start

```bash
cd example
uv run main.py
```

Visit: http://localhost:8000/premier/dashboard

## What You'll Learn

### 1. Plugin Mode Integration
```python
from premier.asgi import ASGIGateway, GatewayConfig
from app import app

config = GatewayConfig.from_file("gateway.yaml")
gateway = ASGIGateway(config, app=app)
```

### 2. YAML Configuration
```yaml
premier:
  paths:
    - pattern: "/api/users*"
      features:
        cache:
          expire_s: 300
        rate_limit:
          quota: 100
          duration: 60
```

### 3. Web Dashboard
- Real-time monitoring
- Configuration editing
- Performance analytics
- Cache management

## API Endpoints for Testing

### Caching Demo
- `GET /api/users` - 5 minute cache
- `GET /api/products` - 10 minute cache  
- `GET /api/search?q=alice` - 30 minute cache

### Rate Limiting Demo
- `GET /api/admin/stats` - 10 requests/minute
- `POST /api/bulk/process` - 5 requests/minute
- `GET /api/users` - 100 requests/minute

### Resilience Demo
- `GET /api/slow` - Tests timeouts (5 second limit)
- `GET /api/unreliable` - Tests retry logic (60% failure rate)

### Monitoring Demo
- All endpoints have performance thresholds
- Dashboard shows real-time metrics
- Request logs with timing data

## Testing Commands

### Cache Performance
```bash
# Cache miss (slow)
time curl http://localhost:8000/api/users

# Cache hit (fast)  
time curl http://localhost:8000/api/users
```

### Rate Limiting
```bash
# Trigger rate limiting
for i in {1..15}; do 
  curl -w "%{http_code}\n" http://localhost:8000/api/admin/stats
done
```

### Timeout Handling
```bash
# Some requests timeout after 5s
curl -w "Time: %{time_total}s\n" http://localhost:8000/api/slow
```

### Retry Logic
```bash
# Automatic retries on failures
curl -v http://localhost:8000/api/unreliable
```

## Configuration Patterns

### High-Traffic Endpoints
```yaml
- pattern: "/api/popular/*"
  features:
    cache:
      expire_s: 600
    rate_limit:
      quota: 1000
      algorithm: "token_bucket"
```

### Admin/Sensitive Endpoints  
```yaml
- pattern: "/api/admin/*"
  features:
    rate_limit:
      quota: 10
      algorithm: "fixed_window"
    timeout:
      seconds: 30.0
```

### Expensive Operations
```yaml
- pattern: "/api/analytics/*"
  features:
    cache:
      expire_s: 1800
    rate_limit:
      quota: 5
    timeout:
      seconds: 60.0
```

## Advanced Features

### Custom Cache Keys
```yaml
cache:
  expire_s: 300
  key_template: "custom:{method}:{path}:{user_id}"
```

### Multiple Rate Limit Algorithms
- `sliding_window` - Smooth rate limiting
- `token_bucket` - Burst handling
- `fixed_window` - Simple quotas  
- `leaky_bucket` - Consistent flow

### Retry Strategies
```yaml
retry:
  max_attempts: 5
  wait: 1.0
  backoff: "exponential"
  exceptions: ["ConnectionError", "TimeoutError"]
```

## Production Deployment

### With Redis Backend
```python
from premier.providers.redis import AsyncRedisCache
from redis.asyncio import Redis

redis_client = Redis.from_url("redis://localhost:6379")
cache_provider = AsyncRedisCache(redis_client)

gateway = ASGIGateway(config, app=app, cache_provider=cache_provider)
```

### Multiple Workers
```bash
uvicorn main:gateway --workers 4 --host 0.0.0.0 --port 8000
```

### Docker Deployment
```dockerfile
FROM python:3.10-slim
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["uvicorn", "main:gateway", "--host", "0.0.0.0", "--port", "8000"]
```

## Next Steps

1. **Explore the Example** - Run the complete example and experiment with the dashboard
2. **Try Different Configs** - Modify `gateway.yaml` and see live changes
3. **Integration Testing** - Use your own FastAPI/Django app
4. **Production Setup** - Add Redis, monitoring, and scaling