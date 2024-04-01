# import asyncio
import pytest

# from redis.asyncio.client import Redis
from redis import Redis

from pythrottler import (
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


async def test_throttle_raise_error():
    throttler.config(quota_counter=MemoryCounter())
    quota = 3

    @limits(quota=quota, duration_s=5)
    def add(a: int, b: int) -> int:
        res = a + b
        return res

    tries = 4
    with pytest.raises(QuotaExceedsError) as qe:
        res = [add(3, 5) for _ in range(tries)]
        assert len(res) <= quota


async def test_throttler_do_not_raise_error():
    quota = 3

    @limits(quota=quota, duration_s=5)
    def add(a: int, b: int) -> int:
        res = a + b
        return res

    tries = 2
    res = [add(3, 5) for _ in range(tries)]
    assert len(res) == tries
