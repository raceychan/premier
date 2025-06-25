from premier.errors import PremierError


class RetryError(PremierError):
    """Base class for retry-related errors."""
    pass


class MaxRetriesExceededError(RetryError):
    """Raised when maximum retry attempts are exceeded."""
    
    def __init__(self, max_attempts: int, last_exception: Exception):
        self.max_attempts = max_attempts
        self.last_exception = last_exception
        super().__init__(f"Max retries ({max_attempts}) exceeded. Last error: {last_exception}")


class RetryConfigurationError(RetryError):
    """Raised when retry configuration is invalid."""
    pass


class CircuitBreakerError(PremierError):
    """Base class for circuit breaker errors."""
    pass


class CircuitBreakerOpenError(CircuitBreakerError):
    """Raised when circuit breaker is open and blocking requests."""
    
    def __init__(self, message: str = "Circuit breaker is open"):
        super().__init__(message)


class CircuitBreakerConfigurationError(CircuitBreakerError):
    """Raised when circuit breaker configuration is invalid."""
    pass