"""
Role-Based Access Control (RBAC) implementation for Premier.

This module provides comprehensive RBAC functionality that integrates with
the existing authentication system to control access to routes based on
user roles and permissions.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Union, Any

from .errors import AuthError


class RBACError(AuthError):
    """Base exception for RBAC-related errors."""
    pass


class AccessDeniedError(RBACError):
    """Exception raised when user lacks required permissions."""
    pass


class RoleNotFoundError(RBACError):
    """Exception raised when a role is not found."""
    pass


class PermissionNotFoundError(RBACError):
    """Exception raised when a permission is not found."""
    pass


@dataclass
class Permission:
    """Represents a specific permission."""
    
    name: str
    description: Optional[str] = None
    
    def __post_init__(self):
        if not self.name:
            raise ValueError("Permission name cannot be empty")
        
        # Validate permission name format (e.g., "read:api", "write:users", "*:*")
        if not re.match(r'^[a-zA-Z0-9_*]+:[a-zA-Z0-9_*]+$', self.name):
            raise ValueError(
                f"Invalid permission format: {self.name}. "
                "Expected format: 'action:resource' (e.g., 'read:api', 'write:users', '*:*')"
            )
    
    def matches(self, required_permission: str) -> bool:
        """Check if this permission matches the required permission."""
        # Support wildcard permissions (e.g., "read:*" matches "read:api")
        if '*' in self.name:
            # Convert wildcard to regex
            pattern = self.name.replace('*', '.*')
            return bool(re.match(f'^{pattern}$', required_permission))
        
        return self.name == required_permission
    
    def __str__(self) -> str:
        return self.name
    
    def __repr__(self) -> str:
        return f"Permission(name='{self.name}')"


@dataclass
class Role:
    """Represents a user role with associated permissions."""
    
    name: str
    permissions: List[Permission] = field(default_factory=list)
    description: Optional[str] = None
    
    def __post_init__(self):
        if not self.name:
            raise ValueError("Role name cannot be empty")
        
        # Validate role name format
        if not re.match(r'^[a-zA-Z0-9_-]+$', self.name):
            raise ValueError(
                f"Invalid role name format: {self.name}. "
                "Only alphanumeric characters, underscores, and hyphens are allowed."
            )
    
    def has_permission(self, permission: str) -> bool:
        """Check if this role has the specified permission."""
        return any(perm.matches(permission) for perm in self.permissions)
    
    def add_permission(self, permission: Union[str, Permission]):
        """Add a permission to this role."""
        if isinstance(permission, str):
            permission = Permission(name=permission)
        
        # Avoid duplicate permissions
        if not any(perm.name == permission.name for perm in self.permissions):
            self.permissions.append(permission)
    
    def remove_permission(self, permission_name: str):
        """Remove a permission from this role."""
        self.permissions = [perm for perm in self.permissions if perm.name != permission_name]
    
    def get_permission_names(self) -> Set[str]:
        """Get all permission names for this role."""
        return {perm.name for perm in self.permissions}
    
    def __str__(self) -> str:
        return self.name
    
    def __repr__(self) -> str:
        return f"Role(name='{self.name}', permissions={len(self.permissions)})"


@dataclass
class RBACConfig:
    """Configuration for Role-Based Access Control."""
    
    # Role definitions
    roles: Dict[str, Role] = field(default_factory=dict)
    
    # User-role mappings (username -> list of role names)
    user_roles: Dict[str, List[str]] = field(default_factory=dict)
    
    # Default role for authenticated users (optional)
    default_role: Optional[str] = None
    
    # Route-permission mappings (route_pattern -> required_permissions)
    route_permissions: Dict[str, List[str]] = field(default_factory=dict)
    
    # Allow access if user has ANY of the required permissions (default: True)
    # If False, user must have ALL required permissions
    allow_any_permission: bool = True
    
    def add_role(self, role: Union[str, Role]):
        """Add a role to the configuration."""
        if isinstance(role, str):
            role = Role(name=role)
        
        self.roles[role.name] = role
    
    def add_user_role(self, username: str, role_name: str):
        """Assign a role to a user."""
        if role_name not in self.roles:
            raise RoleNotFoundError(f"Role '{role_name}' not found")
        
        if username not in self.user_roles:
            self.user_roles[username] = []
        
        if role_name not in self.user_roles[username]:
            self.user_roles[username].append(role_name)
    
    def remove_user_role(self, username: str, role_name: str):
        """Remove a role from a user."""
        if username in self.user_roles and role_name in self.user_roles[username]:
            self.user_roles[username].remove(role_name)
    
    def get_user_roles(self, username: str) -> List[Role]:
        """Get all roles for a user."""
        role_names = self.user_roles.get(username, [])
        
        # Add default role if configured
        if self.default_role and self.default_role not in role_names:
            role_names.append(self.default_role)
        
        return [self.roles[role_name] for role_name in role_names if role_name in self.roles]
    
    def get_user_permissions(self, username: str) -> Set[str]:
        """Get all permissions for a user."""
        permissions = set()
        for role in self.get_user_roles(username):
            permissions.update(role.get_permission_names())
        return permissions
    
    def add_route_permission(self, route_pattern: str, permission: str):
        """Add a required permission for a route."""
        if route_pattern not in self.route_permissions:
            self.route_permissions[route_pattern] = []
        
        if permission not in self.route_permissions[route_pattern]:
            self.route_permissions[route_pattern].append(permission)
    
    def get_route_permissions(self, path: str) -> List[str]:
        """Get required permissions for a specific path."""
        # Sort patterns by specificity (more specific patterns first)
        # Patterns with fewer wildcards and longer length are more specific
        patterns = sorted(
            self.route_permissions.items(),
            key=lambda x: (x[0].count('*'), -len(x[0]))
        )
        
        for pattern, permissions in patterns:
            if re.match(pattern, path):
                return permissions
        return []
    
    def validate(self):
        """Validate the RBAC configuration."""
        # Check that default role exists
        if self.default_role and self.default_role not in self.roles:
            raise RoleNotFoundError(f"Default role '{self.default_role}' not found")
        
        # Check that all user roles exist
        for username, role_names in self.user_roles.items():
            for role_name in role_names:
                if role_name not in self.roles:
                    raise RoleNotFoundError(f"Role '{role_name}' assigned to user '{username}' not found")


class RBACHandler:
    """Handles RBAC authorization logic."""
    
    def __init__(self, config: RBACConfig):
        self.config = config
        self.config.validate()
    
    def check_access(self, user_info: Dict[str, Any], path: str, method: str = "GET") -> bool:
        """Check if user has access to the specified path."""
        # Get required permissions for the path
        required_permissions = self.config.get_route_permissions(path)
        
        # If no permissions are required, allow access
        if not required_permissions:
            return True
        
        # Get user's permissions
        username = self._extract_username(user_info)
        
        # Check if user has required permissions
        if self.config.allow_any_permission:
            # User needs ANY of the required permissions
            return any(
                any(perm.matches(required_perm) for perm in self._get_user_permission_objects(username))
                for required_perm in required_permissions
            )
        else:
            # User needs ALL required permissions
            return all(
                any(perm.matches(required_perm) for perm in self._get_user_permission_objects(username))
                for required_perm in required_permissions
            )
    
    def authorize(self, user_info: Dict[str, Any], path: str, method: str = "GET"):
        """Authorize user access to path, raising AccessDeniedError if denied."""
        if not self.check_access(user_info, path, method):
            username = self._extract_username(user_info)
            required_permissions = self.config.get_route_permissions(path)
            user_permissions = self.config.get_user_permissions(username)
            
            raise AccessDeniedError(
                f"Access denied for user '{username}' to path '{path}'. "
                f"Required permissions: {required_permissions}, "
                f"User permissions: {list(user_permissions)}"
            )
    
    def get_user_context(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """Get enhanced user context with roles and permissions."""
        username = self._extract_username(user_info)
        roles = self.config.get_user_roles(username)
        permissions = self.config.get_user_permissions(username)
        
        return {
            **user_info,
            "roles": [role.name for role in roles],
            "permissions": list(permissions),
            "rbac_enabled": True
        }
    
    def _extract_username(self, user_info: Dict[str, Any]) -> str:
        """Extract username from user info."""
        # Support different auth types
        if "username" in user_info:
            return user_info["username"]
        elif "sub" in user_info:
            return user_info["sub"]
        elif "user_id" in user_info:
            return user_info["user_id"]
        else:
            raise ValueError("Could not extract username from user info")
    
    def _get_user_permission_objects(self, username: str) -> List[Permission]:
        """Get Permission objects for a user."""
        permissions = []
        for role in self.config.get_user_roles(username):
            permissions.extend(role.permissions)
        return permissions


def create_rbac_config_from_dict(data: Dict[str, Any]) -> RBACConfig:
    """Create RBAC configuration from dictionary."""
    config = RBACConfig()
    
    # Parse roles
    if "roles" in data:
        for role_name, role_data in data["roles"].items():
            role = Role(name=role_name)
            
            if isinstance(role_data, dict):
                # Role with permissions and description
                role.description = role_data.get("description")
                permissions = role_data.get("permissions", [])
                for perm_name in permissions:
                    role.add_permission(perm_name)
            elif isinstance(role_data, list):
                # Role with just permissions list
                for perm_name in role_data:
                    role.add_permission(perm_name)
            
            config.add_role(role)
    
    # Parse user-role mappings
    if "user_roles" in data:
        config.user_roles = data["user_roles"]
    
    # Parse route permissions
    if "route_permissions" in data:
        config.route_permissions = data["route_permissions"]
    
    # Parse configuration options
    config.default_role = data.get("default_role")
    config.allow_any_permission = data.get("allow_any_permission", True)
    
    return config