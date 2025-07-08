#!/usr/bin/env python3
"""
Example ASGI server with JWT authentication enabled.

This example demonstrates how to use the premier JWT auth feature with a real ASGI application.
You can test it with curl commands to verify JWT authentication works.

Usage:
    python example_jwt_server.py

Then in another terminal:
    # Generate a JWT token first (you'll need to install pyjwt):
    python -c "import jwt; print(jwt.encode({'sub': 'user123', 'name': 'Test User'}, 'mysecret', algorithm='HS256'))"
    
    # Test with valid JWT:
    curl -H "Authorization: Bearer YOUR_JWT_TOKEN" http://localhost:8001/api/protected
    
    # Test without auth (should fail):
    curl http://localhost:8001/api/protected
    
    # Test public endpoint (no auth required):
    curl http://localhost:8001/public/info
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
            "message": "Welcome to the JWT protected API!",
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
        # Default response with JWT generation example
        response_data = {
            "message": "Premier JWT Auth Demo",
            "endpoints": {
                "/api/protected": "Protected endpoint (requires JWT)",
                "/public/info": "Public endpoint (no auth required)"
            },
            "jwt_generation_example": {
                "secret": "mysecret",
                "algorithm": "HS256",
                "python_command": "python -c \"import jwt; print(jwt.encode({'sub': 'user123', 'name': 'Test User'}, 'mysecret', algorithm='HS256'))\""
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


def create_jwt_gateway():
    """Create ASGI Gateway with JWT authentication configuration."""
    
    # Configure JWT Auth for API endpoints
    jwt_auth_config = AuthConfig(
        type="jwt",
        secret="mysecret",
        algorithm="HS256"
    )
    
    # Create feature configuration with auth
    protected_features = FeatureConfig(auth=jwt_auth_config)
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


def generate_sample_jwt():
    """Generate a sample JWT token for testing."""
    try:
        import jwt
        
        payload = {
            "sub": "user123",
            "name": "Test User",
            "email": "test@example.com",
            "iat": 1234567890,
            "exp": 9999999999  # Far future expiration
        }
        
        token = jwt.encode(payload, "mysecret", algorithm="HS256")
        return token
        
    except ImportError:
        return None


async def run_server():
    """Run the demo server."""
    try:
        import uvicorn
        
        # Create the ASGI app
        app = create_jwt_gateway()
        
        print("🚀 Starting Premier JWT Auth Demo Server...")
        print("📍 Server running at: http://localhost:8001")
        
        # Try to generate a sample JWT
        sample_token = generate_sample_jwt()
        
        print("\n📚 Test Commands:")
        
        if sample_token:
            print(f"  # Test with valid JWT:")
            print(f"  curl -H \"Authorization: Bearer {sample_token}\" http://localhost:8001/api/protected")
        else:
            print("  # First, generate a JWT token:")
            print("  python -c \"import jwt; print(jwt.encode({'sub': 'user123', 'name': 'Test User'}, 'mysecret', algorithm='HS256'))\"")
            print("  # Then test with the generated token:")
            print("  curl -H \"Authorization: Bearer YOUR_JWT_TOKEN\" http://localhost:8001/api/protected")
        
        print("\n  # Test without auth (should return 401):")
        print("  curl http://localhost:8001/api/protected")
        print("\n  # Test public endpoint (no auth required):")
        print("  curl http://localhost:8001/public/info")
        print("\n  # Test root endpoint:")
        print("  curl http://localhost:8001/")
        
        print("\n💡 JWT Configuration:")
        print("   Secret: mysecret")
        print("   Algorithm: HS256")
        
        if not sample_token:
            print("\n⚠️  Install pyjwt to generate test tokens:")
            print("   pip install premier[jwt]")
        
        print("\n🛑 Press Ctrl+C to stop the server")
        
        # Run the server
        config = uvicorn.Config(app, host="0.0.0.0", port=8001, log_level="info")
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