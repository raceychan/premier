import asyncio
import re
import time
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

import yaml

from ..cache import Cache
from ..dashboard import DashboardService
from ..providers import AsyncCacheProvider, AsyncInMemoryCache
from ..retry import retry
from ..throttler import Throttler
from ..throttler.handler import AsyncDefaultHandler
from ..timer import ILogger
from .loadbalancer import ILoadBalancer, RandomLoadBalancer, create_random_load_balancer

# from urllib.parse import urljoin, urlparse


@dataclass
class CacheConfig:
    """Cache configuration based on cache.py parameters."""

    expire_s: Optional[int] = None
    cache_key: Optional[Union[str, Callable[..., str]]] = None
    encoder: Optional[Callable[[Any], Any]] = None


@dataclass
class RetryConfig:
    """Retry configuration based on retry.py parameters."""

    max_attempts: int = 3
    wait: Union[
        float, int, List[Union[float, int]], Callable[[int], Union[float, int]]
    ] = 1.0
    exceptions: tuple[type[Exception], ...] = (Exception,)
    on_fail: Optional[Callable] = None
    logger: Optional[ILogger] = None


@dataclass
class TimeoutConfig:
    """Timeout configuration based on timer.py parameters."""

    seconds: float
    logger: Optional[ILogger] = None


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    quota: int
    duration: int
    algorithm: str = "fixed_window"
    bucket_size: Optional[int] = None


@dataclass
class MonitoringConfig:
    """Monitoring configuration."""

    log_threshold: float = 0.1


def apply_timeout(
    handler: Callable, timeout_config: Optional[TimeoutConfig]
) -> Callable:
    """Apply timeout wrapper to handler."""
    if timeout_config is None:
        return handler

    async def timeout_wrapper(scope: dict, receive: Callable, send: Callable):
        try:
            await asyncio.wait_for(
                handler(scope, receive, send), timeout=timeout_config.seconds
            )
        except asyncio.TimeoutError:
            if timeout_config.logger:
                timeout_config.logger.exception(
                    f"Request timeout after {timeout_config.seconds}s"
                )
            await send(
                {
                    "type": "http.response.start",
                    "status": 504,
                    "headers": [[b"content-type", b"application/json"]],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"error": "Request timeout"}',
                }
            )

    return timeout_wrapper


def apply_retry_wrapper(
    handler: Callable, retry_config: Optional[RetryConfig]
) -> Callable:
    """Apply retry wrapper to handler."""
    if retry_config is None:
        return handler

    return retry(
        max_attempts=retry_config.max_attempts,
        wait=retry_config.wait,
        exceptions=retry_config.exceptions,
        on_fail=retry_config.on_fail,
        logger=retry_config.logger,
    )(handler)


def apply_rate_limit(handler: Callable, rate_limiter: Optional[Any]) -> Callable:
    """Apply rate limiting wrapper to handler."""
    if rate_limiter is None:
        return handler

    handler = rate_limiter(handler)

    async def rate_limit_wrapper(scope: dict, receive: Callable, send: Callable):
        try:
            await handler(scope, receive, send)
        except Exception:
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [[b"content-type", b"application/json"]],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"error": "Rate limit exceeded"}',
                }
            )

    return rate_limit_wrapper


def apply_cache(
    handler: Callable, cache_config: Optional[CacheConfig], cache_provider
) -> Callable:
    """Apply caching wrapper to handler."""
    if cache_config is None:
        return handler

    async def cache_wrapper(scope: dict, receive: Callable, send: Callable):
        # Extract request key for caching
        path = scope.get("path", "/")
        method = scope.get("method", "GET")

        if cache_config.cache_key:
            if callable(cache_config.cache_key):
                cache_key = cache_config.cache_key(scope)
            else:
                cache_key = cache_config.cache_key
        else:
            cache_key = f"response:{method}:{path}"

        # Try to get cached response
        cached_response = await cache_provider.get(cache_key)
        if cached_response is not None:
            # Mark cache hit in scope for stats tracking
            scope["_cache_hit"] = True
            # Send cached response
            await send(cached_response["start"])
            await send(cached_response["body"])
            return

        # Mark cache miss in scope for stats tracking
        scope["_cache_hit"] = False

        # Capture response for caching
        response_parts = {"start": None, "body": None}

        async def capturing_send(message):
            if message["type"] == "http.response.start":
                response_parts["start"] = message
            elif message["type"] == "http.response.body":
                response_parts["body"] = message
                # Encode and cache the complete response
                cache_value = (
                    cache_config.encoder(response_parts)
                    if cache_config.encoder
                    else response_parts
                )
                await cache_provider.set(
                    cache_key, cache_value, ex=cache_config.expire_s
                )
            await send(message)

        await handler(scope, receive, capturing_send)

    return cache_wrapper


def apply_monitoring(
    handler: Callable, monitor_config: Optional[MonitoringConfig]
) -> Callable:
    """Apply monitoring wrapper to handler."""
    if monitor_config is None:
        return handler

    async def monitor_wrapper(scope: dict, receive: Callable, send: Callable):

        path = scope.get("path", "/")
        method = scope.get("method", "GET")
        request_key = f"{method}:{path}"
        start_time = time.time()
        try:
            await handler(scope, receive, send)
        finally:
            duration = time.time() - start_time
            if duration > monitor_config.log_threshold:
                print(f"Request {request_key} took {duration:.3f}s")

    return monitor_wrapper


@dataclass
class FeatureConfig:
    """Configuration for individual features that can be applied to a path."""

    cache: Optional[CacheConfig] = None
    rate_limit: Optional[RateLimitConfig] = None
    retry: Optional[RetryConfig] = None
    timeout: Optional[TimeoutConfig] = None
    monitoring: Optional[MonitoringConfig] = None

    # Compiled properties (set during feature compilation)
    rate_limiter: Optional[Any] = field(default=None, init=False)

    def get_applicable_features(self) -> List[str]:
        """Get list of features that are configured for this feature config."""
        features = []
        if self.timeout is not None:
            features.append("timeout")
        if self.retry is not None:
            features.append("retry")
        if self.rate_limiter is not None:
            features.append("rate_limit")
        if self.cache is not None:
            features.append("cache")
        if self.monitoring is not None:
            features.append("monitoring")
        return features


@dataclass
class PathConfig:
    """Configuration for a specific path pattern."""

    pattern: str  # regex pattern or exact path
    features: FeatureConfig


@dataclass
class GatewayConfig:
    """Main configuration for the ASGI gateway."""

    paths: List[PathConfig]
    default_features: Optional[FeatureConfig] = None
    keyspace: str = "asgi-gateway"

    @classmethod
    def from_file(
        cls, file_path: Union[str, Path], namespace: str = "premier"
    ) -> "GatewayConfig":
        """Load gateway configuration from a YAML file.

        Args:
            file_path: Path to the YAML configuration file
            namespace: Namespace in the YAML file (e.g., "premier" for top-level or "tool.premier" for nested)

        Returns:
            GatewayConfig instance

        Example YAML structure:
        ```yaml
        premier:
          keyspace: "my-gateway"

          paths:
            - pattern: "/api/*"
              features:
                timeout:
                  seconds: 5.0
                rate_limit:
                  quota: 100
                  duration: 60
                  algorithm: "fixed_window"
                retry:
                  max_attempts: 3
                  wait: 1.0

            - pattern: "/health"
              features:
                monitoring:
                  log_threshold: 0.1

          default_features:
            timeout:
              seconds: 10.0
            cache:
              expire_s: 300
        ```
        """

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Navigate to the specified namespace
        config_data = data
        for part in namespace.split("."):
            if part not in config_data:
                raise KeyError(f"Namespace '{namespace}' not found in {file_path}")
            config_data = config_data[part]

        return cls._from_dict(config_data)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "GatewayConfig":
        """Create GatewayConfig from dictionary data."""
        # Parse paths
        paths = []
        for path_data in data.get("paths", []):
            features = cls._parse_features(path_data.get("features", {}))
            paths.append(PathConfig(pattern=path_data["pattern"], features=features))

        # Parse default features
        default_features = None
        if "default_features" in data:
            default_features = cls._parse_features(data["default_features"])

        return cls(
            paths=paths,
            default_features=default_features,
            keyspace=data.get("keyspace", "asgi-gateway"),
        )

    @staticmethod
    def _parse_features(features_data: Dict[str, Any]) -> FeatureConfig:
        """Parse features configuration from dictionary."""
        # Parse cache config
        cache = None
        if "cache" in features_data:
            cache_data = features_data["cache"]
            cache = CacheConfig(
                expire_s=cache_data.get("expire_s"),
                cache_key=cache_data.get("cache_key"),
                encoder=None,  # Functions can't be serialized in TOML
            )

        # Parse retry config
        retry = None
        if "retry" in features_data:
            retry_data = features_data["retry"]
            retry = RetryConfig(
                max_attempts=retry_data.get("max_attempts", 3),
                wait=retry_data.get("wait", 1.0),
                exceptions=(
                    Exception,
                ),  # Default, can't serialize exception types in TOML
                on_fail=None,  # Functions can't be serialized in TOML
                logger=None,  # Logger instances can't be serialized in TOML
            )

        # Parse timeout config
        timeout = None
        if "timeout" in features_data:
            timeout_data = features_data["timeout"]
            timeout = TimeoutConfig(
                seconds=timeout_data["seconds"],
                logger=None,  # Logger instances can't be serialized in TOML
            )

        # Parse rate limit config
        rate_limit = None
        if "rate_limit" in features_data:
            rate_limit_data = features_data["rate_limit"]
            rate_limit = RateLimitConfig(
                quota=rate_limit_data["quota"],
                duration=rate_limit_data["duration"],
                algorithm=rate_limit_data.get("algorithm", "fixed_window"),
                bucket_size=rate_limit_data.get("bucket_size"),
            )

        # Parse monitoring config
        monitoring = None
        if "monitoring" in features_data:
            monitoring_data = features_data["monitoring"]
            monitoring = MonitoringConfig(
                log_threshold=monitoring_data.get("log_threshold", 0.1)
            )

        return FeatureConfig(
            cache=cache,
            retry=retry,
            timeout=timeout,
            rate_limit=rate_limit,
            monitoring=monitoring,
        )


class ASGIGateway:
    """
    ASGI application that applies Premier gateway features based on path configuration.

    This class creates a pluggable ASGI middleware that can apply different
    combinations of caching, rate limiting, retry logic, timeouts, and monitoring
    to different paths based on configuration.
    """

    def __init__(
        self,
        *,
        config: GatewayConfig,
        app: Optional[Callable] = None,
        servers: Optional[Sequence[str]] = None,
        cache_provider: Optional[AsyncCacheProvider] = None,
        throttler: Optional[Throttler] = None,
        config_file_path: Optional[str] = None,
        lb_factory: Callable[[List[str]], ILoadBalancer] = RandomLoadBalancer,
    ):
        """
        Initialize the ASGI Gateway.

        Args:
            config: Gateway configuration with path-based feature mapping
            app: Downstream ASGI application (optional, can be set later)
            servers: Sequence of server URLs to forward requests to (mutually exclusive with app)
            cache_provider: Cache provider for both caching and throttling
            throttler: Throttler instance for rate limiting
        """
        if app is not None and servers is not None:
            raise ValueError("app and servers are mutually exclusive")

        self.config = config
        self.app = app
        self.servers = list(servers) if servers else None

        # Initialize cache provider
        self._cache_provider = cache_provider or AsyncInMemoryCache()

        # Initialize throttler
        self._throttler = throttler or Throttler(
            handler=AsyncDefaultHandler(self._cache_provider),
            keyspace=f"{config.keyspace}:throttler",
        )

        self._compiled_patterns = self._compile_path_patterns()
        self._session = None
        self._handler_cache: Dict[int, Callable] = {}
        # Cache compiled handlers by compiled feature id

        # Initialize dashboard service
        self._dashboard_service = DashboardService(config_file_path)
        self._stats_enabled = True

        if servers:
            from .forward import ForwardService

            # Initialize forward service
            self._forward_service = ForwardService(self.servers, lb_factory=lb_factory)
        else:
            self._forward_service = None

    def _compile_path_patterns(self) -> List[tuple[re.Pattern, FeatureConfig]]:
        """Compile regex patterns and features for efficient path matching."""
        compiled = []
        for path_config in self.config.paths:
            pattern = path_config.pattern
            if not pattern.startswith("^"):
                # Convert simple path to regex if not already regex
                if "*" in pattern or "?" in pattern or "[" in pattern:
                    # Basic glob-style conversion
                    pattern = pattern.replace("*", ".*").replace("?", ".")
                    pattern = f"^{pattern}$"
                else:
                    # Exact match
                    pattern = f"^{re.escape(pattern)}$"

            compiled_feature = self._compile_features(path_config.features)
            compiled.append((re.compile(pattern), compiled_feature))
        return compiled

    def _compile_features(self, feature_config: FeatureConfig) -> FeatureConfig:
        """Pre-compile features for efficient execution."""
        # Create a copy of the feature config to avoid modifying the original

        compiled = deepcopy(feature_config)

        # Compile rate limiting
        if feature_config.rate_limit is not None:
            rate_config = feature_config.rate_limit
            algo = rate_config.algorithm
            quota = rate_config.quota
            duration = rate_config.duration

            # Create rate limiter based on algorithm
            if algo == "fixed_window":
                limiter = self._throttler.fixed_window(quota, duration)
            elif algo == "sliding_window":
                limiter = self._throttler.sliding_window(quota, duration)
            elif algo == "token_bucket":
                limiter = self._throttler.token_bucket(quota, duration)
            elif algo == "leaky_bucket":
                bucket_size = rate_config.bucket_size or quota
                limiter = self._throttler.leaky_bucket(quota, bucket_size, duration)
            else:
                limiter = self._throttler.fixed_window(quota, duration)

            compiled.rate_limiter = limiter

        return compiled

    def _match_path(self, path: str) -> Optional[FeatureConfig]:
        """Find the first matching path configuration for the given path."""
        for pattern, compiled_feature in self._compiled_patterns:
            if pattern.match(path):
                return compiled_feature

        # Return compiled default features if available
        if self.config.default_features is not None:
            return self._compile_features(self.config.default_features)
        return None

    async def call_downstream(self, scope: dict, receive: Callable, send: Callable):
        if self._forward_service:
            await self._forward_service.forward_http_request(scope, receive, send)
        elif self.app:
            await self.app(scope, receive, send)
        else:
            # Default response if no downstream app or servers
            response = b'{"error": "No downstream application or servers configured"}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [[b"content-type", b"application/json"]],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": response,
                }
            )

    def _get_compiled_handler(self, feature_config: FeatureConfig) -> Callable:
        """Get or build a compiled handler for the given feature configuration."""
        cache_key = id(feature_config)  # Use object id as cache key
        if cache_key in self._handler_cache:
            return self._handler_cache[cache_key]

        # Build and cache the handler
        handler = self.call_downstream

        # Apply features in reverse order since each wraps the previous
        handler = apply_monitoring(handler, feature_config.monitoring)
        handler = apply_cache(handler, feature_config.cache, self._cache_provider)
        handler = apply_rate_limit(handler, feature_config.rate_limiter)
        handler = apply_retry_wrapper(handler, feature_config.retry)
        handler = apply_timeout(handler, feature_config.timeout)

        # Add stats tracking wrapper
        handler = self._apply_stats_tracking(handler)

        # Cache the fully composed handler
        self._handler_cache[cache_key] = handler
        return handler

    async def __call__(self, scope: dict, receive: Callable, send: Callable):
        """ASGI application entry point."""
        if scope["type"] == "websocket":
            # Handle WebSocket connections
            await self._handle_websocket(scope, receive, send)
            return

        elif scope["type"] != "http":
            # Pass through other non-HTTP requests
            if self.app:
                await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")

        # Handle dashboard routes
        if path.startswith("/premier/dashboard"):
            await self._dashboard_service(scope, receive, send)
            return

        compiled_feature = self._match_path(path)

        if compiled_feature:
            handler = self._get_compiled_handler(compiled_feature)
            await handler(scope, receive, send)
        else:
            # No features configured, pass through to downstream app or servers
            if self._forward_service:
                await self._forward_service.forward_http_request(scope, receive, send)
            elif self.app:
                await self.app(scope, receive, send)
            else:
                # Default response
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [[b"content-type", b"text/plain"]],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b"ASGI Gateway - No features configured",
                    }
                )

    def set_downstream_app(self, app: Callable):
        """Set the downstream ASGI application."""
        self.app = app

    async def _handle_websocket(self, scope: dict, receive: Callable, send: Callable):
        """Handle WebSocket connections with optional feature application."""
        path = scope.get("path", "/")
        compiled_feature = self._match_path(path)

        if compiled_feature:
            # Apply relevant features to WebSocket connection
            handler = self._get_websocket_handler(compiled_feature)
            await handler(scope, receive, send)
        else:
            # No features configured, pass through to downstream app or servers
            if self._forward_service:
                await self._forward_service.forward_websocket_connection(
                    scope, receive, send
                )
            elif self.app:
                await self.app(scope, receive, send)
            else:
                # Default WebSocket rejection
                await send({"type": "websocket.close", "code": 1000})

    def _get_websocket_handler(self, feature_config: FeatureConfig) -> Callable:
        """Get or build a WebSocket handler for the given feature configuration."""
        # For WebSocket, we mainly support monitoring and rate limiting
        handler = self._call_websocket_downstream

        # Apply monitoring if configured
        if feature_config.monitoring:
            handler = self._apply_websocket_monitoring(
                handler, feature_config.monitoring
            )

        # Apply rate limiting if configured
        if feature_config.rate_limiter:
            handler = self._apply_websocket_rate_limit(
                handler, feature_config.rate_limiter
            )

        return handler

    async def _call_websocket_downstream(
        self, scope: dict, receive: Callable, send: Callable
    ):
        """Call downstream WebSocket handler."""
        if self._forward_service:
            await self._forward_service.forward_websocket_connection(
                scope, receive, send
            )
        elif self.app:
            await self.app(scope, receive, send)
        else:
            await send({"type": "websocket.close", "code": 1000})

    def _apply_websocket_monitoring(
        self, handler: Callable, monitor_config: MonitoringConfig
    ) -> Callable:
        """Apply monitoring to WebSocket connections."""

        async def monitor_wrapper(scope: dict, receive: Callable, send: Callable):

            path = scope.get("path", "/")
            connection_start = time.time()

            async def monitoring_send(message):
                if message["type"] == "websocket.close":
                    duration = time.time() - connection_start
                    if duration > monitor_config.log_threshold:
                        print(f"WebSocket {path} connection lasted {duration:.3f}s")
                await send(message)

            await handler(scope, receive, monitoring_send)

        return monitor_wrapper

    def _apply_websocket_rate_limit(self, handler: Callable, rate_limiter) -> Callable:
        """Apply rate limiting to WebSocket connections."""
        handler = rate_limiter(handler)

        async def rate_limit_wrapper(scope: dict, receive: Callable, send: Callable):
            # Check rate limit on connection

            try:
                await handler(scope, receive, send)
            except Exception:
                # Rate limit exceeded, close connection
                await send(
                    {
                        "type": "websocket.close",
                        "code": 1008,
                        "reason": b"Rate limit exceeded",
                    }
                )

        return rate_limit_wrapper

    def _apply_stats_tracking(self, handler: Callable) -> Callable:
        """Apply stats tracking wrapper to handler."""
        if not self._stats_enabled:
            return handler

        async def stats_wrapper(scope: dict, receive: Callable, send: Callable):
            path = scope.get("path", "/")
            method = scope.get("method", "GET")
            start_time = time.time()
            status = 200

            # Track response info
            async def tracking_send(message):
                nonlocal status
                if message["type"] == "http.response.start":
                    status = message["status"]
                await send(message)

            try:
                await handler(scope, receive, tracking_send)
            finally:
                response_time = (time.time() - start_time) * 1000  # Convert to ms
                cache_hit = scope.get("_cache_hit", False)
                self._dashboard_service.record_request(
                    method, path, status, response_time, cache_hit
                )

        return stats_wrapper

    async def close(self):
        """Close gateway resources."""
        await self._cache_provider.close()
        if self._forward_service:
            await self._forward_service.close()


def create_gateway(
    config: GatewayConfig,
    app: Optional[Callable] = None,
    cache_provider: Optional[AsyncCacheProvider] = None,
    throttler: Optional[Throttler] = None,
    lb_factory: Callable[[List[str]], ILoadBalancer] = RandomLoadBalancer,
) -> ASGIGateway:
    """
    Factory function to create an ASGI Gateway.

    Args:
        config: Gateway configuration with path-based feature mapping
        app: Downstream ASGI application (optional)
        cache_provider: Cache provider for both caching and throttling
        throttler: Throttler instance for rate limiting
        lb_factory: Load balancer factory function

    Returns:
        Configured ASGIGateway instance
    """
    return ASGIGateway(
        config=config,
        app=app,
        cache_provider=cache_provider,
        throttler=throttler,
        lb_factory=lb_factory,
    )
