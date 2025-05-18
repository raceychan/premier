import asyncio
import json
import logging
from pathlib import Path

import pytest

from premier import  AsyncDefaultHandler
from premier import throttler as _throttler


def read_envs(file: Path) -> dict[str, str]:
    envs = {
        key: value
        for line in file.read_text().split("\n")
        if line and not line.startswith("#")
        for key, value in [line.split("=", 1)]
    }
    return envs


envs = read_envs(Path("./.env"))


@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def logger():
    _logger = logging.getLogger("prmeier-test")
    _logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_format = logging.Formatter(
        "%(name)s | %(levelname)s | %(asctime)s | %(message)s"
    )
    console_handler.setFormatter(console_format)

    _logger.addHandler(console_handler)

    return _logger


<<<<<<< HEAD
@pytest.fixture(scope="session")
def redis_handler():
    redis = Redis.from_url(envs["REDIS_URL"])  # type: ignore
    handler = RedisHandler(redis=redis)
    yield handler
    handler.close()


=======
>>>>>>> version/0.4.1
@pytest.fixture(scope="function")
def throttler():
    _throttler.config(keyspace="test")
    yield _throttler


<<<<<<< HEAD
@pytest.fixture(scope="function")
async def aredishandler():
    aredis = AIORedis.from_url(envs["REDIS_URL"])
    handler = AsyncRedisHandler(aredis)
=======
>>>>>>> version/0.4.1

@pytest.fixture
async def async_handler():
    handler = AsyncDefaultHandler()
    yield handler
    await handler.close()


@pytest.fixture
async def aiothrottler(async_handler: AsyncDefaultHandler):
    _throttler.config(aiohandler=async_handler, keyspace="premier-pytest")
    yield _throttler
    await _throttler.aclear()
