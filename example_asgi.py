"""
Example usage of Premier ASGI Gateway.

This example demonstrates how to configure and use the ASGI Gateway
with different features applied to different paths.
"""

import asyncio
from premier.asgi import create_gateway, GatewayConfig


# Example downstream ASGI application
async def simple_app(scope, receive, send):
    """Simple ASGI app for demonstration."""
    if scope["type"] == "http":
        path = scope.get("path", "/")
        method = scope.get("method", "GET")
        
        response_body = f"Hello from {method} {path}".encode()
        
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"text/plain"]],
        })
        await send({
            "type": "http.response.body",
            "body": response_body,
        })


# Gateway configuration
config: GatewayConfig = {
    "keyspace": "example-gateway",
    "paths": [
        {
            "pattern": "/api/users/*",
            "features": {
                "rate_limit": {
                    "algorithm": "sliding_window",
                    "quota": 100,
                    "duration": 60,  # 100 requests per minute
                },
                "cache": {
                    "expire_s": 300,  # 5 minutes
                },
                "timeout": 10.0,  # 10 seconds
                "monitoring": {
                    "log_threshold": 0.1,  # Log requests > 100ms
                },
            },
        },
        {
            "pattern": "/api/admin/*",
            "features": {
                "rate_limit": {
                    "algorithm": "token_bucket",
                    "quota": 10,
                    "duration": 60,  # 10 requests per minute with bursts
                },
                "retry": {
                    "max_attempts": 3,
                    "wait": 1.0,
                },
                "timeout": 30.0,  # 30 seconds for admin operations
            },
        },
        {
            "pattern": "/api/public/*",
            "features": {
                "rate_limit": {
                    "algorithm": "fixed_window",
                    "quota": 1000,
                    "duration": 3600,  # 1000 requests per hour
                },
                "cache": {
                    "expire_s": 1800,  # 30 minutes
                },
            },
        },
        {
            "pattern": "^/health$",  # Exact match using regex
            "features": {
                "monitoring": {
                    "log_threshold": 0.05,  # Log all health checks > 50ms
                },
            },
        },
    ],
    "default_features": {
        "timeout": 5.0,  # Default 5-second timeout for unmatched paths
        "monitoring": {
            "log_threshold": 0.5,  # Log slow requests by default
        },
    },
}


async def run_example():
    """Run the ASGI gateway example."""
    # Create the gateway
    gateway = create_gateway(config, simple_app)
    
    # In a real application, you'd serve this with an ASGI server like uvicorn:
    # uvicorn example_asgi:gateway --host 0.0.0.0 --port 8000
    
    print("ASGI Gateway created successfully!")
    print(f"Configuration loaded with {len(config['paths'])} path patterns")
    
    # Simulate some requests (for demonstration)
    test_paths = [
        "/api/users/123",
        "/api/admin/settings",
        "/api/public/catalog",
        "/health",
        "/unknown/path",
    ]
    
    for path in test_paths:
        features = gateway._match_path(path)
        print(f"Path '{path}' -> Features: {list(features.keys()) if features else 'default'}")
    
    # Clean up
    await gateway.close()


if __name__ == "__main__":
    asyncio.run(run_example())