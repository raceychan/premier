#!/usr/bin/env python3
"""
Comprehensive tests for RBAC (Role-Based Access Control) functionality.

This test suite covers all aspects of RBAC including:
- Role and Permission creation
- RBACConfig configuration
- RBACHandler authorization logic
- Integration with authentication system
- Configuration parsing from dictionaries
"""

import pytest
from premier.features.auth.rbac import (
    Permission,
    Role,
    RBACConfig,
    RBACHandler,
    create_rbac_config_from_dict,
    RBACError,
    AccessDeniedError,
    RoleNotFoundError,
    PermissionNotFoundError,
)


class TestPermission:
    """Test Permission class functionality."""
    
    def test_permission_creation(self):
        """Test creating a permission with valid name."""
        perm = Permission(name="read:api", description="Read API access")
        assert perm.name == "read:api"
        assert perm.description == "Read API access"
    
    def test_permission_invalid_name(self):
        """Test that invalid permission names raise ValueError."""
        with pytest.raises(ValueError, match="Invalid permission format"):
            Permission(name="invalid_name")
        
        with pytest.raises(ValueError, match="Invalid permission format"):
            Permission(name="read")
        
        with pytest.raises(ValueError, match="Invalid permission format"):
            Permission(name="read:")
    
    def test_permission_empty_name(self):
        """Test that empty permission names raise ValueError."""
        with pytest.raises(ValueError, match="Permission name cannot be empty"):
            Permission(name="")
    
    def test_permission_matches_exact(self):
        """Test exact permission matching."""
        perm = Permission(name="read:api")
        assert perm.matches("read:api") is True
        assert perm.matches("write:api") is False
        assert perm.matches("read:users") is False
    
    def test_permission_matches_wildcard(self):
        """Test wildcard permission matching."""
        perm = Permission(name="read:*")
        assert perm.matches("read:api") is True
        assert perm.matches("read:users") is True
        assert perm.matches("read:admin") is True
        assert perm.matches("write:api") is False
        
        perm = Permission(name="*:api")
        assert perm.matches("read:api") is True
        assert perm.matches("write:api") is True
        assert perm.matches("delete:api") is True
        assert perm.matches("read:users") is False
    
    def test_permission_string_representation(self):
        """Test string representation of Permission."""
        perm = Permission(name="read:api")
        assert str(perm) == "read:api"
        assert repr(perm) == "Permission(name='read:api')"


class TestRole:
    """Test Role class functionality."""
    
    def test_role_creation(self):
        """Test creating a role with valid name."""
        role = Role(name="admin", description="Administrator role")
        assert role.name == "admin"
        assert role.description == "Administrator role"
        assert role.permissions == []
    
    def test_role_invalid_name(self):
        """Test that invalid role names raise ValueError."""
        with pytest.raises(ValueError, match="Invalid role name format"):
            Role(name="admin role")  # spaces not allowed
        
        with pytest.raises(ValueError, match="Invalid role name format"):
            Role(name="admin@role")  # @ not allowed
    
    def test_role_empty_name(self):
        """Test that empty role names raise ValueError."""
        with pytest.raises(ValueError, match="Role name cannot be empty"):
            Role(name="")
    
    def test_role_add_permission_string(self):
        """Test adding permission as string."""
        role = Role(name="admin")
        role.add_permission("read:api")
        
        assert len(role.permissions) == 1
        assert role.permissions[0].name == "read:api"
    
    def test_role_add_permission_object(self):
        """Test adding permission as Permission object."""
        role = Role(name="admin")
        perm = Permission(name="read:api")
        role.add_permission(perm)
        
        assert len(role.permissions) == 1
        assert role.permissions[0] == perm
    
    def test_role_add_duplicate_permission(self):
        """Test that duplicate permissions are not added."""
        role = Role(name="admin")
        role.add_permission("read:api")
        role.add_permission("read:api")  # Duplicate
        
        assert len(role.permissions) == 1
        assert role.permissions[0].name == "read:api"
    
    def test_role_remove_permission(self):
        """Test removing permission from role."""
        role = Role(name="admin")
        role.add_permission("read:api")
        role.add_permission("write:api")
        
        role.remove_permission("read:api")
        
        assert len(role.permissions) == 1
        assert role.permissions[0].name == "write:api"
    
    def test_role_has_permission(self):
        """Test checking if role has specific permission."""
        role = Role(name="admin")
        role.add_permission("read:api")
        role.add_permission("write:*")
        
        assert role.has_permission("read:api") is True
        assert role.has_permission("write:users") is True  # Wildcard match
        assert role.has_permission("delete:api") is False
    
    def test_role_get_permission_names(self):
        """Test getting all permission names."""
        role = Role(name="admin")
        role.add_permission("read:api")
        role.add_permission("write:api")
        
        names = role.get_permission_names()
        assert names == {"read:api", "write:api"}
    
    def test_role_string_representation(self):
        """Test string representation of Role."""
        role = Role(name="admin")
        role.add_permission("read:api")
        role.add_permission("write:api")
        
        assert str(role) == "admin"
        assert repr(role) == "Role(name='admin', permissions=2)"


class TestRBACConfig:
    """Test RBACConfig class functionality."""
    
    def test_rbac_config_creation(self):
        """Test creating empty RBAC config."""
        config = RBACConfig()
        assert config.roles == {}
        assert config.user_roles == {}
        assert config.default_role is None
        assert config.route_permissions == {}
        assert config.allow_any_permission is True
    
    def test_add_role_string(self):
        """Test adding role as string."""
        config = RBACConfig()
        config.add_role("admin")
        
        assert "admin" in config.roles
        assert config.roles["admin"].name == "admin"
    
    def test_add_role_object(self):
        """Test adding role as Role object."""
        config = RBACConfig()
        role = Role(name="admin")
        config.add_role(role)
        
        assert "admin" in config.roles
        assert config.roles["admin"] == role
    
    def test_add_user_role(self):
        """Test assigning role to user."""
        config = RBACConfig()
        config.add_role("admin")
        config.add_user_role("user1", "admin")
        
        assert "user1" in config.user_roles
        assert "admin" in config.user_roles["user1"]
    
    def test_add_user_role_nonexistent(self):
        """Test assigning nonexistent role to user."""
        config = RBACConfig()
        
        with pytest.raises(RoleNotFoundError):
            config.add_user_role("user1", "nonexistent")
    
    def test_add_duplicate_user_role(self):
        """Test that duplicate user roles are not added."""
        config = RBACConfig()
        config.add_role("admin")
        config.add_user_role("user1", "admin")
        config.add_user_role("user1", "admin")  # Duplicate
        
        assert len(config.user_roles["user1"]) == 1
    
    def test_remove_user_role(self):
        """Test removing role from user."""
        config = RBACConfig()
        config.add_role("admin")
        config.add_role("user")
        config.add_user_role("user1", "admin")
        config.add_user_role("user1", "user")
        
        config.remove_user_role("user1", "admin")
        
        assert "admin" not in config.user_roles["user1"]
        assert "user" in config.user_roles["user1"]
    
    def test_get_user_roles(self):
        """Test getting all roles for a user."""
        config = RBACConfig()
        admin_role = Role(name="admin")
        user_role = Role(name="user")
        config.add_role(admin_role)
        config.add_role(user_role)
        config.add_user_role("user1", "admin")
        config.add_user_role("user1", "user")
        
        roles = config.get_user_roles("user1")
        assert len(roles) == 2
        assert admin_role in roles
        assert user_role in roles
    
    def test_get_user_roles_with_default(self):
        """Test getting user roles with default role."""
        config = RBACConfig()
        config.add_role("admin")
        config.add_role("default")
        config.default_role = "default"
        config.add_user_role("user1", "admin")
        
        roles = config.get_user_roles("user1")
        assert len(roles) == 2
        role_names = [role.name for role in roles]
        assert "admin" in role_names
        assert "default" in role_names
    
    def test_get_user_permissions(self):
        """Test getting all permissions for a user."""
        config = RBACConfig()
        admin_role = Role(name="admin")
        admin_role.add_permission("read:api")
        admin_role.add_permission("write:api")
        
        user_role = Role(name="user")
        user_role.add_permission("read:api")
        user_role.add_permission("read:users")
        
        config.add_role(admin_role)
        config.add_role(user_role)
        config.add_user_role("user1", "admin")
        config.add_user_role("user1", "user")
        
        permissions = config.get_user_permissions("user1")
        assert permissions == {"read:api", "write:api", "read:users"}
    
    def test_add_route_permission(self):
        """Test adding required permission for a route."""
        config = RBACConfig()
        config.add_route_permission("/api/admin", "admin:access")
        config.add_route_permission("/api/admin", "read:admin")
        
        assert "/api/admin" in config.route_permissions
        assert "admin:access" in config.route_permissions["/api/admin"]
        assert "read:admin" in config.route_permissions["/api/admin"]
    
    def test_add_duplicate_route_permission(self):
        """Test that duplicate route permissions are not added."""
        config = RBACConfig()
        config.add_route_permission("/api/admin", "admin:access")
        config.add_route_permission("/api/admin", "admin:access")  # Duplicate
        
        assert len(config.route_permissions["/api/admin"]) == 1
    
    def test_get_route_permissions(self):
        """Test getting required permissions for a route."""
        config = RBACConfig()
        config.add_route_permission("/api/admin/.*", "admin:access")
        config.add_route_permission("/api/user/.*", "user:access")
        
        # Test regex matching
        assert config.get_route_permissions("/api/admin/users") == ["admin:access"]
        assert config.get_route_permissions("/api/user/profile") == ["user:access"]
        assert config.get_route_permissions("/api/public") == []
    
    def test_validate_success(self):
        """Test successful validation of RBAC config."""
        config = RBACConfig()
        config.add_role("admin")
        config.add_role("user")
        config.default_role = "user"
        config.add_user_role("user1", "admin")
        
        # Should not raise any exception
        config.validate()
    
    def test_validate_default_role_not_found(self):
        """Test validation failure when default role doesn't exist."""
        config = RBACConfig()
        config.add_role("admin")
        config.default_role = "nonexistent"
        
        with pytest.raises(RoleNotFoundError):
            config.validate()
    
    def test_validate_user_role_not_found(self):
        """Test validation failure when user role doesn't exist."""
        config = RBACConfig()
        config.add_role("admin")
        config.add_user_role("user1", "admin")
        
        # Remove the role after assignment
        del config.roles["admin"]
        
        with pytest.raises(RoleNotFoundError):
            config.validate()


class TestRBACHandler:
    """Test RBACHandler class functionality."""
    
    def create_test_config(self):
        """Create a test RBAC configuration."""
        config = RBACConfig()
        
        # Create roles
        admin_role = Role(name="admin")
        admin_role.add_permission("*:*")  # Admin can do everything
        
        user_role = Role(name="user")
        user_role.add_permission("read:api")
        user_role.add_permission("read:users")
        
        manager_role = Role(name="manager")
        manager_role.add_permission("read:*")
        manager_role.add_permission("write:users")
        
        config.add_role(admin_role)
        config.add_role(user_role)
        config.add_role(manager_role)
        
        # Assign roles to users
        config.add_user_role("admin_user", "admin")
        config.add_user_role("regular_user", "user")
        config.add_user_role("manager_user", "manager")
        
        # Define route permissions
        config.add_route_permission("/api/admin/.*", "admin:access")
        config.add_route_permission("/api/users/.*", "read:users")
        config.add_route_permission("/api/users/create", "write:users")
        
        return config
    
    def test_rbac_handler_creation(self):
        """Test creating RBAC handler."""
        config = self.create_test_config()
        handler = RBACHandler(config)
        assert handler.config == config
    
    def test_check_access_admin(self):
        """Test admin access to all routes."""
        config = self.create_test_config()
        handler = RBACHandler(config)
        
        user_info = {"username": "admin_user", "auth_type": "basic"}
        
        # Admin should have access to everything
        assert handler.check_access(user_info, "/api/admin/users") is True
        assert handler.check_access(user_info, "/api/users/profile") is True
        assert handler.check_access(user_info, "/api/users/create") is True
    
    def test_check_access_user(self):
        """Test regular user access."""
        config = self.create_test_config()
        handler = RBACHandler(config)
        
        user_info = {"username": "regular_user", "auth_type": "basic"}
        
        # User should have limited access
        assert handler.check_access(user_info, "/api/users/profile") is True  # Has read:users
        assert handler.check_access(user_info, "/api/users/create") is False  # No write:users
        assert handler.check_access(user_info, "/api/admin/users") is False  # No admin:access
    
    def test_check_access_manager(self):
        """Test manager access."""
        config = self.create_test_config()
        handler = RBACHandler(config)
        
        user_info = {"username": "manager_user", "auth_type": "basic"}
        
        # Manager should have read and write access to users
        assert handler.check_access(user_info, "/api/users/profile") is True  # Has read:users
        assert handler.check_access(user_info, "/api/users/create") is True  # Has write:users
        assert handler.check_access(user_info, "/api/admin/users") is False  # No admin:access
    
    def test_check_access_no_permissions_required(self):
        """Test access to routes with no permission requirements."""
        config = self.create_test_config()
        handler = RBACHandler(config)
        
        user_info = {"username": "regular_user", "auth_type": "basic"}
        
        # Routes with no permissions should be accessible
        assert handler.check_access(user_info, "/api/public") is True
        assert handler.check_access(user_info, "/health") is True
    
    def test_check_access_jwt_user(self):
        """Test access with JWT user info."""
        config = self.create_test_config()
        handler = RBACHandler(config)
        
        # JWT user info uses 'sub' instead of 'username'
        user_info = {"sub": "regular_user", "auth_type": "jwt"}
        
        assert handler.check_access(user_info, "/api/users/profile") is True
        assert handler.check_access(user_info, "/api/users/create") is False
    
    def test_check_access_allow_any_permission(self):
        """Test access with allow_any_permission=True."""
        config = self.create_test_config()
        config.allow_any_permission = True
        handler = RBACHandler(config)
        
        # Create a route that requires multiple permissions
        config.add_route_permission("/api/multi", "read:api")
        config.add_route_permission("/api/multi", "write:api")
        
        user_info = {"username": "regular_user", "auth_type": "basic"}
        
        # User has read:api but not write:api, should pass with allow_any_permission=True
        assert handler.check_access(user_info, "/api/multi") is True
    
    def test_check_access_require_all_permissions(self):
        """Test access with allow_any_permission=False."""
        config = self.create_test_config()
        config.allow_any_permission = False
        handler = RBACHandler(config)
        
        # Create a route that requires multiple permissions
        config.add_route_permission("/api/multi", "read:api")
        config.add_route_permission("/api/multi", "write:api")
        
        user_info = {"username": "regular_user", "auth_type": "basic"}
        
        # User has read:api but not write:api, should fail with allow_any_permission=False
        assert handler.check_access(user_info, "/api/multi") is False
    
    def test_authorize_success(self):
        """Test successful authorization."""
        config = self.create_test_config()
        handler = RBACHandler(config)
        
        user_info = {"username": "regular_user", "auth_type": "basic"}
        
        # Should not raise any exception
        handler.authorize(user_info, "/api/users/profile")
    
    def test_authorize_failure(self):
        """Test authorization failure."""
        config = self.create_test_config()
        handler = RBACHandler(config)
        
        user_info = {"username": "regular_user", "auth_type": "basic"}
        
        # Should raise AccessDeniedError
        with pytest.raises(AccessDeniedError) as exc_info:
            handler.authorize(user_info, "/api/admin/users")
        
        assert "Access denied" in str(exc_info.value)
        assert "regular_user" in str(exc_info.value)
        assert "/api/admin/users" in str(exc_info.value)
    
    def test_get_user_context(self):
        """Test getting enhanced user context."""
        config = self.create_test_config()
        handler = RBACHandler(config)
        
        user_info = {"username": "manager_user", "auth_type": "basic"}
        
        context = handler.get_user_context(user_info)
        
        assert context["username"] == "manager_user"
        assert context["auth_type"] == "basic"
        assert context["roles"] == ["manager"]
        assert "read:*" in context["permissions"]  # Manager has wildcard read permission
        assert "write:users" in context["permissions"]
        assert context["rbac_enabled"] is True
    
    def test_extract_username_basic(self):
        """Test extracting username from basic auth."""
        config = self.create_test_config()
        handler = RBACHandler(config)
        
        user_info = {"username": "testuser", "auth_type": "basic"}
        username = handler._extract_username(user_info)
        assert username == "testuser"
    
    def test_extract_username_jwt(self):
        """Test extracting username from JWT."""
        config = self.create_test_config()
        handler = RBACHandler(config)
        
        user_info = {"sub": "testuser", "auth_type": "jwt"}
        username = handler._extract_username(user_info)
        assert username == "testuser"
    
    def test_extract_username_user_id(self):
        """Test extracting username from user_id."""
        config = self.create_test_config()
        handler = RBACHandler(config)
        
        user_info = {"user_id": "testuser", "auth_type": "custom"}
        username = handler._extract_username(user_info)
        assert username == "testuser"
    
    def test_extract_username_failure(self):
        """Test failure to extract username."""
        config = self.create_test_config()
        handler = RBACHandler(config)
        
        user_info = {"email": "test@example.com", "auth_type": "basic"}
        
        with pytest.raises(ValueError, match="Could not extract username"):
            handler._extract_username(user_info)


class TestRBACConfigParser:
    """Test RBAC configuration parsing from dictionaries."""
    
    def test_parse_basic_config(self):
        """Test parsing basic RBAC configuration."""
        data = {
            "roles": {
                "admin": {
                    "description": "Administrator",
                    "permissions": ["read:*", "write:*", "delete:*"]
                },
                "user": {
                    "permissions": ["read:api", "read:users"]
                }
            },
            "user_roles": {
                "admin_user": ["admin"],
                "regular_user": ["user"]
            },
            "route_permissions": {
                "/api/admin/.*": ["admin:access"],
                "/api/users/.*": ["read:users"]
            },
            "default_role": "user",
            "allow_any_permission": True
        }
        
        config = create_rbac_config_from_dict(data)
        
        # Check roles
        assert "admin" in config.roles
        assert "user" in config.roles
        assert config.roles["admin"].description == "Administrator"
        assert len(config.roles["admin"].permissions) == 3
        assert len(config.roles["user"].permissions) == 2
        
        # Check user roles
        assert config.user_roles["admin_user"] == ["admin"]
        assert config.user_roles["regular_user"] == ["user"]
        
        # Check route permissions
        assert config.route_permissions["/api/admin/.*"] == ["admin:access"]
        assert config.route_permissions["/api/users/.*"] == ["read:users"]
        
        # Check configuration options
        assert config.default_role == "user"
        assert config.allow_any_permission is True
    
    def test_parse_roles_list_format(self):
        """Test parsing roles with list format (permissions only)."""
        data = {
            "roles": {
                "admin": ["read:*", "write:*"],
                "user": ["read:api"]
            }
        }
        
        config = create_rbac_config_from_dict(data)
        
        assert "admin" in config.roles
        assert "user" in config.roles
        assert len(config.roles["admin"].permissions) == 2
        assert len(config.roles["user"].permissions) == 1
    
    def test_parse_minimal_config(self):
        """Test parsing minimal RBAC configuration."""
        data = {
            "roles": {
                "admin": ["read:*"]
            }
        }
        
        config = create_rbac_config_from_dict(data)
        
        assert "admin" in config.roles
        assert len(config.roles["admin"].permissions) == 1
        assert config.user_roles == {}
        assert config.route_permissions == {}
        assert config.default_role is None
        assert config.allow_any_permission is True
    
    def test_parse_empty_config(self):
        """Test parsing empty RBAC configuration."""
        data = {}
        
        config = create_rbac_config_from_dict(data)
        
        assert config.roles == {}
        assert config.user_roles == {}
        assert config.route_permissions == {}
        assert config.default_role is None
        assert config.allow_any_permission is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])