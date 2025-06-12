import asyncio
import logging
from unittest.mock import patch

import pytest

from premier import BucketFullError, QuotaExceedsError, Throttler
from premier.throttler import handler


def _keymaker(a: int, b: int) -> str:
    return f"{a}"


async def test_throttle_raise_error(aiothrottler: Throttler):
    quota = 3

    @aiothrottler.fixed_window(quota=quota, duration=5)
    def add(a: int, b: int) -> int:  # sync function
        res = a + b
        return res

    # First 3 calls should work
    for _ in range(quota):
        result = await add(3, 5)
        assert result == 8

    # 4th call should raise QuotaExceedsError
    with pytest.raises(QuotaExceedsError):
        await add(3, 5)


async def test_method(aiothrottler: Throttler):
    quota = 3

    class T:
        @aiothrottler.fixed_window(quota=quota, duration=5)
        def add(self, a: int, b: int) -> int:  # sync method
            res = a + b
            return res

    t = T()
    # First 3 calls should work
    for _ in range(quota):
        result = await t.add(3, 5)
        assert result == 8

    # 4th call should raise QuotaExceedsError
    with pytest.raises(QuotaExceedsError):
        await t.add(3, 5)


async def test_throttler_do_not_raise_error():
    from unittest.mock import Mock

    from premier.providers import AsyncInMemoryCache
    from premier.throttler.handler import AsyncDefaultHandler
    from premier.throttler.throttler import Throttler

    # Create a mock timer that returns values in sequence
    mock_timer = Mock()
    # Provide enough values for all timer calls during the test
    # First 3 calls at t=0, then the final call at t=4 to simulate time progression
    mock_timer.side_effect = [0, 0, 0, 0, 4, 4, 6, 6]  # Extra values to be safe

    # Create handler with injected timer
    handler_with_timer = AsyncDefaultHandler(AsyncInMemoryCache(), timer=mock_timer)

    # Create and configure throttler with custom handler
    throttler = Throttler(handler=handler_with_timer, keyspace="test")
    await throttler.clear()

    @throttler.fixed_window(quota=2, duration=3)
    def add(a: int, b: int) -> int:  # sync function
        res = a + b
        return res

    tries = 2  # Only test the quota limit
    res = []
    for _ in range(tries):
        res.append(await add(3, 5))  # decorated function is async
    assert len(res) == tries

    # The third call should be throttled
    try:
        await add(3, 5)
        assert False, "Should have been throttled"
    except QuotaExceedsError:
        pass  # Expected


async def test_throttler_do_not_raise_error_with_interval(aiothrottler: Throttler):
    await aiothrottler.clear()

    @aiothrottler.fixed_window(quota=3, duration=5)
    def add(a: int, b: int) -> int:  # sync function
        res = a + b
        return res

    tries = 2
    res = [await add(3, 5) for _ in range(tries)]  # decorated function is async
    assert len(res) == tries


async def test_throttler_with_keymaker(aiothrottler: Throttler):
    await aiothrottler.clear()

    @aiothrottler.fixed_window(quota=3, duration=5, keymaker=_keymaker)
    def add(a: int, b: int) -> int:  # sync function
        res = a + b
        return res

    tries = 2
    res = [await add(3, 5) for _ in range(tries)]  # decorated function is async
    assert len(res) == tries


async def test_throttler_with_token_bucket():
    from unittest.mock import Mock

    from premier.providers import AsyncInMemoryCache
    from premier.throttler.handler import AsyncDefaultHandler
    from premier.throttler.throttler import Throttler

    # Create a mock timer that returns values in sequence
    mock_timer = Mock()
    # Mock time progression to simulate token bucket refill
    mock_timer.side_effect = [
        0,
        0,
        0,
        0,
        2,
    ]  # First 3 calls at t=0, 4th fails, 5th at t=2

    # Create handler with injected timer
    handler_with_timer = AsyncDefaultHandler(AsyncInMemoryCache(), timer=mock_timer)

    # Create and configure throttler with custom handler
    throttler = Throttler(handler=handler_with_timer, keyspace="test")
    await throttler.clear()

    @throttler.token_bucket(quota=3, duration=5, keymaker=_keymaker)
    def add(a: int, b: int) -> int:  # sync function
        res = a + b
        return res

    tries = 4
    res: list[int] = []
    try:
        for _ in range(tries):
            res.append(await add(3, 5))  # decorated function is async
    except QuotaExceedsError:
        res.append(await add(3, 5))  # This should work due to mocked time progression

    assert len(res) == tries


# BUG: this would leave "p" and "t" to redis and won't be removed
async def test_throttler_with_leaky_bucket(aiothrottler: Throttler):
    bucket_size = 3
    quota = 1
    duration = 1

    @aiothrottler.leaky_bucket(
        quota=quota,
        bucket_size=bucket_size,
        duration=duration,
        keymaker=_keymaker,
    )
    def add(a: int, b: int) -> None:  # sync function
        # Remove sleep to speed up test
        return None

    tries = 6
    rejected = 0
    res: list[int | None] = []

    for _ in range(tries):
        try:
            await add(3, 5)  # decorated function is async
        except BucketFullError:
            rejected += 1
        else:
            res.append(None)

    # In leaky bucket: bucket_size allows immediate tasks, quota determines rate
    # So we expect bucket_size tasks to succeed immediately, rest rejected
    expected_rejected = tries - bucket_size
    assert rejected == expected_rejected
    assert len(res) == tries - rejected
