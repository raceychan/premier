import logging
from unittest.mock import patch

import pytest

from premier import BucketFullError, QuotaExceedsError, Throttler
from premier.throttler import handler


def _keymaker(a: int, b: int) -> str:
    return f"{a}"


def test_throttle_raise_error(throttler: Throttler):
    quota = 3

    @throttler.fixed_window(quota=quota, duration=5)
    def add(a: int, b: int) -> int:
        res = a + b
        return res

    tries = 4
    with pytest.raises(QuotaExceedsError):
        res = [add(3, 5) for _ in range(tries)]
        assert len(res) <= quota


def test_method(throttler: Throttler):
    quota = 3

    class T:
        @throttler.fixed_window(quota=quota, duration=5)
        def add(self, a: int, b: int) -> int:
            res = a + b
            return res

    tries = 4
    t = T()
    with pytest.raises(QuotaExceedsError):
        res: list[None] = [t.add(3, 5) for _ in range(tries)]
        assert len(res) <= quota


def test_throttler_do_not_raise_error():
    from unittest.mock import Mock
    from premier.throttler.handler import DefaultHandler
    from premier.throttler.throttler import Throttler
    
    # Create a mock timer that returns values in sequence
    mock_timer = Mock()
    # Provide enough values for all timer calls during the test
    # First 3 calls at t=0, then the final call at t=4 to simulate time progression
    mock_timer.side_effect = [0, 0, 0, 0, 4, 4, 6, 6]  # Extra values to be safe
    
    # Create handler with injected timer
    handler_with_timer = DefaultHandler(timer=mock_timer)
    
    # Create and configure throttler with custom handler
    throttler = Throttler()
    throttler.config(handler=handler_with_timer, keyspace="test")
    throttler.clear()
    
    @throttler.fixed_window(quota=2, duration=3)
    def add(a: int, b: int) -> int:
        res = a + b
        return res

    tries = 3
    res = [add(3, 5) for _ in range(tries - 1)]
    res.append(add(3, 5))  # This should work due to mocked time progression
    assert len(res) == tries


def test_throttler_do_not_raise_error_with_interval(throttler: Throttler):
    throttler.clear()

    @throttler.fixed_window(quota=3, duration=5)
    def add(a: int, b: int) -> int:
        res = a + b
        return res

    tries = 2
    res = [add(3, 5) for _ in range(tries)]
    assert len(res) == tries


def test_throttler_with_keymaker(throttler: Throttler):
    throttler.clear()

    @throttler.fixed_window(quota=3, duration=5, keymaker=_keymaker)
    def add(a: int, b: int) -> int:
        res = a + b
        return res

    tries = 2
    res = [add(3, 5) for _ in range(tries)]
    assert len(res) == tries


def test_throttler_with_token_bucket():
    from unittest.mock import Mock
    from premier.throttler.handler import DefaultHandler
    from premier.throttler.throttler import Throttler
    
    # Create a mock timer that returns values in sequence
    mock_timer = Mock()
    # Mock time progression to simulate token bucket refill
    mock_timer.side_effect = [0, 0, 0, 0, 2]  # First 3 calls at t=0, 4th fails, 5th at t=2
    
    # Create handler with injected timer
    handler_with_timer = DefaultHandler(timer=mock_timer)
    
    # Create and configure throttler with custom handler
    throttler = Throttler()
    throttler.config(handler=handler_with_timer, keyspace="test")
    throttler.clear()
    
    @throttler.token_bucket(quota=3, duration=5, keymaker=_keymaker)
    def add(a: int, b: int) -> int:
        res = a + b
        return res

    tries = 4
    res: list[int] = []
    try:
        for _ in range(tries):
            res.append(add(3, 5))
    except QuotaExceedsError:
        res.append(add(3, 5))  # This should work due to mocked time progression

    assert len(res) == tries


# BUG: this would leave "p" and "t" to redis and won't be removed
def test_throttler_with_leaky_bucket(throttler: Throttler):
    bucket_size = 3
    quota = 1
    duration = 1

    @throttler.leaky_bucket(
        quota=quota,
        bucket_size=bucket_size,
        duration=duration,
        keymaker=_keymaker,
    )
    def add(a: int, b: int) -> None:
        # Remove sleep to speed up test  
        return None

    tries = 6
    rejected = 0
    res: list[int | None] = []

    for _ in range(tries):
        try:
            add(3, 5)
        except BucketFullError:
            rejected += 1
        else:
            res.append(None)

    assert rejected == tries - (bucket_size + quota)
    assert len(res) == tries - rejected
