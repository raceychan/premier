import asyncio

import pytest

from premier import (  # BucketFullError,; QuotaExceedsError,
    AsyncRedisHandler,
    ThrottleAlgo,
    Throttler,
)
from premier import throttler as _throttler

url = "redis://@192.168.50.22:7379/0"

pytest.skip(allow_module_level=True)


@pytest.fixture
async def aiohandler():
    handler = AsyncRedisHandler.from_url(url)

    yield handler

    await handler.close()


@pytest.fixture
async def throttler(aiohandler: AsyncRedisHandler):
    _throttler.config(aiohandler=aiohandler, keyspace="premier-pytest")
    yield _throttler
    await _throttler.aclear()


async def test_async_throttler_with_leaky_bucket(throttler: Throttler):
    bucket_size = 5
    quota = 1

    @throttler.throttle(
        throttle_algo=ThrottleAlgo.LEAKY_BUCKET,
        quota=quota,
        duration=1,
        bucket_size=bucket_size,
    )
    async def add(a: int, b: int) -> None:
        await asyncio.sleep(0)
        print(f"executed, {a+b=}")

    todo = set[asyncio.Task[None]]()
    rejected = 0

    tries = 8
    for _ in range(tries):
        task = asyncio.create_task(add(3, 5))
        todo.add(task)
    done, wait = await asyncio.wait(todo)

    rejected = [e for e in done if e.exception()]
    consumed = bucket_size + quota
    assert len(rejected) == tries - consumed
