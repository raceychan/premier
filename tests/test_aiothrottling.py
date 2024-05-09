import asyncio

import pytest

from premier import ThrottleAlgo, Throttler  # BucketFullError,; QuotaExceedsError,

pytest.skip(allow_module_level=True)


async def test_async_throttler_with_leaky_bucket(aiothrottler: Throttler):
    bucket_size = 5
    quota = 1

    @aiothrottler.throttle(
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
    done, _ = await asyncio.wait(todo)

    rejected = [e for e in done if e.exception()]
    consumed = bucket_size + quota
    assert len(rejected) == tries - consumed
