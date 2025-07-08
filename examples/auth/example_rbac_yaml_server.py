#!/usr/bin/env python3
"""
Example RBAC server using YAML configuration.

This server demonstrates how to configure RBAC using a YAML file,
showing the declarative approach to defining roles, permissions,
and route access controls.

Run this server with:
    python example_rbac_yaml_server.py

The server will load RBAC configuration from example_rbac_config.yaml
"""

import json
import time
from pathlib import Path

import uvicorn
from premier.asgi import ASGIGateway, GatewayConfig


async def demo_app(scope, receive, send):
    """Demo ASGI application that shows user access info."""
    assert scope["type"] == "http"
    
    path = scope["path"]
    method = scope["method"]
    user_info = scope.get("user", {})
    
    # Create response based on the accessed path
    if path.startswith("/api/admin/"):
        message = "🔐 Admin Area - Administrative functions"
        level = "admin"
        description = "This area requires admin:access permission"
    elif path.startswith("/api/manager/"):
        message = "👨‍💼 Manager Area - Management functions"
        level = "manager"
        description = "This area requires manager:access permission"
    elif path.startswith("/api/users/"):
        if path.endswith("/create"):
            message = "👤 User Creation - Manager function"
            level = "manager"
            description = "This endpoint requires write:users permission"
        elif path.endswith("/profile"):
            message = "👤 User Profile - Personal area"
            level = "user"
            description = "This endpoint requires write:profile permission"
        else:
            message = "👤 User Area - User data access"
            level = "user"
            description = "This area requires read:users permission"
    elif path.startswith("/api/public/"):
        message = "🌐 Public Area - Open access"
        level = "public"
        description = "This area has no specific permission requirements"
    elif path == "/health":
        message = "❤️ Health Check - System status"
        level = "health"
        description = "This endpoint has no authentication requirements"
    else:
        message = "📋 General Access"
        level = "general"
        description = "This endpoint uses default permissions"
    
    response_data = {
        "message": message,
        "level": level,
        "description": description,
        "path": path,
        "method": method,
        "user": user_info,
        "timestamp": time.time(),
        "config_source": "YAML file",
        "rbac_enabled": bool(user_info.get("rbac_enabled", False))
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


def generate_test_tokens():
    """Generate JWT tokens for testing."""
    try:
        import jwt
    except ImportError:
        print("❌ JWT library not installed. Install with: pip install premier[jwt]")
        return {}
    
    secret = "your-secret-key"
    algorithm = "HS256"
    current_time = int(time.time())
    expiration_time = current_time + 3600  # 1 hour
    
    # Define test users with different roles
    users = [
        {
            "sub": "admin_user",
            "name": "Admin User",
            "email": "admin@example.com",
            "role": "admin"
        },
        {
            "sub": "manager_user",
            "name": "Manager User",
            "email": "manager@example.com",
            "role": "manager"
        },
        {
            "sub": "regular_user",
            "name": "Regular User",
            "email": "user@example.com",
            "role": "user"
        },
        {
            "sub": "guest_user",
            "name": "Guest User",
            "email": "guest@example.com",
            "role": "guest"
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
        tokens[user["role"]] = token
    
    return tokens


def print_usage_examples():
    """Print usage examples for testing the YAML RBAC server."""
    print("🚀 YAML RBAC Server Examples")
    print("=" * 50)
    
    print("\n📄 Configuration Source:")
    print("  • example_rbac_config.yaml")
    print("  • Declarative RBAC setup")
    print("  • JWT authentication")
    
    print("\n📋 Available Routes:")
    print("  • /api/admin/settings     - Admin only")
    print("  • /api/manager/dashboard  - Manager only")
    print("  • /api/users/create       - Manager only (write:users)")
    print("  • /api/users/profile      - User level (write:profile)")
    print("  • /api/users/list         - User level (read:users)")
    print("  • /api/public/info        - Public access")
    print("  • /health                 - No auth required")
    
    print("\n🔑 Generate Test Tokens:")
    tokens = generate_test_tokens()
    
    if tokens:
        print("  Test tokens generated successfully!")
        print("  Use these tokens in Authorization header:")
        print("  Authorization: Bearer <token>")
        print()
        
        for role, token in tokens.items():
            print(f"  {role.upper()} TOKEN:")
            print(f"    {token}")
            print(f"    curl -H 'Authorization: Bearer {token}' http://localhost:8002/api/{role}/info")
            print()
    
    print("\n✅ Success Examples:")
    if tokens:
        print(f"  curl -H 'Authorization: Bearer {tokens['admin']}' http://localhost:8002/api/admin/settings")
        print(f"  curl -H 'Authorization: Bearer {tokens['manager']}' http://localhost:8002/api/users/create")
        print(f"  curl -H 'Authorization: Bearer {tokens['user']}' http://localhost:8002/api/users/profile")
        print(f"  curl -H 'Authorization: Bearer {tokens['guest']}' http://localhost:8002/api/public/info")
    
    print("  curl http://localhost:8002/health")
    
    print("\n❌ Access Denied Examples (403 Forbidden):")
    if tokens:
        print(f"  curl -H 'Authorization: Bearer {tokens['user']}' http://localhost:8002/api/admin/settings")
        print(f"  curl -H 'Authorization: Bearer {tokens['guest']}' http://localhost:8002/api/users/create")
    
    print("\n🔍 Authentication Failure Examples (401 Unauthorized):")
    print("  curl -H 'Authorization: Bearer invalid_token' http://localhost:8002/api/users/profile")
    print("  curl http://localhost:8002/api/users/profile")
    
    print("\n💡 YAML Configuration Features:")
    print("  • Declarative role definitions")
    print("  • Permission-based access control")
    print("  • Route-specific permissions")
    print("  • User-role mappings")
    print("  • Default role assignment")
    print("  • Flexible permission matching")


if __name__ == "__main__":
    print("🚀 Starting Premier YAML RBAC Example Server...")
    
    # Check if YAML config file exists
    config_file = Path("example_rbac_config.yaml")
    if not config_file.exists():
        print(f"❌ Configuration file not found: {config_file}")
        print("   Please ensure example_rbac_config.yaml is in the current directory.")
        exit(1)
    
    try:
        # Load configuration from YAML file
        gateway_config = GatewayConfig.from_file(config_file)
        gateway = ASGIGateway(config=gateway_config, app=demo_app)
        
        print("✅ RBAC configuration loaded from YAML file")
        print_usage_examples()
        
        print("\n🌐 Server starting on http://localhost:8002")
        print("🔑 JWT authentication with RBAC from YAML config")
        print("📖 Check the examples above for testing different scenarios")
        print("🛑 Press Ctrl+C to stop the server")
        
        uvicorn.run(gateway, host="0.0.0.0", port=8002, log_level="info")
        
    except FileNotFoundError:
        print(f"❌ Configuration file not found: {config_file}")
        print("   Please ensure example_rbac_config.yaml is in the current directory.")
        exit(1)
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        exit(1)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")