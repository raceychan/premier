import base64
import binascii
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from .errors import (
    InvalidAuthHeaderError,
    InvalidCredentialsError,
    InvalidTokenError,
    MissingAuthHeaderError,
)


@dataclass
class AuthConfig:
    """Configuration for authentication."""

    type: str  # "basic" or "jwt"

    # Basic auth options
    username: Optional[str] = None
    password: Optional[str] = None

    # JWT options
    secret: Optional[str] = None
    algorithm: str = "HS256"
    audience: Optional[str] = None
    issuer: Optional[str] = None
    verify_signature: bool = True
    verify_exp: bool = True
    verify_nbf: bool = True
    verify_iat: bool = True
    verify_aud: bool = True
    verify_iss: bool = True

    def __post_init__(self):
        if self.type == "basic" and (not self.username or not self.password):
            raise ValueError("Basic auth requires username and password")
        if self.type == "jwt" and not self.secret:
            raise ValueError("JWT auth requires secret")


class AuthHandler(ABC):
    """Abstract base class for authentication handlers."""

    @abstractmethod
    async def authenticate(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """Authenticate request and return user info."""
        pass


class BasicAuth(AuthHandler):
    """Basic authentication handler."""

    def __init__(self, config: AuthConfig):
        self.config = config

    async def authenticate(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """Authenticate using Basic auth."""
        auth_header = headers.get("authorization")
        if not auth_header:
            raise MissingAuthHeaderError("Authorization header is required")

        if not auth_header.startswith("Basic "):
            raise InvalidAuthHeaderError("Invalid authorization header format")

        try:
            # Decode base64 credentials
            encoded_credentials = auth_header[6:]  # Remove "Basic " prefix
            decoded_bytes = base64.b64decode(encoded_credentials)
            decoded_str = decoded_bytes.decode("utf-8")

            if ":" not in decoded_str:
                raise InvalidAuthHeaderError("Invalid credentials format")

            username, password = decoded_str.split(":", 1)

            # Validate credentials
            if username != self.config.username or password != self.config.password:
                raise InvalidCredentialsError("Invalid username or password")

            return {"username": username, "auth_type": "basic"}

        except (binascii.Error, UnicodeDecodeError):
            raise InvalidAuthHeaderError("Invalid base64 encoding")


class JWTAuth(AuthHandler):
    """JWT authentication handler with lazy import."""

    def __init__(self, config: AuthConfig):
        self.config = config
        self._jwt_module = None

    def _get_jwt_module(self):
        """Lazy import JWT module."""
        if self._jwt_module is None:
            try:
                import jwt

                self._jwt_module = jwt
            except ImportError:
                raise ImportError(
                    "pyjwt is required for JWT authentication. "
                    "Install with: pip install premier[jwt]"
                )
        return self._jwt_module

    async def authenticate(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """Authenticate using JWT."""
        jwt_module = self._get_jwt_module()

        auth_header = headers.get("authorization")
        if not auth_header:
            raise MissingAuthHeaderError("Authorization header is required")

        if not auth_header.startswith("Bearer "):
            raise InvalidAuthHeaderError("Invalid authorization header format")

        token = auth_header[7:]  # Remove "Bearer " prefix

        try:
            # Prepare JWT decode options
            options = {
                "verify_signature": self.config.verify_signature,
                "verify_exp": self.config.verify_exp,
                "verify_nbf": self.config.verify_nbf,
                "verify_iat": self.config.verify_iat,
                "verify_aud": self.config.verify_aud,
                "verify_iss": self.config.verify_iss,
            }

            # Decode JWT token
            payload = jwt_module.decode(
                token,
                self.config.secret,
                algorithms=[self.config.algorithm],
                audience=self.config.audience,
                issuer=self.config.issuer,
                options=options,
            )

            # Add auth type to payload
            payload["auth_type"] = "jwt"
            return payload

        except jwt_module.InvalidSignatureError:
            raise InvalidTokenError("Invalid JWT signature")
        except jwt_module.DecodeError as e:
            raise InvalidTokenError(f"JWT decode error: {e}")
        except jwt_module.ExpiredSignatureError:
            raise InvalidTokenError("JWT token has expired")
        except jwt_module.InvalidAudienceError:
            raise InvalidTokenError("Invalid JWT audience")
        except jwt_module.InvalidIssuerError:
            raise InvalidTokenError("Invalid JWT issuer")
        except jwt_module.InvalidTokenError as e:
            raise InvalidTokenError(f"Invalid JWT token: {e}")
        except jwt_module.InvalidKeyError:
            raise InvalidTokenError("Invalid JWT key")


def create_auth_handler(config: AuthConfig) -> AuthHandler:
    """Factory function to create appropriate auth handler."""
    if config.type == "basic":
        return BasicAuth(config)
    elif config.type == "jwt":
        return JWTAuth(config)
    else:
        raise ValueError(f"Unsupported auth type: {config.type}")
