import asyncio
import logging

import pytest as pytest

from premier import BucketFullError, Throttler


async def test_async_throttler_with_leaky_bucket(
    aiothrottler: Throttler, logger: logging.Logger
):
    bucket_size = 3
    quota = 1
    duration = 1

    @aiothrottler.leaky_bucket(
        quota=quota,
        duration=duration,
        bucket_size=bucket_size,
    )
    async def add(a: int, b: int) -> None:
        # Remove sleep to speed up test
        pass

    todo = set[asyncio.Task[None]]()
    rejected = 0

    tries = 6
    for _ in range(tries):
        task = asyncio.create_task(add(3, 5))
        todo.add(task)
    done, _ = await asyncio.wait(todo)

    for e in done:
        try:
            e.result()
        except BucketFullError:
            rejected += 1

    # In leaky bucket: bucket_size allows immediate tasks, quota determines rate
    # So we expect bucket_size tasks to succeed immediately, rest rejected
    expected_rejected = tries - bucket_size
    assert rejected == expected_rejected
