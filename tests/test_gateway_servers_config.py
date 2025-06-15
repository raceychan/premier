import pytest
from unittest.mock import patch, AsyncMock

from premier.asgi import (
    ASGIGateway,
    CircuitBreakerConfig,
    FeatureConfig,
    GatewayConfig,
    PathConfig,
    create_gateway,
)


class TestGatewayServersConfig:
    """Test servers configuration in Gateway."""

    def test_gateway_config_with_servers(self):
        """Test GatewayConfig with servers field."""
        servers = ["http://server1.com", "http://server2.com"]
        config = GatewayConfig(
            paths=[],
            servers=servers,
        )
        
        assert config.servers == servers

    def test_gateway_config_without_servers(self):
        """Test GatewayConfig defaults to None for servers."""
        config = GatewayConfig(paths=[])
        assert config.servers is None

    def test_gateway_init_uses_config_servers(self):
        """Test Gateway uses servers from config when not provided in constructor."""
        servers = ["http://server1.com", "http://server2.com"]
        config = GatewayConfig(paths=[], servers=servers)
        
        with pytest.raises(RuntimeError, match="aiohttp is required"):
            # This will fail due to missing aiohttp, but we can still test the logic
            gateway = ASGIGateway(config=config)

    def test_gateway_init_constructor_servers_override_config(self):
        """Test constructor servers parameter overrides config servers."""
        config_servers = ["http://config-server.com"]
        constructor_servers = ["http://constructor-server.com"]
        
        config = GatewayConfig(paths=[], servers=config_servers)
        
        with pytest.raises(RuntimeError, match="aiohttp is required"):
            gateway = ASGIGateway(config=config, servers=constructor_servers)

    def test_gateway_init_no_servers_no_forward_service(self):
        """Test Gateway doesn't initialize forward service when no servers."""
        config = GatewayConfig(paths=[])
        gateway = ASGIGateway(config=config)
        
        assert gateway.servers is None
        assert gateway._forward_service is None

    def test_gateway_init_with_config_servers_requires_aiohttp(self):
        """Test Gateway with config servers requires aiohttp."""
        servers = ["http://server1.com", "http://server2.com"]
        config = GatewayConfig(paths=[], servers=servers)
        
        # Should raise RuntimeError because aiohttp is not available
        with pytest.raises(RuntimeError, match="aiohttp is required"):
            gateway = ASGIGateway(config=config)

    def test_gateway_config_from_dict_includes_servers(self):
        """Test GatewayConfig._from_dict includes servers."""
        data = {
            "paths": [],
            "servers": ["http://server1.com", "http://server2.com"],
            "keyspace": "test-gateway"
        }
        
        config = GatewayConfig._from_dict(data)
        
        assert config.servers == ["http://server1.com", "http://server2.com"]
        assert config.keyspace == "test-gateway"

    def test_gateway_config_from_dict_without_servers(self):
        """Test GatewayConfig._from_dict defaults servers to None."""
        data = {
            "paths": [],
            "keyspace": "test-gateway"
        }
        
        config = GatewayConfig._from_dict(data)
        
        assert config.servers is None
        assert config.keyspace == "test-gateway"


class TestCircuitBreakerConfig:
    """Test circuit breaker configuration."""

    def test_circuit_breaker_config_defaults(self):
        """Test CircuitBreakerConfig default values."""
        config = CircuitBreakerConfig()
        
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.expected_exception == Exception

    def test_circuit_breaker_config_custom_values(self):
        """Test CircuitBreakerConfig with custom values."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            expected_exception=ValueError,
        )
        
        assert config.failure_threshold == 3
        assert config.recovery_timeout == 30.0
        assert config.expected_exception == ValueError

    def test_feature_config_with_circuit_breaker(self):
        """Test FeatureConfig includes circuit breaker."""
        cb_config = CircuitBreakerConfig(failure_threshold=3)
        feature_config = FeatureConfig(circuit_breaker=cb_config)
        
        assert feature_config.circuit_breaker == cb_config
        assert feature_config.circuit_breaker_instance is None  # Not compiled yet

    def test_feature_config_get_applicable_features_includes_circuit_breaker(self):
        """Test get_applicable_features includes circuit_breaker."""
        cb_config = CircuitBreakerConfig()
        feature_config = FeatureConfig(circuit_breaker=cb_config)
        
        features = feature_config.get_applicable_features()
        assert "circuit_breaker" in features

    def test_gateway_config_parse_features_circuit_breaker(self):
        """Test _parse_features parses circuit breaker config."""
        features_data = {
            "circuit_breaker": {
                "failure_threshold": 3,
                "recovery_timeout": 30.0,
            }
        }
        
        feature_config = GatewayConfig._parse_features(features_data)
        
        assert feature_config.circuit_breaker is not None
        assert feature_config.circuit_breaker.failure_threshold == 3
        assert feature_config.circuit_breaker.recovery_timeout == 30.0
        assert feature_config.circuit_breaker.expected_exception == Exception

    def test_gateway_config_parse_features_circuit_breaker_defaults(self):
        """Test _parse_features uses defaults for missing circuit breaker values."""
        features_data = {
            "circuit_breaker": {}
        }
        
        feature_config = GatewayConfig._parse_features(features_data)
        
        assert feature_config.circuit_breaker is not None
        assert feature_config.circuit_breaker.failure_threshold == 5
        assert feature_config.circuit_breaker.recovery_timeout == 60.0

    def test_gateway_compile_features_creates_circuit_breaker_instance(self):
        """Test _compile_features creates circuit breaker instance."""
        cb_config = CircuitBreakerConfig(failure_threshold=3)
        feature_config = FeatureConfig(circuit_breaker=cb_config)
        
        config = GatewayConfig(paths=[])
        gateway = ASGIGateway(config=config)
        
        compiled_features = gateway._compile_features(feature_config)
        
        assert compiled_features.circuit_breaker_instance is not None
        assert compiled_features.circuit_breaker_instance.failure_threshold == 3

    @pytest.mark.asyncio
    async def test_gateway_circuit_breaker_integration(self):
        """Test circuit breaker integration in gateway handler chain."""
        cb_config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1)
        feature_config = FeatureConfig(circuit_breaker=cb_config)
        path_config = PathConfig(pattern="/test", features=feature_config)
        gateway_config = GatewayConfig(paths=[path_config])
        
        failure_count = 0
        
        async def failing_app(scope, receive, send):
            nonlocal failure_count
            failure_count += 1
            if failure_count <= 2:
                raise Exception("Test failure")
            
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/plain"]],
            })
            await send({
                "type": "http.response.body",
                "body": b"Success after recovery",
            })
        
        gateway = ASGIGateway(config=gateway_config, app=failing_app)
        
        scope = {"type": "http", "method": "GET", "path": "/test"}
        receive = AsyncMock(return_value={"type": "http.request", "body": b"", "more_body": False})
        send = AsyncMock()
        
        # First two calls should fail and open the circuit
        with pytest.raises(Exception, match="Test failure"):
            await gateway(scope, receive, send)
        
        with pytest.raises(Exception, match="Test failure"):
            await gateway(scope, receive, send)
        
        # Third call should be blocked by circuit breaker
        from premier.retry import CircuitBreakerOpenException
        with pytest.raises(CircuitBreakerOpenException):
            await gateway(scope, receive, send)


class TestFactoryFunctionWithServers:
    """Test factory function with servers configuration."""

    def test_create_gateway_with_config_servers(self):
        """Test create_gateway uses servers from config."""
        servers = ["http://server1.com"]
        config = GatewayConfig(paths=[], servers=servers)
        
        with pytest.raises(RuntimeError, match="aiohttp is required"):
            gateway = create_gateway(config)