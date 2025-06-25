import pytest
from types import FunctionType, MethodType
from typing import Any, Dict

from premier.features.throttler.interface import (
    _func_keymaker,
    _make_key,
    ThrottleAlgo,
    ThrottleInfo,
    LBThrottleInfo,
    Duration,
    AlgoTypeEnum,
)


class TestFuncKeymaker:
    def test_function_keymaker(self):
        """Test _func_keymaker with regular function"""
        def test_func():
            pass
        
        result = _func_keymaker(test_func, ThrottleAlgo.FIXED_WINDOW, "test_keyspace")
        expected = f"test_keyspace:fixed_window:{test_func.__module__}:test_func"
        assert result == expected
        
    def test_method_keymaker(self):
        """Test _func_keymaker with method"""
        class TestClass:
            def test_method(self):
                pass
                
        instance = TestClass()
        method = instance.test_method
        
        result = _func_keymaker(method, ThrottleAlgo.TOKEN_BUCKET, "test_keyspace")
        expected = f"test_keyspace:token_bucket:{method.__module__}:TestClass:test_method"
        assert result == expected
        
    def test_callable_without_name(self):
        """Test _func_keymaker with callable without __name__"""
        class CallableWithoutName:
            def __call__(self):
                pass
                
        callable_obj = CallableWithoutName()
        # Remove __name__ attribute to test fallback
        if hasattr(callable_obj, '__name__'):
            delattr(callable_obj, '__name__')
            
        result = _func_keymaker(callable_obj, ThrottleAlgo.LEAKY_BUCKET, "test_keyspace")
        expected = f"test_keyspace:leaky_bucket:{callable_obj.__module__}:"
        assert result == expected
        
    def test_callable_with_name(self):
        """Test _func_keymaker with callable that has __name__"""
        class CallableWithName:
            __name__ = "custom_callable"
            
            def __call__(self):
                pass
                
        callable_obj = CallableWithName()
        
        result = _func_keymaker(callable_obj, ThrottleAlgo.SLIDING_WINDOW, "test_keyspace")
        expected = f"test_keyspace:sliding_window:{callable_obj.__module__}:custom_callable"
        assert result == expected


class TestMakeKey:
    def test__make_key_without_keymaker(self):
        """Test _make_key without custom keymaker"""
        def test_func():
            pass
            
        result = _make_key(
            test_func,
            ThrottleAlgo.FIXED_WINDOW,
            "test_keyspace",
            None,
            (1, 2),
            {"key": "value"}
        )
        
        expected = _func_keymaker(test_func, ThrottleAlgo.FIXED_WINDOW, "test_keyspace")
        assert result == expected
        
    def test__make_key_with_keymaker(self):
        """Test _make_key with custom keymaker"""
        def test_func():
            pass
            
        def custom_keymaker(a, b, key=None):
            return f"{a}_{b}_{key}"
            
        result = _make_key(
            test_func,
            ThrottleAlgo.TOKEN_BUCKET,
            "test_keyspace",
            custom_keymaker,
            (1, 2),
            {"key": "value"}
        )
        
        base_key = _func_keymaker(test_func, ThrottleAlgo.TOKEN_BUCKET, "test_keyspace")
        expected = f"{base_key}:1_2_value"
        assert result == expected


class TestThrottleInfo:
    def test_throttle_info_creation(self):
        """Test ThrottleInfo creation and properties"""
        def test_func():
            pass
            
        info = ThrottleInfo(
            func=test_func,
            keyspace="test_keyspace",
            algo=ThrottleAlgo.FIXED_WINDOW
        )
        
        assert info.func is test_func
        assert info.keyspace == "test_keyspace"
        assert info.algo == ThrottleAlgo.FIXED_WINDOW
        
    def test_throttle_info_funckey_property(self):
        """Test ThrottleInfo funckey property"""
        def test_func():
            pass
            
        info = ThrottleInfo(
            func=test_func,
            keyspace="test_keyspace",
            algo=ThrottleAlgo.SLIDING_WINDOW
        )
        
        expected = _func_keymaker(test_func, ThrottleAlgo.SLIDING_WINDOW, "test_keyspace")
        assert info.funckey == expected
        
    def test_throttle_info__make_key_without_keymaker(self):
        """Test ThrottleInfo _make_key without keymaker"""
        def test_func():
            pass
            
        info = ThrottleInfo(
            func=test_func,
            keyspace="test_keyspace",
            algo=ThrottleAlgo.TOKEN_BUCKET
        )
        
        result = info.make_key(None, (1, 2), {"key": "value"})
        assert result == info.funckey
        
    def test_throttle_info__make_key_with_keymaker(self):
        """Test ThrottleInfo _make_key with keymaker"""
        def test_func():
            pass
            
        def custom_keymaker(a, b, key=None):
            return f"{a}_{b}_{key}"
            
        info = ThrottleInfo(
            func=test_func,
            keyspace="test_keyspace",
            algo=ThrottleAlgo.LEAKY_BUCKET
        )
        
        result = info.make_key(custom_keymaker, (1, 2), {"key": "value"})
        expected = f"{info.funckey}:1_2_value"
        assert result == expected


class TestLBThrottleInfo:
    def test_lb_throttle_info_creation(self):
        """Test LBThrottleInfo creation with bucket_size"""
        def test_func():
            pass
            
        info = LBThrottleInfo(
            func=test_func,
            keyspace="test_keyspace",
            algo=ThrottleAlgo.LEAKY_BUCKET,
            bucket_size=10
        )
        
        assert info.func is test_func
        assert info.keyspace == "test_keyspace"
        assert info.algo == ThrottleAlgo.LEAKY_BUCKET
        assert info.bucket_size == 10
        
    def test_lb_throttle_info_inherits_from_throttle_info(self):
        """Test that LBThrottleInfo inherits ThrottleInfo functionality"""
        def test_func():
            pass
            
        info = LBThrottleInfo(
            func=test_func,
            keyspace="test_keyspace",
            algo=ThrottleAlgo.LEAKY_BUCKET,
            bucket_size=5
        )
        
        # Should have funckey property from parent
        expected = _func_keymaker(test_func, ThrottleAlgo.LEAKY_BUCKET, "test_keyspace")
        assert info.funckey == expected
        
        # Should have _make_key method from parent
        def custom_keymaker(x):
            return str(x)
            
        result = info.make_key(custom_keymaker, (42,), {})
        expected = f"{info.funckey}:42"
        assert result == expected


class TestDuration:
    def test_duration_creation(self):
        """Test Duration creation with keyword arguments"""
        duration = Duration(seconds=30, minutes=5, hours=2, days=1)
        
        assert duration.seconds == 30
        assert duration.minutes == 5
        assert duration.hours == 2
        assert duration.days == 1
        
    def test_duration_from_seconds_simple(self):
        """Test Duration.from_seconds with simple values"""
        duration = Duration.from_seconds(90)  # 1 minute 30 seconds
        
        assert duration.seconds == 30
        assert duration.minutes == 1
        assert duration.hours == 0
        assert duration.days == 0
        
    def test_duration_from_seconds_complex(self):
        """Test Duration.from_seconds with complex conversion"""
        # 1 day + 2 hours + 5 minutes + 30 seconds = 93930 seconds
        total_seconds = 86400 + 7200 + 300 + 30
        duration = Duration.from_seconds(total_seconds)
        
        assert duration.seconds == 30
        assert duration.minutes == 5
        assert duration.hours == 2
        assert duration.days == 1
        
    def test_duration_from_seconds_edge_cases(self):
        """Test Duration.from_seconds edge cases"""
        # Zero seconds
        duration = Duration.from_seconds(0)
        assert duration.seconds == 0
        assert duration.minutes == 0
        assert duration.hours == 0
        assert duration.days == 0
        
        # Exactly one day
        duration = Duration.from_seconds(86400)
        assert duration.seconds == 0
        assert duration.minutes == 0
        assert duration.hours == 0
        assert duration.days == 1
        
        # Multiple days
        duration = Duration.from_seconds(86400 * 3 + 3661)  # 3 days + 1 hour + 1 minute + 1 second
        assert duration.seconds == 1
        assert duration.minutes == 1
        assert duration.hours == 1
        assert duration.days == 3
        
    def test_duration_as_seconds(self):
        """Test Duration.as_seconds conversion"""
        duration = Duration(seconds=30, minutes=5, hours=2, days=1)
        
        expected = 86400 + 7200 + 300 + 30  # 1 day + 2 hours + 5 minutes + 30 seconds
        assert duration.as_seconds() == expected
        
    def test_duration_round_trip(self):
        """Test Duration round trip conversion"""
        original_seconds = 93930  # Random value
        duration = Duration.from_seconds(original_seconds)
        converted_back = duration.as_seconds()
        
        assert converted_back == original_seconds


class TestAlgoTypeEnum:
    def test_algo_type_enum_generate_next_value(self):
        """Test AlgoTypeEnum._generate_next_value_ method"""
        result = AlgoTypeEnum._generate_next_value_("TEST_VALUE", 1, 0, [])
        assert result == "test_value"
        
    def test_throttle_algo_values(self):
        """Test ThrottleAlgo enum values"""
        assert ThrottleAlgo.TOKEN_BUCKET == "token_bucket"
        assert ThrottleAlgo.LEAKY_BUCKET == "leaky_bucket"
        assert ThrottleAlgo.FIXED_WINDOW == "fixed_window"
        assert ThrottleAlgo.SLIDING_WINDOW == "sliding_window"
        
    def test_throttle_algo_is_string(self):
        """Test that ThrottleAlgo values are strings"""
        for algo in ThrottleAlgo:
            assert isinstance(algo, str)
            assert isinstance(algo.value, str)


class TestProtocols:
    def test_sync_func_protocol(self):
        """Test SyncFunc protocol compliance"""
        from premier.features.throttler.interface import SyncFunc
        
        def test_func(x: int, y: str) -> bool:
            return True
            
        # Test that function has required attributes
        assert hasattr(test_func, '__name__')
        assert callable(test_func)
        
        # Test call
        result = test_func(1, "test")
        assert result is True
        
    def test_async_func_protocol(self):
        """Test AsyncFunc protocol compliance"""
        from premier.features.throttler.interface import AsyncFunc
        import asyncio
        
        async def test_async_func(x: int, y: str) -> bool:
            return True
            
        # Test that function has required attributes
        assert hasattr(test_async_func, '__name__')
        assert callable(test_async_func)
        
        # Test async call
        async def run_test():
            result = await test_async_func(1, "test")
            assert result is True
            
        asyncio.run(run_test())
        


class TestThrottleHandlerDispatch:
    def test_async_throttle_handler_dispatch_fixed_window(self):
        """Test AsyncThrottleHandler dispatch for fixed window"""
        from premier.features.throttler.interface import AsyncThrottleHandler
        
        class MockAsyncHandler(AsyncThrottleHandler):
            async def fixed_window(self, key: str, quota: int, duration: int):
                return "async_fixed_window_result"
                
            async def sliding_window(self, key: str, quota: int, duration: int):
                return "async_sliding_window_result"
                
            async def token_bucket(self, key: str, quota: int, duration: int):
                return "async_token_bucket_result"
                
            def leaky_bucket(self, key: str, bucket_size: int, quota: int, duration: int):
                async def scheduler():
                    return "async_leaky_bucket_result"
                return scheduler
                
            async def clear(self, keyspace: str = "") -> None:
                pass
                
            async def close(self) -> None:
                pass
                
        handler = MockAsyncHandler()
        
        # Test dispatch for each algorithm
        assert handler.dispatch(ThrottleAlgo.FIXED_WINDOW) == handler.fixed_window
        assert handler.dispatch(ThrottleAlgo.SLIDING_WINDOW) == handler.sliding_window
        assert handler.dispatch(ThrottleAlgo.TOKEN_BUCKET) == handler.token_bucket
        
        # Test unsupported algorithm
        with pytest.raises(NotImplementedError):
            handler.dispatch(ThrottleAlgo.LEAKY_BUCKET)
            
    def test_async_throttle_handler_dispatch(self):
        """Test AsyncThrottleHandler dispatch"""
        from premier.features.throttler.interface import AsyncThrottleHandler
        
        class MockAsyncHandler(AsyncThrottleHandler):
            async def fixed_window(self, key: str, quota: int, duration: int):
                return "async_fixed_window_result"
                
            async def sliding_window(self, key: str, quota: int, duration: int):
                return "async_sliding_window_result"
                
            async def token_bucket(self, key: str, quota: int, duration: int):
                return "async_token_bucket_result"
                
            async def leaky_bucket(self, key: str, bucket_size: int, quota: int, duration: int):
                async def scheduler():
                    return "async_leaky_bucket_result"
                return scheduler
                
            async def clear(self, keyspace: str = "") -> None:
                pass
                
            async def close(self) -> None:
                pass
                
        handler = MockAsyncHandler()
        
        # Test dispatch for each algorithm
        assert handler.dispatch(ThrottleAlgo.FIXED_WINDOW) == handler.fixed_window
        assert handler.dispatch(ThrottleAlgo.SLIDING_WINDOW) == handler.sliding_window
        assert handler.dispatch(ThrottleAlgo.TOKEN_BUCKET) == handler.token_bucket
        
        # Test unsupported algorithm
        with pytest.raises(NotImplementedError):
            handler.dispatch(ThrottleAlgo.LEAKY_BUCKET)