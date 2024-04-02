# import asyncio
import time

import pytest
from redis import Redis
from redis.asyncio.client import Redis as AIORedis

from premier import (
    MemoryCounter,
    QuotaExceedsError,
    RedisCounter,
    ThrottleAlgo,
    limits,
    throttler,
)

url = "redis://@192.168.50.22:7379/0"
redis = Redis.from_url(url)

# throttler.config(quota_counter=RedisCounter(redis=redis))

throttler.config(counter=MemoryCounter())


async def test_throttle_raise_error():
    quota = 3

    @limits(quota=quota, duration_s=5)
    def add(a: int, b: int) -> int:
        res = a + b
        return res

    tries = 4
    with pytest.raises(QuotaExceedsError) as qe:
        res = [add(3, 5) for _ in range(tries)]
        assert len(res) <= quota


@pytest.mark.skip
async def test_throttler_do_not_raise_error():
    throttler.clear()

    @limits(quota=3, duration_s=5)
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
    ...

    @limits(quota=3, duration_s=5)
    def add(a: int, b: int) -> int:
        res = a + b
        return res

    tries = 2
    res = [add(3, 5) for _ in range(tries)]
    assert len(res) == tries


async def test_throttler_with_keymaker():

    @limits(quota=3, duration_s=5, keymaker=lambda a, b: f"{a}")
    def add(a: int, b: int) -> int:
        res = a + b
        return res

    tries = 2
    res = [add(3, 5) for _ in range(tries)]
    assert len(res) == tries
