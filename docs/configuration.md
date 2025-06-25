# Configuration Reference

Premier supports extensive configuration options for path-based policies. This page provides a complete reference of all available configuration fields.

## YAML Configuration Overview

Premier uses YAML files for declarative configuration. Here's the basic structure:

```yaml
premier:
  keyspace: "my-api"           # Namespace for cache keys and throttling
  servers: []                  # Backend servers (standalone mode)
  paths: []                    # Path-specific configuration rules
  default_features: {}         # Default features applied to all paths
```

## Top-Level Configuration

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `keyspace` | string | Namespace for cache keys and throttling | `"asgi-gateway"` |
| `paths` | array | Path-specific configuration rules | `[]` |
| `default_features` | object | Default features applied to all paths | `null` |
| `servers` | array | Backend server URLs for standalone mode | `null` |

### Example

```yaml
premier:
  keyspace: "production-api"
  servers: 
    - "http://backend1:8000"
    - "http://backend2:8000"
  
  default_features:
    timeout:
      seconds: 10.0
    monitoring:
      log_threshold: 1.0
```

## Path Configuration

Configure features for specific URL patterns using path rules.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `pattern` | string | Path pattern (regex or glob-style) | `"/api/users/*"`, `"^/admin/.*$"` |
| `features` | object | Features to apply to this path | See feature configuration below |

### Pattern Matching

Premier supports both glob-style and regex patterns:

=== "Glob Style"
    ```yaml
    paths:
      - pattern: "/api/users/*"        # Matches /api/users/123
      - pattern: "/api/*/posts"        # Matches /api/v1/posts
      - pattern: "/files/**"           # Matches /files/images/photo.jpg
    ```

=== "Regex Style"
    ```yaml
    paths:
      - pattern: "^/api/users/\\d+$"   # Matches /api/users/123 (numbers only)
      - pattern: "^/admin/.*$"         # Matches any path starting with /admin/
      - pattern: "\\.json$"            # Matches paths ending with .json
    ```

## Feature Configuration

### Cache Configuration

Enable response caching for improved performance.

| Field | Type | Description | Default | Example |
|-------|------|-------------|---------|---------|
| `expire_s` | integer | Cache expiration in seconds | `null` (no expiration) | `300` |
| `cache_key` | string/function | Custom cache key | Auto-generated | `"user:{user_id}"` |

```yaml
cache:
  expire_s: 300                 # Cache for 5 minutes
  cache_key: "custom_key"       # Optional custom key
```

### Rate Limiting Configuration

Control request rates to prevent abuse and ensure fair usage.

| Field | Type | Description | Default | Example |
|-------|------|-------------|---------|---------|
| `quota` | integer | Number of requests allowed | Required | `100` |
| `duration` | integer | Time window in seconds | Required | `60` |
| `algorithm` | string | Rate limiting algorithm | `"fixed_window"` | `"sliding_window"` |
| `bucket_size` | integer | Bucket size (for leaky_bucket) | Same as quota | `50` |
| `error_status` | integer | HTTP status code for rate limit errors | `429` | `503` |
| `error_message` | string | Error message for rate limit errors | `"Rate limit exceeded"` | `"Too many requests"` |

#### Available Algorithms

- **`fixed_window`**: Simple time-based windows
- **`sliding_window`**: Smooth rate limiting over time  
- **`token_bucket`**: Burst capacity with steady refill rate
- **`leaky_bucket`**: Queue-based rate limiting with controlled draining

```yaml
rate_limit:
  quota: 100
  duration: 60
  algorithm: "sliding_window"
  error_status: 429
  error_message: "Rate limit exceeded for this endpoint"
```

### Timeout Configuration

Set maximum response times to prevent hanging requests.

| Field | Type | Description | Default | Example |
|-------|------|-------------|---------|---------|
| `seconds` | float | Timeout duration in seconds | Required | `5.0` |
| `error_status` | integer | HTTP status code for timeout errors | `504` | `408` |
| `error_message` | string | Error message for timeout errors | `"Request timeout"` | `"Request took too long"` |

```yaml
timeout:
  seconds: 5.0
  error_status: 504
  error_message: "Request timeout - please try again"
```

### Retry Configuration

Automatically retry failed requests with configurable backoff strategies.

| Field | Type | Description | Default | Example |
|-------|------|-------------|---------|---------|
| `max_attempts` | integer | Maximum retry attempts | `3` | `5` |
| `wait` | float/array/function | Wait time between retries | `1.0` | `[1, 2, 4]` |
| `exceptions` | array | Exception types to retry on | `[Exception]` | Custom exceptions |

#### Wait Strategies

=== "Fixed Delay"
    ```yaml
    retry:
      max_attempts: 3
      wait: 1.0              # Wait 1 second between retries
    ```

=== "Exponential Backoff"
    ```yaml
    retry:
      max_attempts: 4
      wait: [1, 2, 4, 8]     # Increasing delays
    ```

### Circuit Breaker Configuration

Prevent cascading failures by temporarily disabling failing services.

| Field | Type | Description | Default | Example |
|-------|------|-------------|---------|---------|
| `failure_threshold` | integer | Failures before opening circuit | `5` | `10` |
| `recovery_timeout` | float | Seconds before attempting recovery | `60.0` | `120.0` |
| `expected_exception` | string | Exception type that triggers circuit | `"Exception"` | `"ConnectionError"` |

```yaml
circuit_breaker:
  failure_threshold: 5
  recovery_timeout: 60.0
  expected_exception: "ConnectionError"
```

### Monitoring Configuration

Configure performance monitoring and logging thresholds.

| Field | Type | Description | Default | Example |
|-------|------|-------------|---------|---------|
| `log_threshold` | float | Log requests taking longer than this (seconds) | `0.1` | `1.0` |

```yaml
monitoring:
  log_threshold: 0.1          # Log requests > 100ms
```

## Complete Configuration Example

Here's a comprehensive example showing all features:

```yaml
premier:
  keyspace: "production-api"
  servers: 
    - "http://backend1:8000"
    - "http://backend2:8000"
  
  paths:
    # High-traffic user API with aggressive caching
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
          wait: [1, 2, 4]
        circuit_breaker:
          failure_threshold: 5
          recovery_timeout: 60.0
        monitoring:
          log_threshold: 0.1
          
    # Admin API with strict rate limiting
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
          
    # WebSocket connections
    - pattern: "/ws/*"
      features:
        rate_limit:
          quota: 50
          duration: 60
          algorithm: "sliding_window"
        monitoring:
          log_threshold: 1.0
          
  # Applied to all paths that don't match above patterns
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

## Environment Variables

You can override configuration values using environment variables:

```bash
export PREMIER_KEYSPACE="production"
export PREMIER_REDIS_URL="redis://redis:6379"
export PREMIER_LOG_LEVEL="INFO"
```

## Loading Configuration

### From File

```python
from premier.asgi import GatewayConfig

config = GatewayConfig.from_file("gateway.yaml")
```

### From Dictionary

```python
config_dict = {
    "premier": {
        "keyspace": "my-api",
        "paths": [...]
    }
}
config = GatewayConfig.from_dict(config_dict)
```

### From Environment

```python
# Loads from PREMIER_CONFIG_FILE environment variable
config = GatewayConfig.from_env()
```

## Configuration Validation

Premier validates your configuration at startup and provides helpful error messages:

```python
try:
    config = GatewayConfig.from_file("invalid.yaml")
except ConfigurationError as e:
    print(f"Configuration error: {e}")
```

## Hot Reloading

Premier supports hot reloading of configuration in development mode:

```python
config = GatewayConfig.from_file("gateway.yaml", watch=True)
gateway = ASGIGateway(config, app=app)
```

Changes to the YAML file will be automatically detected and applied without restarting the application.

## Next Steps

- [Web Dashboard](web-gui.md) - Monitor and edit configuration via web UI
- [Examples](examples.md) - See complete configuration examples