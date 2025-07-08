"""
Example demonstrating the Premier facade pattern usage.

This example shows how to use the Premier class as a unified interface
for all Premier functionality including caching, throttling, retry, and timing.
"""

import asyncio
from premier import Premier


async def main():
    # Initialize Premier with default settings
    premier = Premier(keyspace="example")
    
    print("=== Premier Facade Example ===\n")
    
    # Example 1: Caching
    print("1. Caching Example:")
    
    @premier.cache_result(expire_s=60)
    async def expensive_calculation(n: int) -> int:
        print(f"  Computing {n}^2 (expensive operation)")
        await asyncio.sleep(0.1)  # Simulate expensive operation
        return n * n
    
    # First call - will compute
    result1 = await expensive_calculation(5)
    print(f"  First call result: {result1}")
    
    # Second call - will use cache
    result2 = await expensive_calculation(5)
    print(f"  Second call result: {result2} (from cache)")
    
    print()
    
    # Example 2: Throttling
    print("2. Throttling Example:")
    
    @premier.fixed_window(quota=3, duration=2)
    async def api_call(msg: str) -> str:
        print(f"  API call: {msg}")
        return f"Response to: {msg}"
    
    # These should succeed
    for i in range(3):
        result = await api_call(f"Request {i+1}")
        print(f"  {result}")
    
    print("  (Quota exhausted for this window)")
    print()
    
    # Example 3: Leaky Bucket
    print("3. Leaky Bucket Example:")
    
    @premier.leaky_bucket(bucket_size=2, quota=1, duration=1)
    async def rate_limited_task(task_id: int) -> str:
        print(f"  Processing task {task_id}")
        return f"Task {task_id} completed"
    
    # First task processes immediately
    result = await rate_limited_task(1)
    print(f"  {result}")
    
    print()
    
    # Example 4: Retry
    print("4. Retry Example:")
    
    attempt_count = 0
    
    @premier.retry(max_attempts=3, wait=0.1)
    async def flaky_service(data: str) -> str:
        nonlocal attempt_count
        attempt_count += 1
        print(f"  Attempt {attempt_count} for data: {data}")
        
        if attempt_count < 3:
            raise ConnectionError("Service temporarily unavailable")
        
        return f"Successfully processed: {data}"
    
    try:
        result = await flaky_service("important data")
        print(f"  {result}")
    except Exception as e:
        print(f"  Failed: {e}")
    
    print()
    
    # Example 5: Timeout
    print("5. Timeout Example:")
    
    @premier.timeout(0.2)
    async def slow_operation() -> str:
        print("  Starting slow operation...")
        await asyncio.sleep(0.1)  # This should complete in time
        return "Operation completed"
    
    try:
        result = await slow_operation()
        print(f"  {result}")
    except asyncio.TimeoutError:
        print("  Operation timed out")
    
    print()
    
    # Example 6: Timing
    print("6. Timing Example:")
    
    @premier.timeit()
    def cpu_intensive_task(n: int) -> int:
        """Simulate CPU-intensive work."""
        total = 0
        for i in range(n):
            total += i * i
        return total
    
    result = cpu_intensive_task(1000)
    print(f"  Result: {result}")
    
    print()
    
    # Example 7: Combining multiple decorators
    print("7. Combined Decorators Example:")
    
    @premier.cache_result(expire_s=30)
    @premier.retry(max_attempts=2, wait=0.1)
    @premier.timeit()
    async def robust_api_call(endpoint: str) -> dict:
        print(f"  Making robust API call to: {endpoint}")
        # Simulate some processing
        await asyncio.sleep(0.05)
        return {"endpoint": endpoint, "status": "success", "data": "example"}
    
    result = await robust_api_call("/users")
    print(f"  API Result: {result}")
    
    print()
    
    # Cleanup
    print("8. Cleanup:")
    await premier.close()
    print("  Premier resources closed")
    
    print("\n=== Example Complete ===")


if __name__ == "__main__":
    asyncio.run(main())