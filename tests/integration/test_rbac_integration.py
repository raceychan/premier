#!/usr/bin/env python3
"""
Integration tests for RBAC with Premier Gateway.

This test suite covers the integration of RBAC with the authentication
system and ASGI gateway, testing real-world scenarios.
"""

import base64
import json
import time
from typing import Dict, Any

import pytest
from premier.asgi import ASGIGateway, GatewayConfig, PathConfig, FeatureConfig
from premier.features.auth import AuthConfig
from premier.features.auth.rbac import RBACConfig, Role, Permission


class TestRBACIntegration:
    """Integration tests for RBAC with authentication and gateway."""
    
    async def demo_app(self, scope, receive, send):
        """Demo ASGI app that shows user info."""
        assert scope["type"] == "http"
        
        path = scope["path"]
        method = scope["method"]
        user_info = scope.get("user", {})
        
        response_data = {
            "message": f"Access granted to {path}",
            "user": user_info,
            "path": path,
            "method": method,
            "timestamp": time.time(),
        }
        
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
    
    def create_rbac_config(self) -> RBACConfig:
        """Create a comprehensive RBAC configuration."""
        config = RBACConfig()
        
        # Create roles with permissions
        admin_role = Role(name="admin", description="System Administrator")
        admin_role.add_permission("*:*")  # Admin can do everything
        
        manager_role = Role(name="manager", description="Manager")
        manager_role.add_permission("read:*")
        manager_role.add_permission("write:users")
        manager_role.add_permission("write:reports")
        manager_role.add_permission("manager:access")
        
        user_role = Role(name="user", description="Regular User")
        user_role.add_permission("read:api")
        user_role.add_permission("read:users")
        user_role.add_permission("write:profile")
        
        guest_role = Role(name="guest", description="Guest User")
        guest_role.add_permission("read:public")
        
        # Add roles to config
        config.add_role(admin_role)
        config.add_role(manager_role)
        config.add_role(user_role)
        config.add_role(guest_role)
        
        # Assign roles to users
        config.add_user_role("admin", "admin")
        config.add_user_role("manager", "manager")
        config.add_user_role("manager_user", "manager")
        config.add_user_role("user", "user")
        config.add_user_role("regular_user", "user")
        config.add_user_role("guest", "guest")
        
        # Define route permissions
        config.add_route_permission("/api/admin/.*", "admin:access")
        config.add_route_permission("/api/manager/.*", "manager:access")
        config.add_route_permission("/api/users/.*", "read:users")
        config.add_route_permission("/api/users/create", "write:users")
        config.add_route_permission("/api/profile/.*", "write:profile")
        config.add_route_permission("/api/reports/.*", "read:reports")
        config.add_route_permission("/api/reports/create", "write:reports")
        
        # Set default role
        config.default_role = "guest"
        
        return config
    
    def create_basic_auth_gateway_with_rbac(self) -> ASGIGateway:
        """Create gateway with Basic Auth and RBAC."""
        rbac_config = self.create_rbac_config()
        
        # Create a single auth config that accepts multiple users
        # In a real system, this would be a database lookup or similar
        # For testing, we'll create a simple multi-user auth config
        auth_config = AuthConfig(
            type="basic",
            username="admin",  # This will be overridden by custom auth handler
            password="adminpass",
            rbac=rbac_config
        )
        
        protected_features = FeatureConfig(auth=auth_config)
        public_features = FeatureConfig()
        
        paths = [
            # All protected paths use the same auth config
            PathConfig(
                pattern="/api/admin/.*",
                features=protected_features
            ),
            PathConfig(
                pattern="/api/manager/.*",
                features=protected_features
            ),
            PathConfig(
                pattern="/api/users/.*",
                features=protected_features
            ),
            PathConfig(
                pattern="/api/profile/.*",
                features=protected_features
            ),
            PathConfig(
                pattern="/api/reports/.*",
                features=protected_features
            ),
            PathConfig(
                pattern="/api/general/.*",
                features=protected_features
            ),
            # Public paths (no auth)
            PathConfig(
                pattern="/api/public/.*",
                features=public_features
            ),
        ]
        
        gateway_config = GatewayConfig(paths=paths)
        return ASGIGateway(config=gateway_config, app=self.demo_app)
    
    def create_jwt_auth_gateway_with_rbac(self) -> ASGIGateway:
        """Create gateway with JWT Auth and RBAC."""
        rbac_config = self.create_rbac_config()
        
        auth_config = AuthConfig(
            type="jwt",
            secret="test_secret_key",
            algorithm="HS256",
            rbac=rbac_config
        )
        
        protected_features = FeatureConfig(auth=auth_config)
        public_features = FeatureConfig()
        
        paths = [
            PathConfig(pattern="/api/admin/.*", features=protected_features),
            PathConfig(pattern="/api/manager/.*", features=protected_features),
            PathConfig(pattern="/api/users/.*", features=protected_features),
            PathConfig(pattern="/api/profile/.*", features=protected_features),
            PathConfig(pattern="/api/reports/.*", features=protected_features),
            PathConfig(pattern="/api/public/.*", features=public_features),
        ]
        
        gateway_config = GatewayConfig(paths=paths)
        return ASGIGateway(config=gateway_config, app=self.demo_app)
    
    async def make_request(self, gateway, path, headers=None):
        """Helper to make ASGI request and get response."""
        headers = headers or []
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": headers,
        }
        
        received_messages = []
        
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        
        async def send(message):
            received_messages.append(message)
        
        await gateway(scope, receive, send)
        
        # Extract status and body
        status = received_messages[0]["status"]
        body = received_messages[1]["body"].decode()
        
        return status, body, scope
    
    @pytest.mark.asyncio
    async def test_admin_access_to_admin_routes(self):
        """Test that admin can access admin routes."""
        gateway = self.create_basic_auth_gateway_with_rbac()
        
        # Admin credentials
        credentials = base64.b64encode(b"admin:adminpass").decode()
        headers = [[b"authorization", f"Basic {credentials}".encode()]]
        
        status, body, scope = await self.make_request(gateway, "/api/admin/users", headers)
        
        assert status == 200
        response_data = json.loads(body)
        assert response_data["message"] == "Access granted to /api/admin/users"
        assert response_data["user"]["username"] == "admin"
        assert "admin" in response_data["user"]["roles"]
        assert response_data["user"]["rbac_enabled"] is True
    
    @pytest.mark.asyncio
    async def test_user_denied_access_to_admin_routes(self):
        """Test that regular user cannot access admin routes."""
        rbac_config = self.create_rbac_config()
        
        # Create auth config with a user that has limited permissions
        auth_config = AuthConfig(
            type="basic",
            username="regular_user",
            password="userpass",
            rbac=rbac_config
        )
        
        protected_features = FeatureConfig(auth=auth_config)
        
        paths = [
            PathConfig(
                pattern="/api/.*",
                features=protected_features
            ),
        ]
        
        gateway_config = GatewayConfig(paths=paths)
        gateway = ASGIGateway(config=gateway_config, app=self.demo_app)
        
        # User credentials
        credentials = base64.b64encode(b"regular_user:userpass").decode()
        headers = [[b"authorization", f"Basic {credentials}".encode()]]
        
        status, body, scope = await self.make_request(gateway, "/api/admin/users", headers)
        
        assert status == 403  # Forbidden
        assert "Access denied" in body
        assert "regular_user" in body
        assert "/api/admin/users" in body
    
    @pytest.mark.asyncio
    async def test_manager_access_to_manager_routes(self):
        """Test that manager can access manager routes."""
        rbac_config = self.create_rbac_config()
        
        # Create auth config with manager permissions
        auth_config = AuthConfig(
            type="basic",
            username="manager_user",
            password="managerpass",
            rbac=rbac_config
        )
        
        protected_features = FeatureConfig(auth=auth_config)
        
        paths = [
            PathConfig(
                pattern="/api/.*",
                features=protected_features
            ),
        ]
        
        gateway_config = GatewayConfig(paths=paths)
        gateway = ASGIGateway(config=gateway_config, app=self.demo_app)
        
        # Manager credentials
        credentials = base64.b64encode(b"manager_user:managerpass").decode()
        headers = [[b"authorization", f"Basic {credentials}".encode()]]
        
        status, body, scope = await self.make_request(gateway, "/api/manager/dashboard", headers)
        
        assert status == 200
        response_data = json.loads(body)
        assert response_data["user"]["username"] == "manager_user"
        assert "manager" in response_data["user"]["roles"]
    
    @pytest.mark.asyncio
    async def test_user_access_to_user_routes(self):
        """Test that user can access user routes."""
        rbac_config = self.create_rbac_config()
        
        auth_config = AuthConfig(
            type="basic",
            username="user",
            password="userpass",
            rbac=rbac_config
        )
        
        protected_features = FeatureConfig(auth=auth_config)
        
        paths = [
            PathConfig(
                pattern="/api/.*",
                features=protected_features
            ),
        ]
        
        gateway_config = GatewayConfig(paths=paths)
        gateway = ASGIGateway(config=gateway_config, app=self.demo_app)
        
        # User credentials
        credentials = base64.b64encode(b"user:userpass").decode()
        headers = [[b"authorization", f"Basic {credentials}".encode()]]
        
        status, body, scope = await self.make_request(gateway, "/api/users/profile", headers)
        
        assert status == 200
        response_data = json.loads(body)
        assert response_data["user"]["username"] == "user"
        assert "user" in response_data["user"]["roles"]
        assert "read:users" in response_data["user"]["permissions"]
    
    @pytest.mark.asyncio
    async def test_public_route_access(self):
        """Test that public routes don't require authentication."""
        gateway = self.create_basic_auth_gateway_with_rbac()
        
        # No credentials
        status, body, scope = await self.make_request(gateway, "/api/public/info")
        
        assert status == 200
        response_data = json.loads(body)
        assert response_data["message"] == "Access granted to /api/public/info"
        assert "user" not in scope  # No authentication required
    
    @pytest.mark.asyncio
    async def test_jwt_rbac_integration(self):
        """Test RBAC integration with JWT authentication."""
        try:
            import jwt
        except ImportError:
            pytest.skip("pyjwt not installed")
        
        gateway = self.create_jwt_auth_gateway_with_rbac()
        
        # Create JWT token for admin user
        payload = {
            "sub": "admin",
            "name": "Administrator",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        
        token = jwt.encode(payload, "test_secret_key", algorithm="HS256")
        headers = [[b"authorization", f"Bearer {token}".encode()]]
        
        # Admin should be able to access admin routes
        status, body, scope = await self.make_request(gateway, "/api/admin/settings", headers)
        
        assert status == 200
        response_data = json.loads(body)
        assert response_data["user"]["sub"] == "admin"
        assert "admin" in response_data["user"]["roles"]
        assert response_data["user"]["rbac_enabled"] is True
    
    @pytest.mark.asyncio
    async def test_jwt_rbac_access_denied(self):
        """Test RBAC access denied with JWT authentication."""
        try:
            import jwt
        except ImportError:
            pytest.skip("pyjwt not installed")
        
        rbac_config = self.create_rbac_config()
        
        auth_config = AuthConfig(
            type="jwt",
            secret="test_secret_key",
            algorithm="HS256",
            rbac=rbac_config
        )
        
        protected_features = FeatureConfig(auth=auth_config)
        
        paths = [
            PathConfig(
                pattern="/api/.*",
                features=protected_features
            ),
        ]
        
        gateway_config = GatewayConfig(paths=paths)
        gateway = ASGIGateway(config=gateway_config, app=self.demo_app)
        
        # Create JWT token for regular user
        payload = {
            "sub": "regular_user",
            "name": "Regular User",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        
        token = jwt.encode(payload, "test_secret_key", algorithm="HS256")
        headers = [[b"authorization", f"Bearer {token}".encode()]]
        
        # User should not be able to access admin routes
        status, body, scope = await self.make_request(gateway, "/api/admin/settings", headers)
        
        assert status == 403  # Forbidden
        assert "Access denied" in body
        assert "regular_user" in body
    
    @pytest.mark.asyncio
    async def test_rbac_with_wildcard_permissions(self):
        """Test RBAC with wildcard permissions."""
        rbac_config = self.create_rbac_config()
        
        auth_config = AuthConfig(
            type="basic",
            username="manager_user",
            password="managerpass",
            rbac=rbac_config
        )
        
        protected_features = FeatureConfig(auth=auth_config)
        
        paths = [
            PathConfig(
                pattern="/api/.*",
                features=protected_features
            ),
        ]
        
        gateway_config = GatewayConfig(paths=paths)
        gateway = ASGIGateway(config=gateway_config, app=self.demo_app)
        
        # Manager has read:* permission
        credentials = base64.b64encode(b"manager_user:managerpass").decode()
        headers = [[b"authorization", f"Basic {credentials}".encode()]]
        
        # Manager should be able to access routes requiring read permissions
        status, body, scope = await self.make_request(gateway, "/api/users/list", headers)
        
        assert status == 200
        response_data = json.loads(body)
        assert response_data["user"]["username"] == "manager_user"
        assert "read:*" in response_data["user"]["permissions"]  # Wildcard permission
        assert "write:users" in response_data["user"]["permissions"]
    
    @pytest.mark.asyncio
    async def test_rbac_multiple_roles(self):
        """Test RBAC with users having multiple roles."""
        rbac_config = self.create_rbac_config()
        
        # Give user both user and manager roles
        rbac_config.add_user_role("user", "manager")
        
        auth_config = AuthConfig(
            type="basic",
            username="user",
            password="userpass",
            rbac=rbac_config
        )
        
        paths = [
            PathConfig(
                pattern="/api/.*",
                features=FeatureConfig(auth=auth_config)
            ),
        ]
        
        gateway_config = GatewayConfig(paths=paths)
        gateway = ASGIGateway(config=gateway_config, app=self.demo_app)
        
        credentials = base64.b64encode(b"user:userpass").decode()
        headers = [[b"authorization", f"Basic {credentials}".encode()]]
        
        status, body, scope = await self.make_request(gateway, "/api/reports/create", headers)
        
        assert status == 200
        response_data = json.loads(body)
        assert response_data["user"]["username"] == "user"
        assert "user" in response_data["user"]["roles"]
        assert "manager" in response_data["user"]["roles"]
        assert "write:reports" in response_data["user"]["permissions"]
    
    @pytest.mark.asyncio
    async def test_rbac_default_role(self):
        """Test RBAC with default role."""
        rbac_config = self.create_rbac_config()
        
        # Don't assign any specific roles to new_user
        # They should get the default 'guest' role
        
        auth_config = AuthConfig(
            type="basic",
            username="new_user",
            password="newpass",
            rbac=rbac_config
        )
        
        paths = [
            PathConfig(
                pattern="/api/.*",
                features=FeatureConfig(auth=auth_config)
            ),
        ]
        
        gateway_config = GatewayConfig(paths=paths)
        gateway = ASGIGateway(config=gateway_config, app=self.demo_app)
        
        credentials = base64.b64encode(b"new_user:newpass").decode()
        headers = [[b"authorization", f"Basic {credentials}".encode()]]
        
        status, body, scope = await self.make_request(gateway, "/api/public/info", headers)
        
        assert status == 200
        response_data = json.loads(body)
        assert response_data["user"]["username"] == "new_user"
        assert "guest" in response_data["user"]["roles"]
        assert "read:public" in response_data["user"]["permissions"]
    
    @pytest.mark.asyncio
    async def test_rbac_error_handling(self):
        """Test RBAC error handling scenarios."""
        gateway = self.create_basic_auth_gateway_with_rbac()
        
        # Test with invalid credentials (should get 401)
        credentials = base64.b64encode(b"invalid:invalid").decode()
        headers = [[b"authorization", f"Basic {credentials}".encode()]]
        
        status, body, scope = await self.make_request(gateway, "/api/admin/users", headers)
        
        assert status == 401  # Unauthorized
        assert "Invalid username or password" in body
    
    @pytest.mark.asyncio
    async def test_rbac_route_without_permissions(self):
        """Test accessing routes that don't require specific permissions."""
        rbac_config = self.create_rbac_config()
        
        auth_config = AuthConfig(
            type="basic",
            username="regular_user",
            password="userpass",
            rbac=rbac_config
        )
        
        protected_features = FeatureConfig(auth=auth_config)
        
        paths = [
            PathConfig(
                pattern="/api/.*",
                features=protected_features
            ),
        ]
        
        gateway_config = GatewayConfig(paths=paths)
        gateway = ASGIGateway(config=gateway_config, app=self.demo_app)
        
        # User credentials
        credentials = base64.b64encode(b"regular_user:userpass").decode()
        headers = [[b"authorization", f"Basic {credentials}".encode()]]
        
        # Access a route that doesn't have specific permission requirements
        status, body, scope = await self.make_request(gateway, "/api/general/info", headers)
        
        assert status == 200
        response_data = json.loads(body)
        assert response_data["user"]["username"] == "regular_user"
        # Route should be accessible because no specific permissions are required
    
    @pytest.mark.asyncio
    async def test_rbac_method_specific_permissions(self):
        """Test RBAC with method-specific permissions."""
        # This test would require extending RBAC to support HTTP methods
        # For now, we'll test that the method is passed to the authorize function
        
        rbac_config = self.create_rbac_config()
        
        auth_config = AuthConfig(
            type="basic",
            username="user",
            password="userpass",
            rbac=rbac_config
        )
        
        protected_features = FeatureConfig(auth=auth_config)
        
        paths = [
            PathConfig(
                pattern="/api/.*",
                features=protected_features
            ),
        ]
        
        gateway_config = GatewayConfig(paths=paths)
        gateway = ASGIGateway(config=gateway_config, app=self.demo_app)
        
        credentials = base64.b64encode(b"user:userpass").decode()
        headers = [[b"authorization", f"Basic {credentials}".encode()]]
        
        # Test GET request
        status, body, scope = await self.make_request(gateway, "/api/users/profile", headers)
        
        assert status == 200
        response_data = json.loads(body)
        assert response_data["method"] == "GET"
        assert response_data["user"]["username"] == "user"


class TestRBACConfigurationParsing:
    """Test RBAC configuration parsing in gateway context."""
    
    @pytest.mark.asyncio
    async def test_rbac_config_from_dict(self):
        """Test parsing RBAC configuration from dictionary."""
        try:
            import jwt
        except ImportError:
            pytest.skip("pyjwt not installed")
        
        # Create a gateway configuration with RBAC
        config_dict = {
            "paths": [
                {
                    "pattern": "/api/.*",
                    "features": {
                        "auth": {
                            "type": "jwt",
                            "secret": "test_secret",
                            "rbac": {
                                "roles": {
                                    "admin": {
                                        "description": "Administrator",
                                        "permissions": ["*:*"]
                                    },
                                    "user": {
                                        "permissions": ["read:api"]
                                    }
                                },
                                "user_roles": {
                                    "admin_user": ["admin"],
                                    "regular_user": ["user"]
                                },
                                "route_permissions": {
                                    "/api/admin/.*": ["admin:access"]
                                },
                                "default_role": "user"
                            }
                        }
                    }
                }
            ]
        }
        
        gateway_config = GatewayConfig._from_dict(config_dict)
        
        # Verify the configuration was parsed correctly
        assert len(gateway_config.paths) == 1
        path_config = gateway_config.paths[0]
        assert path_config.pattern == "/api/.*"
        assert path_config.features.auth is not None
        assert path_config.features.auth.type == "jwt"
        assert path_config.features.auth.secret == "test_secret"
        assert path_config.features.auth.rbac is not None
        
        rbac_config = path_config.features.auth.rbac
        assert "admin" in rbac_config.roles
        assert "user" in rbac_config.roles
        assert rbac_config.user_roles["admin_user"] == ["admin"]
        assert rbac_config.default_role == "user"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])