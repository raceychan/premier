#!/usr/bin/env python3
"""
Example JWT RBAC server demonstrating Role-Based Access Control with JWT authentication.

This server shows how to configure RBAC with JWT tokens containing role information.
It includes:
- JWT token generation for different user roles
- Role-based access control
- Token validation and authorization

Run this server with:
    python example_jwt_rbac_server.py

The server will generate JWT tokens for different users and show how to use them.
"""

import json
import time
from typing import Dict, Any

import uvicorn
from premier.asgi import ASGIGateway, GatewayConfig, PathConfig, FeatureConfig
from premier.features.auth import AuthConfig, RBACConfig, Role


async def demo_app(scope, receive, send):
    """Demo ASGI application that shows user access info."""
    assert scope["type"] == "http"
    
    path = scope["path"]
    method = scope["method"]
    user_info = scope.get("user", {})
    
    # Create response based on the accessed path
    if path.startswith("/api/admin/"):
        message = "🔐 Admin Area - Full system access"
        level = "admin"
    elif path.startswith("/api/manager/"):
        message = "👨‍💼 Manager Area - User and content management"
        level = "manager"
    elif path.startswith("/api/users/"):
        message = "👤 User Area - Personal data and profile"
        level = "user"
    elif path.startswith("/api/public/"):
        message = "🌐 Public Area - General information"
        level = "public"
    elif path == "/tokens":
        message = "🔑 Token Generator - Get JWT tokens for testing"
        level = "token"
    else:
        message = "📋 General Access"
        level = "general"
    
    # Special handling for token generation endpoint
    if path == "/tokens":
        tokens = generate_test_tokens()
        response_data = {
            "message": message,
            "tokens": tokens,
            "usage": {
                "description": "Use these tokens in Authorization header",
                "format": "Authorization: Bearer <token>",
                "example": "curl -H 'Authorization: Bearer <admin_token>' http://localhost:8001/api/admin/settings"
            },
            "timestamp": time.time()
        }
    else:
        response_data = {
            "message": message,
            "level": level,
            "path": path,
            "method": method,
            "user": user_info,
            "timestamp": time.time(),
            "access_granted": True
        }
    
    body = json.dumps(response_data, indent=2).encode()
    
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [
            [b"content-type", b"application/json"],
            [b"access-control-allow-origin", b"*"],
        ],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })


def create_rbac_config():
    """Create RBAC configuration for JWT-based authentication."""
    config = RBACConfig()
    
    # Define roles with their permissions
    admin_role = Role(name="admin", description="System Administrator")
    admin_role.add_permission("*:*")  # Full access
    
    manager_role = Role(name="manager", description="Content Manager")
    manager_role.add_permission("read:*")  # Can read everything
    manager_role.add_permission("write:users")  # Can manage users
    manager_role.add_permission("write:content")  # Can manage content
    manager_role.add_permission("manager:access")  # Can access manager area
    
    user_role = Role(name="user", description="Regular User")
    user_role.add_permission("read:users")  # Can read user data
    user_role.add_permission("write:profile")  # Can edit own profile
    user_role.add_permission("read:public")  # Can read public content
    
    guest_role = Role(name="guest", description="Guest User")
    guest_role.add_permission("read:public")  # Can only read public content
    
    # Add roles to config
    config.add_role(admin_role)
    config.add_role(manager_role)
    config.add_role(user_role)
    config.add_role(guest_role)
    
    # Define user-role mappings (based on JWT 'sub' claim)
    config.add_user_role("admin_user", "admin")
    config.add_user_role("manager_user", "manager")
    config.add_user_role("regular_user", "user")
    config.add_user_role("guest_user", "guest")
    
    # Define route permissions
    config.add_route_permission("/api/admin/.*", "admin:access")
    config.add_route_permission("/api/manager/.*", "manager:access")
    config.add_route_permission("/api/users/.*", "read:users")
    config.add_route_permission("/api/users/create", "write:users")
    config.add_route_permission("/api/users/profile", "write:profile")
    config.add_route_permission("/api/content/.*", "read:content")
    config.add_route_permission("/api/content/create", "write:content")
    
    # Set default role
    config.default_role = "guest"
    
    return config


def generate_test_tokens() -> Dict[str, Any]:
    """Generate JWT tokens for testing different user roles."""
    try:
        import jwt
    except ImportError:
        return {
            "error": "JWT library not installed. Install with: pip install premier[jwt]"
        }
    
    secret = "jwt_rbac_secret_key"
    algorithm = "HS256"
    current_time = int(time.time())
    expiration_time = current_time + 3600  # 1 hour
    
    # Define test users with different roles
    users = [
        {
            "sub": "admin_user",
            "name": "Admin User",
            "email": "admin@example.com",
            "role": "admin",
            "description": "Full system access"
        },
        {
            "sub": "manager_user",
            "name": "Manager User",
            "email": "manager@example.com",
            "role": "manager",
            "description": "Can manage users and content"
        },
        {
            "sub": "regular_user",
            "name": "Regular User",
            "email": "user@example.com",
            "role": "user",
            "description": "Can access user functions"
        },
        {
            "sub": "guest_user",
            "name": "Guest User",
            "email": "guest@example.com",
            "role": "guest",
            "description": "Read-only access"
        }
    ]
    
    tokens = {}
    
    for user in users:
        payload = {
            "sub": user["sub"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "iat": current_time,
            "exp": expiration_time,
            "iss": "premier-rbac-example",
            "aud": "premier-api"
        }
        
        token = jwt.encode(payload, secret, algorithm=algorithm)
        
        tokens[user["role"]] = {
            "token": token,
            "user": user,
            "expires_at": expiration_time,
            "curl_example": f"curl -H 'Authorization: Bearer {token}' http://localhost:8001/api/{user['role']}/info"
        }
    
    return tokens


def create_jwt_gateway():
    """Create a gateway with JWT authentication and RBAC."""
    rbac_config = create_rbac_config()
    
    # JWT authentication configuration
    auth_config = AuthConfig(
        type="jwt",
        secret="jwt_rbac_secret_key",
        algorithm="HS256",
        audience="premier-api",
        issuer="premier-rbac-example",
        verify_signature=True,
        verify_exp=True,
        verify_nbf=True,
        verify_iat=True,
        verify_aud=True,
        verify_iss=True,
        rbac=rbac_config
    )
    
    protected_features = FeatureConfig(auth=auth_config)
    public_features = FeatureConfig()
    
    paths = [
        # All API routes require JWT authentication
        PathConfig(
            pattern="/api/.*",
            features=protected_features
        ),
        
        # Token generation endpoint - public
        PathConfig(
            pattern="/tokens",
            features=public_features
        ),
        
        # Health check - public
        PathConfig(
            pattern="/health",
            features=public_features
        ),
    ]
    
    gateway_config = GatewayConfig(paths=paths)
    return ASGIGateway(config=gateway_config, app=demo_app)


def print_usage_examples():
    """Print usage examples for testing the JWT RBAC server."""
    print("🚀 JWT RBAC Server Examples")
    print("=" * 50)
    
    print("\n📋 Available Routes:")
    print("  • /tokens                 - Get JWT tokens (public)")
    print("  • /api/admin/settings     - Admin only")
    print("  • /api/admin/users        - Admin only")
    print("  • /api/manager/dashboard  - Manager only")
    print("  • /api/users/create       - Manager only")
    print("  • /api/users/profile      - User level")
    print("  • /api/users/list         - User level")
    print("  • /api/content/create     - Manager only")
    print("  • /api/content/view       - User level")
    print("  • /api/public/info        - Guest level")
    print("  • /health                 - Public (no auth)")
    
    print("\n🔑 Get JWT Tokens:")
    print("  curl http://localhost:8001/tokens")
    print("  # This will return JWT tokens for different user roles")
    
    print("\n✅ Usage Pattern:")
    print("  1. Get tokens: curl http://localhost:8001/tokens")
    print("  2. Copy a token from the response")
    print("  3. Use it in Authorization header:")
    print("     curl -H 'Authorization: Bearer <token>' http://localhost:8001/api/admin/settings")
    
    print("\n🎯 Test Scenarios:")
    print("  • Admin token -> /api/admin/settings (✅ 200)")
    print("  • Manager token -> /api/users/create (✅ 200)")
    print("  • User token -> /api/users/profile (✅ 200)")
    print("  • Guest token -> /api/public/info (✅ 200)")
    print("  • User token -> /api/admin/settings (❌ 403)")
    print("  • Guest token -> /api/users/create (❌ 403)")
    print("  • Invalid token -> any protected route (❌ 401)")
    print("  • No token -> any protected route (❌ 401)")
    
    print("\n💡 JWT Token Structure:")
    print("  • sub: User identifier (used for RBAC mapping)")
    print("  • name: User display name")
    print("  • email: User email address")
    print("  • role: User role (for reference)")
    print("  • iat: Issued at timestamp")
    print("  • exp: Expiration timestamp")
    print("  • iss: Issuer (premier-rbac-example)")
    print("  • aud: Audience (premier-api)")
    
    print("\n🔍 Advanced Testing:")
    print("  # Test with expired token (wait 1 hour or modify exp claim)")
    print("  # Test with invalid signature (modify secret)")
    print("  # Test with wrong audience/issuer")
    print("  # Test different HTTP methods (GET, POST, PUT, DELETE)")


if __name__ == "__main__":
    print("🚀 Starting Premier JWT RBAC Example Server...")
    print_usage_examples()
    
    # Create the gateway with JWT + RBAC
    gateway = create_jwt_gateway()
    
    print("\n🌐 Server starting on http://localhost:8001")
    print("🔑 JWT authentication with RBAC is enabled")
    print("📖 Get tokens from: http://localhost:8001/tokens")
    print("🛑 Press Ctrl+C to stop the server")
    
    try:
        uvicorn.run(gateway, host="0.0.0.0", port=8001, log_level="info")
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")