import asyncio
import pytest
import time
from unittest.mock import AsyncMock

from premier.retry import CircuitBreaker, CircuitBreakerOpenException


class TestCircuitBreaker:
    def test_initialization(self):
        cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30.0,
            expected_exception=ValueError,
        )
        
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 30.0
        assert cb.expected_exception == ValueError
        assert cb.failure_count == 0
        assert cb.last_failure_time is None
        assert cb.state == "CLOSED"

    def test_default_initialization(self):
        cb = CircuitBreaker()
        
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 60.0
        assert cb.expected_exception == Exception
        assert cb.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_successful_calls_keep_circuit_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        
        @cb
        async def success_func():
            return "success"
        
        # Multiple successful calls should keep circuit closed
        for _ in range(10):
            result = await success_func()
            assert result == "success"
            assert cb.state == "CLOSED"
            assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold_failures(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0, expected_exception=ValueError)
        
        @cb
        async def failing_func():
            raise ValueError("Test error")
        
        # First 3 failures should not open circuit but increment failure count
        for i in range(3):
            with pytest.raises(ValueError):
                await failing_func()
            
            if i < 2:  # Before threshold
                assert cb.state == "CLOSED"
                assert cb.failure_count == i + 1
            else:  # At threshold
                assert cb.state == "OPEN"
                assert cb.failure_count == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_exception(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0, expected_exception=ValueError)
        
        @cb
        async def failing_func():
            raise ValueError("Test error")
        
        # Trigger circuit opening
        for _ in range(2):
            with pytest.raises(ValueError):
                await failing_func()
        
        assert cb.state == "OPEN"
        
        # Further calls should raise CircuitBreakerOpenException
        with pytest.raises(CircuitBreakerOpenException):
            await failing_func()

    @pytest.mark.asyncio
    async def test_circuit_recovery_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1, expected_exception=ValueError)
        
        call_count = 0
        
        @cb
        async def recovery_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ValueError("Initial failures")
            return "recovered"
        
        # Trigger circuit opening
        for _ in range(2):
            with pytest.raises(ValueError):
                await recovery_func()
        
        assert cb.state == "OPEN"
        
        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        
        # Next call should attempt recovery (HALF_OPEN state)
        result = await recovery_func()
        assert result == "recovered"
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1, expected_exception=ValueError)
        
        call_count = 0
        
        @cb
        async def half_open_fail_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:  # First 2 to open, 3rd to test half-open failure
                raise ValueError("Test error")
            return "success"
        
        # Trigger circuit opening
        for _ in range(2):
            with pytest.raises(ValueError):
                await half_open_fail_func()
        
        assert cb.state == "OPEN"
        
        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        
        # Half-open call that fails should reopen circuit
        with pytest.raises(ValueError):
            await half_open_fail_func()
        
        assert cb.state == "OPEN"

    @pytest.mark.asyncio
    async def test_only_expected_exceptions_trigger_circuit(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0, expected_exception=ValueError)
        
        @cb
        async def mixed_exception_func(exception_type):
            if exception_type == "value_error":
                raise ValueError("Value error")
            elif exception_type == "type_error":
                raise TypeError("Type error")
            return "success"
        
        # TypeError should not trigger circuit breaker
        with pytest.raises(TypeError):
            await mixed_exception_func("type_error")
        
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0
        
        # ValueError should trigger circuit breaker
        with pytest.raises(ValueError):
            await mixed_exception_func("value_error")
        
        assert cb.state == "CLOSED"
        assert cb.failure_count == 1

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0, expected_exception=ValueError)
        
        call_count = 0
        
        @cb
        async def reset_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First failure")
            return "success"
        
        # First call fails
        with pytest.raises(ValueError):
            await reset_func()
        
        assert cb.failure_count == 1
        
        # Second call succeeds - should reset failure count
        result = await reset_func()
        assert result == "success"
        assert cb.failure_count == 0
        assert cb.state == "CLOSED"

    def test_should_attempt_reset_logic(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0)
        
        # No previous failure
        assert cb._should_attempt_reset() is True
        
        # Recent failure
        cb.last_failure_time = time.time()
        assert cb._should_attempt_reset() is False
        
        # Old failure
        cb.last_failure_time = time.time() - 2.0
        assert cb._should_attempt_reset() is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_async_mock(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        mock_func = AsyncMock(side_effect=ValueError("Mock error"))
        decorated_func = cb(mock_func)
        
        # Trigger circuit opening
        for _ in range(2):
            with pytest.raises(ValueError):
                await decorated_func()
        
        assert cb.state == "OPEN"
        assert mock_func.call_count == 2
        
        # Circuit is open, should not call the function
        with pytest.raises(CircuitBreakerOpenException):
            await decorated_func()
        
        assert mock_func.call_count == 2  # Should not increment