#!/usr/bin/env python3
"""
Example ASGI server with authentication enabled.

This example demonstrates how to use the premier auth feature with a real ASGI application.
You can test it with curl commands to verify authentication works.

Usage:
    python example_auth_server.py

Then in another terminal:
    # Test Basic Auth
    curl -H "Authorization: Basic dGVzdHVzZXI6dGVzdHBhc3M=" http://localhost:8000/api/protected
    
    # Test without auth (should fail)
    curl http://localhost:8000/api/protected
    
    # Test public endpoint (no auth required)
    curl http://localhost:8000/public/info
"""

import asyncio
import json
from premier.asgi import ASGIGateway, GatewayConfig, AuthConfig, PathConfig, FeatureConfig


async def demo_app(scope, receive, send):
    """Demo ASGI application that shows user info."""
    assert scope["type"] == "http"
    
    path = scope["path"]
    method = scope["method"]
    
    # Get user info from scope (added by auth middleware)
    user_info = scope.get("user", {})
    
    # Prepare response based on path
    if path.startswith("/api/"):
        # Protected API endpoints
        response_data = {
            "message": "Welcome to the protected API!",
            "user": user_info,
            "path": path,
            "method": method
        }
    elif path.startswith("/public/"):
        # Public endpoints
        response_data = {
            "message": "This is a public endpoint",
            "path": path,
            "method": method,
            "auth_required": False
        }
    else:
        # Default response
        response_data = {
            "message": "Premier Auth Demo",
            "endpoints": {
                "/api/protected": "Protected endpoint (requires auth)",
                "/public/info": "Public endpoint (no auth required)"
            }
        }
    
    # Send response
    body = json.dumps(response_data, indent=2).encode()
    
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [[b"content-type", b"application/json"]],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })


def create_auth_gateway():
    """Create ASGI Gateway with authentication configuration."""
    
    # Configure Basic Auth for API endpoints
    basic_auth_config = AuthConfig(
        type="basic",
        username="testuser",
        password="testpass"
    )
    
    # Create feature configuration with auth
    protected_features = FeatureConfig(auth=basic_auth_config)
    public_features = FeatureConfig()  # No auth required
    
    # Configure path-based routing
    paths = [
        PathConfig(pattern="/api/.*", features=protected_features),
        PathConfig(pattern="/public/.*", features=public_features),
    ]
    
    # Create gateway configuration
    gateway_config = GatewayConfig(paths=paths)
    
    # Create and return gateway
    return ASGIGateway(config=gateway_config, app=demo_app)


async def run_server():
    """Run the demo server."""
    try:
        import uvicorn
        
        # Create the ASGI app
        app = create_auth_gateway()
        
        print("🚀 Starting Premier Auth Demo Server...")
        print("📍 Server running at: http://localhost:8000")
        print("\n📚 Test Commands:")
        print("  # Test with valid Basic Auth:")
        print("  curl -H \"Authorization: Basic dGVzdHVzZXI6dGVzdHBhc3M=\" http://localhost:8000/api/protected")
        print("\n  # Test without auth (should return 401):")
        print("  curl http://localhost:8000/api/protected")
        print("\n  # Test public endpoint (no auth required):")
        print("  curl http://localhost:8000/public/info")
        print("\n  # Test root endpoint:")
        print("  curl http://localhost:8000/")
        print("\n💡 Basic Auth credentials: testuser:testpass")
        print("   Base64 encoded: dGVzdHVzZXI6dGVzdHBhc3M=")
        print("\n🛑 Press Ctrl+C to stop the server")
        
        # Run the server
        config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
        
    except ImportError:
        print("❌ uvicorn is required to run this example.")
        print("Install with: pip install uvicorn")
        return
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")


if __name__ == "__main__":
    asyncio.run(run_server())