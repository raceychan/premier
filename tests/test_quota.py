# import asyncio
import time

import pytest
from redis import Redis

from premier import BucketFullError
from premier import MemoryCounter as MemoryCounter
from premier import QuotaExceedsError
from premier import RedisCounter as RedisCounter
from premier import fixed_window, throttled, throttler, token_bucket

# from redis.asyncio.client import Redis as AIORedis


url = "redis://@192.168.50.22:7379/0"
redis = Redis.from_url(url)  # type: ignore


throttler.config(counter=RedisCounter(redis=redis))


def test_throttle_raise_error():
    quota = 3

    @throttled(quota=quota, duration_s=5)
    def add(a: int, b: int) -> int:
        res = a + b
        return res

    tries = 4
    with pytest.raises(QuotaExceedsError):
        res = [add(3, 5) for _ in range(tries)]
        assert len(res) <= quota


def test_method():
    quota = 3

    class T:
        @fixed_window(quota=quota, duration_s=5)
        def add(self, a: int, b: int) -> int:
            res = a + b
            return res

    tries = 4
    t = T()
    with pytest.raises(QuotaExceedsError):
        res = [t.add(3, 5) for _ in range(tries)]
        assert len(res) <= quota


@pytest.mark.skip
async def test_throttler_do_not_raise_error():
    throttler.clear()

    @fixed_window(quota=3, duration_s=5)
    def add(a: int, b: int) -> int:
        res = a + b
        return res

    tries = 4
    res = [add(3, 5) for _ in range(tries - 1)]
    time.sleep(5)
    res.append(add(3, 5))
    assert len(res) == tries


async def test_throttler_do_not_raise_error_with_interval():
    throttler.clear()

    @fixed_window(quota=3, duration_s=5)
    def add(a: int, b: int) -> int:
        res = a + b
        return res

    tries = 2
    res = [add(3, 5) for _ in range(tries)]
    assert len(res) == tries


async def test_throttler_with_keymaker():

    @fixed_window(quota=3, duration_s=5, keymaker=_keymaker)
    def add(a: int, b: int) -> int:
        res = a + b
        return res

    tries = 2
    res = [add(3, 5) for _ in range(tries)]
    assert len(res) == tries


def _keymaker(a: int, b: int) -> str:
    return f"{a}"


@pytest.mark.skip
async def test_throttler_with_token_bucket():

    @token_bucket(quota=3, duration_s=5, keymaker=_keymaker)
    def add(a: int, b: int) -> int:
        res = a + b
        return res

    tries = 4
    res: list[int] = []
    try:
        for _ in range(tries):
            res.append(add(3, 5))
    except QuotaExceedsError:
        time.sleep(5 / 3)
        res.append(add(3, 5))

    assert len(res) == tries


async def test_throttler_with_leaky_bucket():
    throttler.clear()
    bucket_size = 5
    quota = 1
    duration = 1

    @throttler.leaky_bucket(
        bucket_size=bucket_size,
        quota=quota,
        duration_s=duration,
        keymaker=_keymaker,
    )
    def add(a: int, b: int) -> int:
        time.sleep(0.1)
        res = a + b
        return res

    tries = 8
    res: list[int | None] = []

    rejected = 0
    for _ in range(tries):
        try:
            r = add(3, 5)
            res.append(r)
        except BucketFullError:
            print("\nBuckete is Full")
            rejected += 1

    assert len(res) == bucket_size + quota
    assert rejected == tries - (bucket_size + quota)


# async def test_async_throttler_with_leaky_bucket():
#     throttler.clear()

#     @leaky_bucket(bucket_size=5, quota=1, duration_s=1, keymaker=lambda a, b: f"{a}")
#     async def add(a: int, b: int) -> int:
#         await asyncio.sleep(0.1)
#         res = a + b
#         return res

#     tries = 8
#     res = []

#     rejected = 0
#     for _ in range(tries):
#         try:
#             r = await add(3, 5)
#             res.append(r)
#         except BucketFullError:
#             print("\nBuckete is Full")
#             rejected += 1

#     print(f"\n{len(res)} func executed")
#     assert rejected == 3
