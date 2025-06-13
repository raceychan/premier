"""
Example demonstrating Premier with logging functionality.

This example shows how to use the Premier class with proper logging
for retry attempts, timeouts, and timing measurements.
"""

import asyncio
import logging
from premier import Premier, ILogger


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class StandardLogger:
    """Standard logger that implements ILogger interface."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def info(self, msg: str):
        self.logger.info(msg)
    
    def exception(self, msg: str):
        self.logger.exception(msg)


async def main():
    # Initialize Premier with logging
    premier = Premier(keyspace="logging_example")
    logger = StandardLogger("premier_example")
    
    print("=== Premier Logging Example ===\n")
    
    # Example 1: Retry with logging
    print("1. Retry with Logging:")
    
    attempt_count = 0
    
    @premier.retry(max_attempts=3, wait=0.5, logger=logger)
    async def flaky_service(data: str) -> str:
        nonlocal attempt_count
        attempt_count += 1
        print(f"  Executing attempt {attempt_count}")
        
        if attempt_count < 3:
            raise ConnectionError("Service temporarily unavailable")
        
        return f"Successfully processed: {data}"
    
    try:
        result = await flaky_service("important data")
        print(f"  Final result: {result}")
    except Exception as e:
        print(f"  Failed: {e}")
    
    print()
    
    # Example 2: Timeout with logging
    print("2. Timeout with Logging:")
    
    @premier.timeout(0.2, logger=logger)
    async def slow_operation() -> str:
        print("  Starting operation that might timeout...")
        await asyncio.sleep(0.3)  # This will timeout
        return "Operation completed"
    
    try:
        result = await slow_operation()
        print(f"  Result: {result}")
    except asyncio.TimeoutError:
        print("  Operation timed out (logged to logger)")
    
    print()
    
    # Example 3: Timing with logging
    print("3. Timing with Logging:")
    
    @premier.timeit(logger=logger, log_threshold=0.01, with_args=True)
    async def timed_operation(n: int, operation: str) -> int:
        """Simulate some work with timing."""
        print(f"  Performing {operation} on {n}")
        await asyncio.sleep(0.05)  # Simulate work
        return n * 2
    
    result = await timed_operation(42, "calculation")
    print(f"  Result: {result}")
    
    print()
    
    # Example 4: Custom logger with different log levels
    print("4. Custom Logger Levels:")
    
    class VerboseLogger:
        """More verbose logger with different log levels."""
        
        def __init__(self):
            self.logger = logging.getLogger("verbose")
        
        def info(self, msg: str):
            self.logger.info(f"[INFO] {msg}")
        
        def exception(self, msg: str):
            self.logger.error(f"[ERROR] {msg}")
    
    verbose_logger = VerboseLogger()
    
    @premier.retry(max_attempts=2, wait=0.2, logger=verbose_logger)
    async def quick_fail():
        print("  Trying quick operation...")
        raise ValueError("Quick failure")
    
    try:
        await quick_fail()
    except ValueError:
        print("  Quick operation failed (check logs)")
    
    print()
    
    # Example 5: Combined logging with caching and throttling
    print("5. Combined Operations with Logging:")
    
    @premier.cache_result(expire_s=60)
    @premier.retry(max_attempts=2, wait=0.1, logger=logger)
    @premier.timeit(logger=logger, with_args=True)
    async def robust_api_call(endpoint: str) -> dict:
        print(f"  Making API call to: {endpoint}")
        
        # Simulate occasional failure
        import random
        if random.random() < 0.3:
            raise ConnectionError("Network error")
        
        await asyncio.sleep(0.02)  # Simulate API call
        return {"endpoint": endpoint, "status": "success", "timestamp": asyncio.get_event_loop().time()}
    
    try:
        result = await robust_api_call("/users")
        print(f"  API Result: {result}")
        
        # Second call should use cache
        result2 = await robust_api_call("/users")
        print(f"  Cached Result: {result2}")
        
    except Exception as e:
        print(f"  API call failed: {e}")
    
    print()
    
    # Example 6: Silent operation (no logger)
    print("6. Silent Operation (no logging):")
    
    @premier.retry(max_attempts=2, wait=0.1)  # No logger
    async def silent_operation():
        print("  Silent retry operation")
        raise RuntimeError("Silent failure")
    
    try:
        await silent_operation()
    except RuntimeError:
        print("  Silent operation failed (no retry logs)")
    
    print()
    
    # Cleanup
    print("7. Cleanup:")
    await premier.close()
    print("  Premier resources closed")
    
    print("\n=== Logging Example Complete ===")


if __name__ == "__main__":
    asyncio.run(main())