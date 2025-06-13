from typing import Dict, List, Optional, Callable, Any, Awaitable, Sequence
import asyncio
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin

from .main import Premier

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


@dataclass
class FeatureConfig:
    """Configuration for individual features that can be applied to a path."""
    cache: Optional[Dict[str, Any]] = None
    rate_limit: Optional[Dict[str, Any]] = None
    retry: Optional[Dict[str, Any]] = None
    timeout: Optional[float] = None
    monitoring: Optional[Dict[str, Any]] = None


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


@dataclass
class CompiledFeature:
    """Pre-compiled feature handler for efficient execution."""
    timeout_seconds: Optional[float] = None
    retry_config: Optional[Dict[str, Any]] = None
    rate_limiter: Optional[Any] = None
    cache_config: Optional[Dict[str, Any]] = None
    monitor_config: Optional[Dict[str, Any]] = None
    
    def apply_timeout(self, handler: Callable) -> Callable:
        """Apply timeout wrapper to handler."""
        if self.timeout_seconds is None:
            return handler
        
        timeout_seconds = self.timeout_seconds
        
        async def timeout_wrapper(scope: dict, receive: Callable, send: Callable):
            try:
                await asyncio.wait_for(handler(scope, receive, send), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                await send({
                    "type": "http.response.start",
                    "status": 504,
                    "headers": [[b"content-type", b"application/json"]],
                })
                await send({
                    "type": "http.response.body",
                    "body": b'{"error": "Request timeout"}',
                })
        
        return timeout_wrapper
    
    def apply_retry(self, handler: Callable) -> Callable:
        """Apply retry wrapper to handler."""
        if self.retry_config is None:
            return handler
        
        retry_config = self.retry_config
        max_attempts = retry_config.get("max_attempts", 3)
        wait_time = retry_config.get("wait", 1.0)
        
        async def retry_wrapper(scope: dict, receive: Callable, send: Callable):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    await handler(scope, receive, send)
                    return
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(wait_time)
                    else:
                        raise
        
        return retry_wrapper
    
    def apply_rate_limit(self, handler: Callable) -> Callable:
        """Apply rate limiting wrapper to handler."""
        if self.rate_limiter is None:
            return handler
        
        limiter = self.rate_limiter
        
        async def rate_limit_wrapper(scope: dict, receive: Callable, send: Callable):
            @limiter
            async def limited_func():
                await handler(scope, receive, send)
            
            try:
                await limited_func()
            except Exception as e:
                await send({
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [[b"content-type", b"application/json"]],
                })
                await send({
                    "type": "http.response.body",
                    "body": b'{"error": "Rate limit exceeded"}',
                })
        
        return rate_limit_wrapper
    
    def apply_cache(self, handler: Callable) -> Callable:
        """Apply caching wrapper to handler."""
        if self.cache_config is None:
            return handler
        
        cache_config = self.cache_config
        expire_s = cache_config.get("expire_s", 300)
        
        async def cache_wrapper(scope: dict, receive: Callable, send: Callable):
            # Extract request key for caching
            path = scope.get("path", "/")
            method = scope.get("method", "GET")
            cache_key = f"response:{method}:{path}"
            # In a full implementation, we'd check cache here
            # and return cached response if available
            await handler(scope, receive, send)
        
        return cache_wrapper
    
    def apply_monitoring(self, handler: Callable) -> Callable:
        """Apply monitoring wrapper to handler."""
        if self.monitor_config is None:
            return handler
        
        monitor_config = self.monitor_config
        
        async def monitor_wrapper(scope: dict, receive: Callable, send: Callable):
            import time
            path = scope.get("path", "/")
            method = scope.get("method", "GET")
            request_key = f"{method}:{path}"
            start_time = time.time()
            try:
                await handler(scope, receive, send)
            finally:
                duration = time.time() - start_time
                if duration > monitor_config.get("log_threshold", 0.1):
                    print(f"Request {request_key} took {duration:.3f}s")
        
        return monitor_wrapper
    
    def get_applicable_features(self) -> List[str]:
        """Get list of features that are configured for this compiled feature."""
        features = []
        if self.timeout_seconds is not None:
            features.append("timeout")
        if self.retry_config is not None:
            features.append("retry")
        if self.rate_limiter is not None:
            features.append("rate_limit")
        if self.cache_config is not None:
            features.append("cache")
        if self.monitor_config is not None:
            features.append("monitoring")
        return features


class ASGIGateway:
    """
    ASGI application that applies Premier gateway features based on path configuration.
    
    This class creates a pluggable ASGI middleware that can apply different
    combinations of caching, rate limiting, retry logic, timeouts, and monitoring
    to different paths based on configuration.
    """
    
    def __init__(self, config: GatewayConfig, app: Optional[Callable] = None, servers: Optional[Sequence[str]] = None):
        """
        Initialize the ASGI Gateway.
        
        Args:
            config: Gateway configuration with path-based feature mapping
            app: Downstream ASGI application (optional, can be set later)
            servers: Sequence of server URLs to forward requests to (mutually exclusive with app)
        """
        if app is not None and servers is not None:
            raise ValueError("app and servers are mutually exclusive")
        
        if servers is not None and not AIOHTTP_AVAILABLE:
            raise RuntimeError("aiohttp is required when servers parameter is used. Install with: pip install aiohttp")
        
        self.config = config
        self.app = app
        self.servers = list(servers) if servers else None
        self.premier = Premier(keyspace=config.keyspace)
        self._compiled_patterns = self._compile_path_patterns()
        self._session = None
        self._handler_cache: Dict[int, Callable] = {}  # Cache compiled handlers by compiled feature id
    
    def _compile_path_patterns(self) -> List[tuple[re.Pattern, CompiledFeature]]:
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
    
    def _compile_features(self, feature_config: FeatureConfig) -> CompiledFeature:
        """Pre-compile features for efficient execution."""
        compiled = CompiledFeature()
        
        # Compile timeout
        if feature_config.timeout is not None:
            compiled.timeout_seconds = feature_config.timeout
        
        # Compile retry
        if feature_config.retry is not None:
            compiled.retry_config = feature_config.retry
        
        # Compile rate limiting
        if feature_config.rate_limit is not None:
            rate_config = feature_config.rate_limit
            algo = rate_config.get("algorithm", "fixed_window")
            quota = rate_config["quota"]
            duration = rate_config["duration"]
            
            # Create rate limiter based on algorithm
            if algo == "fixed_window":
                limiter = self.premier.fixed_window(quota, duration)
            elif algo == "sliding_window":
                limiter = self.premier.sliding_window(quota, duration)
            elif algo == "token_bucket":
                limiter = self.premier.token_bucket(quota, duration)
            elif algo == "leaky_bucket":
                bucket_size = rate_config.get("bucket_size", quota)
                limiter = self.premier.leaky_bucket(bucket_size, quota, duration)
            else:
                limiter = self.premier.fixed_window(quota, duration)
            
            compiled.rate_limiter = limiter
        
        # Compile cache
        if feature_config.cache is not None:
            compiled.cache_config = feature_config.cache
        
        # Compile monitoring
        if feature_config.monitoring is not None:
            compiled.monitor_config = feature_config.monitoring
        
        return compiled
    
    def _match_path(self, path: str) -> Optional[CompiledFeature]:
        """Find the first matching path configuration for the given path."""
        for pattern, compiled_feature in self._compiled_patterns:
            if pattern.match(path):
                return compiled_feature
        
        # Return compiled default features if available
        if self.config.default_features is not None:
            return self._compile_features(self.config.default_features)
        return None
    
    def _build_downstream_handler(self) -> Callable:
        """Build the base downstream handler (reusable across requests)."""
        async def call_downstream(scope: dict, receive: Callable, send: Callable):
            if self.servers:
                await self._forward_to_server(scope, receive, send)
            elif self.app:
                await self.app(scope, receive, send)
            else:
                # Default response if no downstream app or servers
                response = b'{"error": "No downstream application or servers configured"}'
                await send({
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [[b"content-type", b"application/json"]],
                })
                await send({
                    "type": "http.response.body",
                    "body": response,
                })
        return call_downstream
    
    def _get_compiled_handler(self, compiled_feature: CompiledFeature) -> Callable:
        """Get or build a compiled handler for the given feature configuration."""
        cache_key = id(compiled_feature)  # Use object id as cache key
        if cache_key in self._handler_cache:
            return self._handler_cache[cache_key]
        
        # Build and cache the handler
        handler = self._build_downstream_handler()
        
        # Apply features in reverse order since each wraps the previous
        feature_appliers = [
            compiled_feature.apply_monitoring,
            compiled_feature.apply_cache,
            compiled_feature.apply_rate_limit,
            compiled_feature.apply_retry,
            compiled_feature.apply_timeout,
        ]
        
        for applier in feature_appliers:
            handler = applier(handler)
        
        # Cache the fully composed handler
        self._handler_cache[cache_key] = handler
        return handler
    
    async def _apply_features(self, scope: dict, receive: Callable, send: Callable, compiled_feature: CompiledFeature):
        """Apply the configured features to the request."""
        handler = self._get_compiled_handler(compiled_feature)
        await handler(scope, receive, send)
    
    async def __call__(self, scope: dict, receive: Callable, send: Callable):
        """ASGI application entry point."""
        if scope["type"] != "http":
            # Pass through non-HTTP requests
            if self.app:
                await self.app(scope, receive, send)
            return
        
        path = scope.get("path", "/")
        compiled_feature = self._match_path(path)
        
        if compiled_feature:
            await self._apply_features(scope, receive, send, compiled_feature)
        else:
                # No features configured, pass through to downstream app or servers
            if self.servers:
                await self._forward_to_server(scope, receive, send)
            elif self.app:
                await self.app(scope, receive, send)
            else:
                # Default response
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [[b"content-type", b"text/plain"]],
                })
                await send({
                    "type": "http.response.body",
                    "body": b"ASGI Gateway - No features configured",
                })
    
    def set_downstream_app(self, app: Callable):
        """Set the downstream ASGI application."""
        self.app = app
    
    async def _get_session(self):
        """Get or create aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def _forward_to_server(self, scope: dict, receive: Callable, send: Callable):
        """Forward the request to one of the configured servers."""
        import random
        
        # Simple round-robin/random selection of server
        if not self.servers:
            raise RuntimeError("No servers configured")
        server_url = random.choice(self.servers)
        
        # Build the target URL
        path = scope.get("path", "/")
        query_string = scope.get("query_string", b"").decode("utf-8")
        target_url = f"{server_url.rstrip('/')}{path}"
        if query_string:
            target_url += f"?{query_string}"
        
        method = scope.get("method", "GET")
        headers = {}
        
        # Convert ASGI headers to dict
        for header_name, header_value in scope.get("headers", []):
            name = header_name.decode("latin1")
            value = header_value.decode("latin1")
            headers[name] = value
        
        # Remove hop-by-hop headers
        hop_by_hop = {"connection", "keep-alive", "proxy-authenticate", 
                     "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade"}
        headers = {k: v for k, v in headers.items() if k.lower() not in hop_by_hop}
        
        # Collect request body
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                if not message.get("more_body", False):
                    break
        
        session = await self._get_session()
        
        try:
            async with session.request(
                method=method,
                url=target_url,
                headers=headers,
                data=body
            ) as response:
                # Send response start
                response_headers = []
                for name, value in response.headers.items():
                    # Skip hop-by-hop headers
                    if name.lower() not in hop_by_hop:
                        response_headers.append([name.encode("latin1"), value.encode("latin1")])
                
                await send({
                    "type": "http.response.start",
                    "status": response.status,
                    "headers": response_headers,
                })
                
                # Stream response body
                async for chunk in response.content.iter_chunked(8192):
                    await send({
                        "type": "http.response.body",
                        "body": chunk,
                        "more_body": True,
                    })
                
                # Send final empty chunk
                await send({
                    "type": "http.response.body",
                    "body": b"",
                    "more_body": False,
                })
        
        except Exception as e:
            # Send error response
            error_response = f'{{"error": "Proxy error: {str(e)}"}}'.encode()
            await send({
                "type": "http.response.start",
                "status": 502,
                "headers": [[b"content-type", b"application/json"]],
            })
            await send({
                "type": "http.response.body",
                "body": error_response,
            })
    
    async def close(self):
        """Close gateway resources."""
        if self._session:
            await self._session.close()
        await self.premier.close()


def create_gateway(config: GatewayConfig, app: Optional[Callable] = None) -> ASGIGateway:
    """
    Factory function to create an ASGI Gateway.
    
    Args:
        config: Gateway configuration with path-based feature mapping
        app: Downstream ASGI application (optional)
    
    Returns:
        Configured ASGIGateway instance
    """
    return ASGIGateway(config, app)