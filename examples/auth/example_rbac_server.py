#!/usr/bin/env python3
"""
Example RBAC server demonstrating Role-Based Access Control with Premier.

This server shows how to configure RBAC with different user roles and permissions.
It includes:
- Admin users with full access
- Manager users with limited management access
- Regular users with basic access
- Guest users with read-only access

Run this server with:
    python example_rbac_server.py

Test with curl:
    # Admin access (full access)
    curl -u admin:adminpass http://localhost:8000/api/admin/settings
    
    # Manager access (can read and manage users)
    curl -u manager:managerpass http://localhost:8000/api/users/create
    
    # Regular user access (can read and edit profile)
    curl -u user:userpass http://localhost:8000/api/users/profile
    
    # Guest access (read-only)
    curl -u guest:guestpass http://localhost:8000/api/public/info
    
    # Access denied examples
    curl -u user:userpass http://localhost:8000/api/admin/settings  # Should return 403
    curl -u guest:guestpass http://localhost:8000/api/users/create  # Should return 403
"""

import uvicorn
from premier.asgi import ASGIGateway, GatewayConfig, PathConfig, FeatureConfig
from premier.features.auth import AuthConfig, RBACConfig, Role


async def demo_app(scope, receive, send):
    """Demo ASGI application that shows user access info."""
    assert scope["type"] == "http"
    
    import json
    import time
    
    path = scope["path"]
    method = scope["method"]
    user_info = scope.get("user", {})
    
    # Create response based on the accessed path
    if path.startswith("/api/admin/"):
        message = "🔐 Admin Area - Sensitive operations available"
        level = "admin"
    elif path.startswith("/api/manager/"):
        message = "👨‍💼 Manager Area - User management functions"
        level = "manager"
    elif path.startswith("/api/users/"):
        message = "👤 User Area - User data and profile"
        level = "user"
    elif path.startswith("/api/public/"):
        message = "🌐 Public Area - General information"
        level = "public"
    else:
        message = "📋 General Access - No specific restrictions"
        level = "general"
    
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
    """Create a comprehensive RBAC configuration."""
    config = RBACConfig()
    
    # Define roles with their permissions
    admin_role = Role(name="admin", description="System Administrator")
    admin_role.add_permission("*:*")  # Full access
    
    manager_role = Role(name="manager", description="User Manager")
    manager_role.add_permission("read:*")  # Can read everything
    manager_role.add_permission("write:users")  # Can create/modify users
    manager_role.add_permission("write:reports")  # Can create reports
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
    
    # Define user-role mappings
    config.add_user_role("admin", "admin")
    config.add_user_role("manager", "manager")
    config.add_user_role("user", "user")
    config.add_user_role("guest", "guest")
    
    # Define route permissions
    config.add_route_permission("/api/admin/.*", "admin:access")
    config.add_route_permission("/api/manager/.*", "manager:access")
    config.add_route_permission("/api/users/.*", "read:users")
    config.add_route_permission("/api/users/create", "write:users")
    config.add_route_permission("/api/users/profile", "write:profile")
    config.add_route_permission("/api/reports/.*", "read:reports")
    config.add_route_permission("/api/reports/create", "write:reports")
    
    # Public routes don't require specific permissions
    # Routes without specific permissions are accessible to authenticated users
    
    # Set default role for users without explicit role assignment
    config.default_role = "guest"
    
    return config


def create_multi_user_gateway():
    """Create a gateway that supports multiple users with different roles."""
    rbac_config = create_rbac_config()
    
    # Create different auth configs for different users
    # In a real application, you'd use a database or identity provider
    auth_configs = {
        "admin": AuthConfig(
            type="basic",
            username="admin",
            password="adminpass",
            rbac=rbac_config
        ),
        "manager": AuthConfig(
            type="basic",
            username="manager",
            password="managerpass",
            rbac=rbac_config
        ),
        "user": AuthConfig(
            type="basic",
            username="user",
            password="userpass",
            rbac=rbac_config
        ),
        "guest": AuthConfig(
            type="basic",
            username="guest",
            password="guestpass",
            rbac=rbac_config
        )
    }
    
    # Define paths with different access levels
    paths = [
        # Admin routes - require admin access
        PathConfig(
            pattern="/api/admin/.*",
            features=FeatureConfig(auth=auth_configs["admin"])
        ),
        
        # Manager routes - require manager access
        PathConfig(
            pattern="/api/manager/.*",
            features=FeatureConfig(auth=auth_configs["manager"])
        ),
        
        # User creation - manager only
        PathConfig(
            pattern="/api/users/create",
            features=FeatureConfig(auth=auth_configs["manager"])
        ),
        
        # User profile - user access
        PathConfig(
            pattern="/api/users/profile",
            features=FeatureConfig(auth=auth_configs["user"])
        ),
        
        # General user routes - user access
        PathConfig(
            pattern="/api/users/.*",
            features=FeatureConfig(auth=auth_configs["user"])
        ),
        
        # Report creation - manager only
        PathConfig(
            pattern="/api/reports/create",
            features=FeatureConfig(auth=auth_configs["manager"])
        ),
        
        # Report reading - user access
        PathConfig(
            pattern="/api/reports/.*",
            features=FeatureConfig(auth=auth_configs["user"])
        ),
        
        # Public routes - guest access
        PathConfig(
            pattern="/api/public/.*",
            features=FeatureConfig(auth=auth_configs["guest"])
        ),
        
        # Health check - no auth required
        PathConfig(
            pattern="/health",
            features=FeatureConfig()
        ),
    ]
    
    gateway_config = GatewayConfig(paths=paths)
    return ASGIGateway(config=gateway_config, app=demo_app)


def create_unified_auth_gateway():
    """Create a gateway with unified authentication and RBAC authorization."""
    rbac_config = create_rbac_config()
    
    # This demonstrates a more realistic setup where all users authenticate
    # with the same system, but RBAC controls what they can access
    
    # In a real system, you'd extend BasicAuth to support multiple users
    # For demo purposes, we'll use admin credentials but show RBAC in action
    auth_config = AuthConfig(
        type="basic",
        username="admin",  # All users use this for demo
        password="adminpass",
        rbac=rbac_config
    )
    
    protected_features = FeatureConfig(auth=auth_config)
    public_features = FeatureConfig()
    
    paths = [
        # All API routes require authentication
        PathConfig(
            pattern="/api/.*",
            features=protected_features
        ),
        
        # Health check - no auth required
        PathConfig(
            pattern="/health",
            features=public_features
        ),
    ]
    
    gateway_config = GatewayConfig(paths=paths)
    return ASGIGateway(config=gateway_config, app=demo_app)


def print_usage_examples():
    """Print usage examples for testing the RBAC server."""
    print("🚀 RBAC Server Examples")
    print("=" * 50)
    
    print("\n📋 Available Routes:")
    print("  • /api/admin/settings     - Admin only")
    print("  • /api/admin/users        - Admin only")
    print("  • /api/manager/dashboard  - Manager only")
    print("  • /api/users/create       - Manager only")
    print("  • /api/users/profile      - User level")
    print("  • /api/users/list         - User level")
    print("  • /api/reports/create     - Manager only")
    print("  • /api/reports/view       - User level")
    print("  • /api/public/info        - Guest level")
    print("  • /health                 - Public (no auth)")
    
    print("\n🔐 User Credentials:")
    print("  • admin:adminpass    - Full access")
    print("  • manager:managerpass - Management access")
    print("  • user:userpass      - User access")
    print("  • guest:guestpass    - Read-only access")
    
    print("\n✅ Success Examples:")
    print("  curl -u admin:adminpass http://localhost:8000/api/admin/settings")
    print("  curl -u manager:managerpass http://localhost:8000/api/users/create")
    print("  curl -u user:userpass http://localhost:8000/api/users/profile")
    print("  curl -u guest:guestpass http://localhost:8000/api/public/info")
    print("  curl http://localhost:8000/health")
    
    print("\n❌ Access Denied Examples (403 Forbidden):")
    print("  curl -u user:userpass http://localhost:8000/api/admin/settings")
    print("  curl -u guest:guestpass http://localhost:8000/api/users/create")
    print("  curl -u user:userpass http://localhost:8000/api/manager/dashboard")
    
    print("\n🔍 Authentication Failure Examples (401 Unauthorized):")
    print("  curl -u wrong:wrong http://localhost:8000/api/users/profile")
    print("  curl http://localhost:8000/api/users/profile")
    
    print("\n💡 Tips:")
    print("  • Use -v flag with curl to see HTTP status codes")
    print("  • Try different user credentials on the same endpoint")
    print("  • Notice the difference between 401 (auth failed) and 403 (access denied)")
    print("  • Check the response JSON to see user roles and permissions")


if __name__ == "__main__":
    print("🚀 Starting Premier RBAC Example Server...")
    print_usage_examples()
    
    # Create the gateway with RBAC
    # You can switch between create_multi_user_gateway() and create_unified_auth_gateway()
    gateway = create_multi_user_gateway()
    
    print("\n🌐 Server starting on http://localhost:8000")
    print("🔑 RBAC is enabled with role-based access control")
    print("📖 Check the examples above for testing different scenarios")
    print("🛑 Press Ctrl+C to stop the server")
    
    try:
        uvicorn.run(gateway, host="0.0.0.0", port=8000, log_level="info")
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")