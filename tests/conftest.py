import pytest
from redis import Redis

from premier import AsyncRedisHandler, DefaultHandler, RedisHandler
from premier import throttler as _throttler

REDIS_URL = "redis://@192.168.50.22:7379/0"


@pytest.fixture
def redis_handler():
    redis = Redis.from_url(REDIS_URL)  # type: ignore
    handler = RedisHandler(redis=redis)
    yield handler
    handler.close()


@pytest.fixture
def throttler(redis_handler: RedisHandler):
    _throttler.config(handler=redis_handler, keyspace="test")
    yield _throttler
    _throttler.clear()


@pytest.fixture
async def aiohandler():
    handler = AsyncRedisHandler.from_url(url)

    yield handler

    await handler.close()


@pytest.fixture
async def aiothrottler(aiohandler: AsyncRedisHandler):
    _throttler.config(aiohandler=aiohandler, keyspace="premier-pytest")
    yield _throttler
    await _throttler.aclear()
