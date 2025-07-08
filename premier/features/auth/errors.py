class AuthError(Exception):
    """Base exception for authentication errors."""
    pass


class InvalidCredentialsError(AuthError):
    """Exception raised when authentication credentials are invalid."""
    pass


class InvalidTokenError(AuthError):
    """Exception raised when JWT token is invalid."""
    pass


class MissingAuthHeaderError(AuthError):
    """Exception raised when required auth header is missing."""
    pass


class InvalidAuthHeaderError(AuthError):
    """Exception raised when auth header format is invalid."""
    pass