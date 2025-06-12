from unittest.mock import AsyncMock, patch

import pytest

from premier.retry.retry import retry


class CustomException(Exception):
    pass


@pytest.mark.asyncio
async def test_retry_basic_success():
    """Test basic retry functionality"""
    mock_func = AsyncMock(return_value="success")

    with patch("asyncio.sleep"):

        @retry(max_attempts=3, wait=1)
        async def test_func():
            return await mock_func()

        result = await test_func()

    assert result == "success"
    assert mock_func.call_count == 1


@pytest.mark.asyncio
async def test_retry_with_failures():
    """Test retry with failures then success"""
    mock_func = AsyncMock(side_effect=[Exception("fail"), "success"])

    with patch("asyncio.sleep"):

        @retry(max_attempts=3, wait=1)
        async def test_func():
            return await mock_func()

        result = await test_func()

    assert result == "success"
    assert mock_func.call_count == 2


@pytest.mark.asyncio
async def test_retry_max_attempts():
    """Test retry reaches max attempts"""
    mock_func = AsyncMock(side_effect=CustomException("always fails"))

    with patch("asyncio.sleep"):

        @retry(max_attempts=2, wait=1)
        async def test_func():
            return await mock_func()

        with pytest.raises(CustomException):
            await test_func()

    assert mock_func.call_count == 2


@pytest.mark.asyncio
async def test_retry_wait_strategies():
    """Test different wait strategies"""
    mock_func = AsyncMock(side_effect=[Exception("fail"), "success"])

    # Test list wait strategy
    with patch("asyncio.sleep") as mock_sleep:

        @retry(max_attempts=2, wait=[1, 2])
        async def test_func():
            return await mock_func()

        result = await test_func()
        assert result == "success"
        mock_sleep.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_retry_callable_wait():
    """Test callable wait strategy"""
    mock_func = AsyncMock(side_effect=[Exception("fail"), "success"])

    def backoff(attempt: int):
        return attempt + 1

    with patch("asyncio.sleep") as mock_sleep:

        @retry(max_attempts=2, wait=backoff)
        async def test_func():
            return await mock_func()

        result = await test_func()
        assert result == "success"
        mock_sleep.assert_called_once_with(1)  # backoff(0) = 1


@pytest.mark.asyncio
async def test_retry_specific_exceptions():
    """Test retry only catches specified exceptions"""

    @retry(max_attempts=3, wait=1, exceptions=(ValueError,))
    async def test_func():
        raise TypeError("should not retry")

    with pytest.raises(TypeError):
        await test_func()
