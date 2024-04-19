import asyncio

import pytest

from premier import (
    AsyncRedisHandler,
    BucketFullError,
    QuotaExceedsError,
    ThrottleAlgo,
    _Throttler,
)
from premier import throttler as _throttler

url = "redis://@192.168.50.22:7379/0"


@pytest.fixture
def aiohandler():
    return AsyncRedisHandler.from_url(url)


@pytest.fixture
def throttler(aiohandler: AsyncRedisHandler):
    _throttler.config(aiohandler=aiohandler, keyspace="test")
    return _throttler


async def test_async_throttler_with_leaky_bucket(throttler: _Throttler):
    throttler.clear()

    @throttler.throttle(
        throttle_algo=ThrottleAlgo.FIXED_WINDOW,
        quota=1,
        duration=1,
    )
    async def add(a: int, b: int) -> int:
        await asyncio.sleep(0.1)
        res = a + b
        return res

    tries = 8
    res: list[int] = []

    rejected = 0
    for _ in range(tries):
        try:
            r = await add(3, 5)
            res.append(r)
        except (BucketFullError, QuotaExceedsError):
            print("\nBuckete is Full")
            rejected += 1

    print(f"\n{len(res)} func executed")
    assert rejected == 7
    print(res)
