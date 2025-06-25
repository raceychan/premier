from premier.errors import PremierError


class TimerError(PremierError):
    """Base class for timer-related errors."""
    pass


class TimeoutError(TimerError):
    """Raised when a function call times out."""
    
    def __init__(self, timeout_seconds: float, function_name: str = ""):
        self.timeout_seconds = timeout_seconds
        self.function_name = function_name
        message = f"Function {function_name} timed out after {timeout_seconds}s" if function_name else f"Operation timed out after {timeout_seconds}s"
        super().__init__(message)


class TimerConfigurationError(TimerError):
    """Raised when timer configuration is invalid."""
    pass


class LoggerError(TimerError):
    """Raised when there's an issue with the logger."""
    pass