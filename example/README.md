# Premier Gateway Example

This example demonstrates Premier API Gateway with a comprehensive dashboard.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install fastapi uvicorn pyyaml
   ```

2. **Run the application:**
   ```bash
   cd example
   uvicorn main:gateway --host 0.0.0.0 --port 8000 --reload
   ```

3. **Visit the dashboard:**
   ```
   http://localhost:8000/premier/dashboard
   ```

## What's Included

### FastAPI Application (`app.py`)
- **User Management**: `/api/users*` - CRUD operations with mock data
- **Product Catalog**: `/api/products*` - Product browsing endpoints  
- **Admin Operations**: `/api/admin/*` - Restricted admin functionality
- **Search**: `/api/search` - Expensive search operation (good for caching)
- **Test Endpoints**: 
  - `/api/slow` - Tests timeout handling
  - `/api/unreliable` - Tests retry logic
  - `/api/bulk/*` - Tests rate limiting

### Gateway Configuration (`gateway.yaml`)
- **Path-specific policies** with different caching, rate limiting, and timeout strategies
- **Caching**: 5-30 minutes TTL based on endpoint characteristics
- **Rate Limiting**: Different algorithms (sliding window, token bucket, fixed window)
- **Timeout Protection**: 5-60 seconds based on operation complexity
- **Retry Logic**: Smart retry strategies for different endpoint types
- **Monitoring**: Performance tracking with configurable thresholds

### Premier Dashboard Features
- **Real-time Statistics**: Request counts, cache hit rates, response times
- **Recent Requests**: Live request monitoring with status codes and timings
- **Active Policies**: View configured policies and their request counts
- **Configuration Editor**: Edit and validate YAML configuration in real-time
- **Auto-refresh**: Dashboard updates every 30 seconds

## Testing the Features

### Cache Testing
```bash
# First request (cache miss)
curl http://localhost:8000/api/users
# Second request (cache hit - faster)
curl http://localhost:8000/api/users
```

### Rate Limiting Testing
```bash
# Spam admin endpoint to trigger rate limiting
for i in {1..15}; do curl http://localhost:8000/api/admin/stats; done
```

### Timeout Testing
```bash
# Some requests will timeout after 5 seconds
curl http://localhost:8000/api/slow
```

### Retry Testing
```bash
# Will retry on failures automatically
curl http://localhost:8000/api/unreliable
```

## Dashboard URLs

- **Main Dashboard**: `http://localhost:8000/premier/dashboard`
- **Stats API**: `http://localhost:8000/premier/dashboard/api/stats`
- **Policies API**: `http://localhost:8000/premier/dashboard/api/policies`
- **Config API**: `http://localhost:8000/premier/dashboard/api/config`

## Configuration Management

The dashboard allows you to:
1. **View** current YAML configuration
2. **Edit** configuration in real-time
3. **Validate** configuration before saving
4. **Reload** configuration from file

Changes take effect immediately without restart!

## Performance Monitoring

Watch the dashboard to see:
- Request patterns and performance
- Cache effectiveness
- Rate limiting in action
- Error rates and retry behavior
- Configuration impact on performance