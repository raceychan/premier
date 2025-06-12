import asyncio
import logging
from pathlib import Path

import pytest

from premier.throttler.throttler import throttler as _throttler
from premier.throttler.handler import AsyncDefaultHandler
from premier.providers import AsyncInMemoryCache


def read_envs(file: Path) -> dict[str, str]:
    envs = {
        key: value
        for line in file.read_text().split("\n")
        if line and not line.startswith("#")
        for key, value in [line.split("=", 1)]
    }
    return envs


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
    cache = AsyncInMemoryCache()
    _throttler.config(handler=AsyncDefaultHandler(cache), keyspace="test")
    yield _throttler


@pytest.fixture
async def async_handler():
    cache = AsyncInMemoryCache()
    handler = AsyncDefaultHandler(cache)
    yield handler
    await handler.close()


@pytest.fixture
async def aiothrottler(async_handler: AsyncDefaultHandler):
    _throttler.config(handler=async_handler, keyspace="premier-pytest")
    yield _throttler
    await _throttler.clear()
