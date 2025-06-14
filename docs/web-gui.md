# Web GUI Dashboard

Premier provides a built-in web dashboard for monitoring and managing your API gateway in real-time.

## Features

- **Real-time Monitoring** - Live request/response metrics and performance data
- **Configuration Management** - View and update gateway configuration
- **Request Analytics** - Detailed request logs and statistics
- **Cache Management** - Monitor cache hit rates and manage cached data
- **Rate Limiting Dashboard** - View current rate limits and usage
- **Health Monitoring** - System health and uptime statistics

## Accessing the Dashboard

The dashboard is automatically available at `/premier/dashboard` when you run your Premier gateway:

```
http://localhost:8000/premier/dashboard
```

## Configuration

The dashboard is enabled by default. You can customize its behavior in your configuration:
<!-- 
```yaml
premier:
  dashboard:
    enabled: true
    path: "/premier/dashboard"
    auth:
      enabled: false  # Set to true for authentication
      username: "admin"
      password: "secret"
``` -->

## Dashboard Sections

### Overview
- Real-time request rate
- Average response time
- Error rate
- Cache hit ratio

### Requests
- Live request log
- Response time distribution
- Status code breakdown
- Top endpoints by traffic

### Configuration
- Current gateway configuration
- Path-based policies
- Feature settings
- Hot reload configuration changes

### Cache
- Cache statistics
- Hit/miss ratios
- Cache size and memory usage
- Manual cache management

### Rate Limiting
- Current rate limit status
- Usage by endpoint
- Rate limit violations
- Algorithm performance

<!-- ## Security

For production deployments, enable authentication:

```yaml
premier:
  dashboard:
    auth:
      enabled: true
      username: "your-username"
      password: "your-secure-password"
``` -->

## API Endpoints

The dashboard uses these API endpoints (also available for programmatic access):

- `GET /premier/api/stats` - Current statistics
- `GET /premier/api/config` - Current configuration
- `POST /premier/api/config` - Update configuration
- `GET /premier/api/cache` - Cache statistics
- `DELETE /premier/api/cache` - Clear cache
- `GET /premier/api/requests` - Request logs

## Custom Styling

You can customize the dashboard appearance by overriding CSS variables or providing custom themes.