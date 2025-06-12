import asyncio
from premier.retry.retry import retry


@retry(max_attempts=3, wait=2)
async def test_fixed_wait():
    print("Attempting with fixed wait...")
    raise ValueError("Test error")


@retry(max_attempts=4, wait=[1, 2, 3])
async def test_list_wait():
    print("Attempting with list wait...")
    raise ValueError("Test error")


@retry(max_attempts=3, wait=lambda attempt: attempt * 0.5)
async def test_callable_wait():
    print("Attempting with callable wait...")
    raise ValueError("Test error")


@retry(max_attempts=2, wait=1)
async def test_success():
    global counter
    counter += 1
    if counter < 2:
        raise ValueError("Fail first time")
    return "Success!"


async def main():
    global counter
    counter = 0
    
    print("Testing successful retry:")
    result = await test_success()
    print(f"Result: {result}")
    
    print("\nTesting fixed wait (will fail):")
    try:
        await test_fixed_wait()
    except ValueError as e:
        print(f"Final error: {e}")


if __name__ == "__main__":
    asyncio.run(main())