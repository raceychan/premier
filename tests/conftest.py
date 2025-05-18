import asyncio
import logging

import pytest

from premier import  AsyncDefaultHandler
from premier import throttler as _throttler

REDIS_URL = "redis://@192.168.50.22:7379/0"


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


@pytest.fixture(scope="function")
def throttler():
    _throttler.config(keyspace="test")
    yield _throttler



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
