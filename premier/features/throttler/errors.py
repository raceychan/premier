from premier.errors import PremierError


class ThrottlerError(PremierError):
    """Base class for throttler-related errors."""
    pass


class ArgumentMissingError(ThrottlerError):
    """Raised when required arguments are missing for throttler configuration."""
    
    def __init__(self, msg: str = ""):
        self.msg = msg
        super().__init__(msg or "Required argument is missing")


class UninitializedHandlerError(ThrottlerError):
    """Raised when throttler handler is not properly initialized."""
    
    def __init__(self, message: str = "Throttler handler not initialized"):
        super().__init__(message)


class QuotaExceedsError(ThrottlerError):
    """Raised when rate limit quota is exceeded."""
    
    time_remains: float

    def __init__(self, quota: int, duration_s: int, time_remains: float):
        msg = f"Rate limit exceeded: {quota} requests allowed per {duration_s} seconds, retry after {time_remains:.2f}s"
        self.quota = quota
        self.duration_s = duration_s
        self.time_remains = time_remains
        super().__init__(msg)


class ThrottlerConfigurationError(ThrottlerError):
    """Raised when throttler configuration is invalid."""
    pass


class ThrottlerAlgorithmError(ThrottlerError):
    """Raised when unsupported throttling algorithm is used."""
    
    def __init__(self, algorithm: str):
        self.algorithm = algorithm
        super().__init__(f"Unsupported throttling algorithm: {algorithm}")


class KeyMakerError(ThrottlerError):
    """Raised when key generation fails in throttler."""
    pass
