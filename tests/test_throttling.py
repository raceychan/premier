import logging
import time

import pytest

from premier import BucketFullError, QuotaExceedsError, Throttler

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


# @pytest.mark.skip
def test_throttler_do_not_raise_error(throttler: Throttler):
    throttler.clear()

    @throttler.fixed_window(quota=2, duration=3)
    def add(a: int, b: int) -> int:
        res = a + b
        return res

    tries = 3
    res = [add(3, 5) for _ in range(tries - 1)]
    time.sleep(3)
    res.append(add(3, 5))
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


# def test_throttler_with_token_bucket(throttler: Throttler):

#     @throttler.token_bucket(quota=3, duration=5, keymaker=_keymaker)
#     def add(a: int, b: int) -> int:
#         res = a + b
#         return res

#     tries = 4
#     res: list[int] = []
#     try:
#         for _ in range(tries):
#             res.append(add(3, 5))
#     except QuotaExceedsError:
#         time.sleep(5 / 3)
#         res.append(add(3, 5))

#     assert len(res) == tries


# BUG: this would leave "p" and "t" to redis and won't be removed
def test_throttler_with_leaky_bucket(throttler: Throttler, logger: logging.Logger):
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
        time.sleep(0.1)

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
