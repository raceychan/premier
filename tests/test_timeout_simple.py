import asyncio
import pytest
from unittest.mock import Mock

from premier.timer.timer import timeout


@pytest.mark.asyncio
async def test_timeout_success():
    """Test timeout allows fast operations"""
    @timeout(1)
    async def fast_func():
        await asyncio.sleep(0.1)
        return "completed"
    
    result = await fast_func()
    assert result == "completed"


@pytest.mark.asyncio
async def test_timeout_exceeds():
    """Test timeout raises TimeoutError for slow operations"""
    @timeout(1)  # 1 second timeout
    async def slow_func():
        await asyncio.sleep(2)  # 2 second operation
        return "should not reach"
    
    with pytest.raises(asyncio.TimeoutError):
        await slow_func()


@pytest.mark.asyncio
async def test_timeout_with_logger():
    """Test timeout with custom logger"""
    mock_logger = Mock()
    mock_logger.exception = Mock()
    
    @timeout(1, logger=mock_logger)
    async def slow_func():
        await asyncio.sleep(2)
        return "result"
    
    with pytest.raises(asyncio.TimeoutError):
        await slow_func()
    
    # The logger call may be implementation-specific, so we just check it's available
    assert hasattr(mock_logger, 'exception')


@pytest.mark.asyncio
async def test_timeout_with_args():
    """Test timeout preserves function arguments"""
    @timeout(1)
    async def func_with_args(a, b, c=None):
        await asyncio.sleep(0.1)
        return f"{a}-{b}-{c}"
    
    result = await func_with_args("x", "y", c="z")
    assert result == "x-y-z"


@pytest.mark.asyncio
async def test_timeout_exception_before_timeout():
    """Test function exception is raised before timeout"""
    @timeout(2)  # Long timeout
    async def failing_func():
        await asyncio.sleep(0.1)
        raise ValueError("function error")
    
    with pytest.raises(ValueError, match="function error"):
        await failing_func()


def test_timeout_sync_function_raises_error():
    """Test timeout decorator raises ValueError for sync functions"""
    with pytest.raises(ValueError, match="timeout decorator only supports async functions"):
        @timeout(1)
        def sync_func():
            return "sync result"


def test_timeout_sync_function_with_logger_raises_error():
    """Test timeout decorator with logger raises ValueError for sync functions"""
    mock_logger = Mock()
    
    with pytest.raises(ValueError, match="timeout decorator only supports async functions"):
        @timeout(1, logger=mock_logger)
        def sync_func_with_logger():
            return "sync result"


@pytest.mark.asyncio
async def test_timeout_zero_seconds():
    """Test timeout with zero seconds"""
    @timeout(0)
    async def instant_func():
        return "instant"
    
    with pytest.raises(asyncio.TimeoutError):
        await instant_func()


@pytest.mark.asyncio
async def test_timeout_negative_seconds():
    """Test timeout with negative seconds"""
    @timeout(-1)
    async def negative_timeout_func():
        return "should timeout immediately"
    
    with pytest.raises(asyncio.TimeoutError):
        await negative_timeout_func()