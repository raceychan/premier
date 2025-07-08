import base64
import pytest
from unittest.mock import AsyncMock, patch

from premier.asgi import ASGIGateway, GatewayConfig, AuthConfig, PathConfig, FeatureConfig
from premier.features.auth.errors import InvalidCredentialsError, InvalidTokenError


class TestGatewayAuthIntegration:
    """Test auth integration with ASGI Gateway."""
    
    @pytest.fixture
    def mock_app(self):
        """Create a mock ASGI app."""
        async def app(scope, receive, send):
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"application/json"]],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"message": "success"}',
            })
        return app
    
    @pytest.fixture
    def basic_auth_config(self):
        """Create basic auth config."""
        return AuthConfig(type="basic", username="testuser", password="testpass")
    
    @pytest.fixture
    def jwt_auth_config(self):
        """Create JWT auth config."""
        return AuthConfig(type="jwt", secret="mysecret", algorithm="HS256")
    
    @pytest.mark.asyncio
    async def test_basic_auth_success(self, mock_app, basic_auth_config):
        """Test successful basic authentication."""
        # Create gateway with basic auth
        feature_config = FeatureConfig(auth=basic_auth_config)
        path_config = PathConfig(pattern="/api/.*", features=feature_config)
        gateway_config = GatewayConfig(paths=[path_config])
        gateway = ASGIGateway(config=gateway_config, app=mock_app)
        
        # Create valid basic auth header
        credentials = base64.b64encode(b"testuser:testpass").decode("utf-8")
        headers = [[b"authorization", f"Basic {credentials}".encode()]]
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/users",
            "headers": headers,
        }
        receive = AsyncMock()
        send = AsyncMock()
        
        # Call gateway
        await gateway(scope, receive, send)
        
        # Verify user info was added to scope
        assert "user" in scope
        assert scope["user"]["username"] == "testuser"
        assert scope["user"]["auth_type"] == "basic"
        
        # Verify successful response
        assert send.call_count == 2
        start_call = send.call_args_list[0][0][0]
        assert start_call["type"] == "http.response.start"
        assert start_call["status"] == 200
    
    @pytest.mark.asyncio
    async def test_basic_auth_failure(self, mock_app, basic_auth_config):
        """Test failed basic authentication."""
        # Create gateway with basic auth
        feature_config = FeatureConfig(auth=basic_auth_config)
        path_config = PathConfig(pattern="/api/.*", features=feature_config)
        gateway_config = GatewayConfig(paths=[path_config])
        gateway = ASGIGateway(config=gateway_config, app=mock_app)
        
        # Create invalid basic auth header
        credentials = base64.b64encode(b"wronguser:wrongpass").decode("utf-8")
        headers = [[b"authorization", f"Basic {credentials}".encode()]]
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/users",
            "headers": headers,
        }
        receive = AsyncMock()
        send = AsyncMock()
        
        # Call gateway
        await gateway(scope, receive, send)
        
        # Verify unauthorized response
        assert send.call_count == 2
        start_call = send.call_args_list[0][0][0]
        assert start_call["type"] == "http.response.start"
        assert start_call["status"] == 401
        
        body_call = send.call_args_list[1][0][0]
        assert b"Invalid username or password" in body_call["body"]
    
    @pytest.mark.asyncio
    async def test_missing_auth_header(self, mock_app, basic_auth_config):
        """Test missing authorization header."""
        # Create gateway with basic auth
        feature_config = FeatureConfig(auth=basic_auth_config)
        path_config = PathConfig(pattern="/api/.*", features=feature_config)
        gateway_config = GatewayConfig(paths=[path_config])
        gateway = ASGIGateway(config=gateway_config, app=mock_app)
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/users",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()
        
        # Call gateway
        await gateway(scope, receive, send)
        
        # Verify unauthorized response
        assert send.call_count == 2
        start_call = send.call_args_list[0][0][0]
        assert start_call["type"] == "http.response.start"
        assert start_call["status"] == 401
        
        body_call = send.call_args_list[1][0][0]
        assert b"Authorization header is required" in body_call["body"]
    
    @pytest.mark.asyncio
    async def test_jwt_auth_success(self, mock_app, jwt_auth_config):
        """Test successful JWT authentication."""
        # Create gateway with JWT auth
        feature_config = FeatureConfig(auth=jwt_auth_config)
        path_config = PathConfig(pattern="/api/.*", features=feature_config)
        gateway_config = GatewayConfig(paths=[path_config])
        gateway = ASGIGateway(config=gateway_config, app=mock_app)
        
        # Mock JWT module
        mock_jwt = AsyncMock()
        mock_jwt.decode.return_value = {"sub": "user123", "exp": 1234567890}
        
        headers = [[b"authorization", b"Bearer valid_token"]]
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/users",
            "headers": headers,
        }
        receive = AsyncMock()
        send = AsyncMock()
        
        # Patch JWT module
        with patch('premier.features.auth.auth.jwt', mock_jwt):
            # Call gateway
            await gateway(scope, receive, send)
        
        # Verify user info was added to scope
        assert "user" in scope
        assert scope["user"]["sub"] == "user123"
        assert scope["user"]["auth_type"] == "jwt"
        
        # Verify successful response
        assert send.call_count == 2
        start_call = send.call_args_list[0][0][0]
        assert start_call["type"] == "http.response.start"
        assert start_call["status"] == 200
    
    @pytest.mark.asyncio
    async def test_jwt_auth_failure(self, mock_app, jwt_auth_config):
        """Test failed JWT authentication."""
        # Create gateway with JWT auth
        feature_config = FeatureConfig(auth=jwt_auth_config)
        path_config = PathConfig(pattern="/api/.*", features=feature_config)
        gateway_config = GatewayConfig(paths=[path_config])
        gateway = ASGIGateway(config=gateway_config, app=mock_app)
        
        # Mock JWT module with decode error
        mock_jwt = AsyncMock()
        mock_jwt.DecodeError = Exception
        mock_jwt.decode.side_effect = mock_jwt.DecodeError("Invalid token")
        
        headers = [[b"authorization", b"Bearer invalid_token"]]
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/users",
            "headers": headers,
        }
        receive = AsyncMock()
        send = AsyncMock()
        
        # Patch JWT module
        with patch('premier.features.auth.auth.jwt', mock_jwt):
            # Call gateway
            await gateway(scope, receive, send)
        
        # Verify unauthorized response
        assert send.call_count == 2
        start_call = send.call_args_list[0][0][0]
        assert start_call["type"] == "http.response.start"
        assert start_call["status"] == 401
        
        body_call = send.call_args_list[1][0][0]
        assert b"JWT decode error" in body_call["body"]
    
    @pytest.mark.asyncio
    async def test_no_auth_required(self, mock_app):
        """Test path without auth requirement."""
        # Create gateway without auth
        feature_config = FeatureConfig()  # No auth config
        path_config = PathConfig(pattern="/public/.*", features=feature_config)
        gateway_config = GatewayConfig(paths=[path_config])
        gateway = ASGIGateway(config=gateway_config, app=mock_app)
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/public/info",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()
        
        # Call gateway
        await gateway(scope, receive, send)
        
        # Verify no auth was required and request succeeded
        assert send.call_count == 2
        start_call = send.call_args_list[0][0][0]
        assert start_call["type"] == "http.response.start"
        assert start_call["status"] == 200
        
        # User info should not be in scope
        assert "user" not in scope
    
    @pytest.mark.asyncio
    async def test_auth_middleware_order(self, mock_app, basic_auth_config):
        """Test auth middleware runs before other middleware."""
        # Create gateway with auth and other features
        feature_config = FeatureConfig(
            auth=basic_auth_config,
            timeout={"seconds": 5}  # Add timeout to test order
        )
        path_config = PathConfig(pattern="/api/.*", features=feature_config)
        gateway_config = GatewayConfig(paths=[path_config])
        gateway = ASGIGateway(config=gateway_config, app=mock_app)
        
        # No auth header - should fail at auth level before timeout
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/users",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()
        
        # Call gateway
        await gateway(scope, receive, send)
        
        # Should get 401 (auth failure), not 504 (timeout)
        assert send.call_count == 2
        start_call = send.call_args_list[0][0][0]
        assert start_call["type"] == "http.response.start"
        assert start_call["status"] == 401


class TestGatewayAuthConfigParsing:
    """Test auth config parsing in gateway."""
    
    def test_parse_basic_auth_config(self):
        """Test parsing basic auth config from dictionary."""
        features_data = {
            "auth": {
                "type": "basic",
                "username": "testuser",
                "password": "testpass"
            }
        }
        
        feature_config = GatewayConfig._parse_features(features_data)
        
        assert feature_config.auth is not None
        assert feature_config.auth.type == "basic"
        assert feature_config.auth.username == "testuser"
        assert feature_config.auth.password == "testpass"
    
    def test_parse_jwt_auth_config(self):
        """Test parsing JWT auth config from dictionary."""
        features_data = {
            "auth": {
                "type": "jwt",
                "secret": "mysecret",
                "algorithm": "HS256",
                "audience": "myapp",
                "issuer": "myissuer",
                "verify_signature": True,
                "verify_exp": False
            }
        }
        
        feature_config = GatewayConfig._parse_features(features_data)
        
        assert feature_config.auth is not None
        assert feature_config.auth.type == "jwt"
        assert feature_config.auth.secret == "mysecret"
        assert feature_config.auth.algorithm == "HS256"
        assert feature_config.auth.audience == "myapp"
        assert feature_config.auth.issuer == "myissuer"
        assert feature_config.auth.verify_signature is True
        assert feature_config.auth.verify_exp is False
    
    def test_parse_jwt_auth_config_defaults(self):
        """Test parsing JWT auth config with defaults."""
        features_data = {
            "auth": {
                "type": "jwt",
                "secret": "mysecret"
            }
        }
        
        feature_config = GatewayConfig._parse_features(features_data)
        
        assert feature_config.auth is not None
        assert feature_config.auth.type == "jwt"
        assert feature_config.auth.secret == "mysecret"
        assert feature_config.auth.algorithm == "HS256"
        assert feature_config.auth.verify_signature is True
        assert feature_config.auth.verify_exp is True
    
    def test_parse_auth_config_missing_type(self):
        """Test parsing auth config without type raises error."""
        features_data = {
            "auth": {
                "username": "testuser",
                "password": "testpass"
            }
        }
        
        with pytest.raises(ValueError, match="Auth configuration requires 'type' field"):
            GatewayConfig._parse_features(features_data)
    
    def test_parse_auth_config_invalid_format(self):
        """Test parsing auth config with invalid format raises error."""
        features_data = {
            "auth": True  # Should be dict
        }
        
        with pytest.raises(ValueError, match="Auth configuration requires a dictionary"):
            GatewayConfig._parse_features(features_data)
    
    def test_parse_no_auth_config(self):
        """Test parsing features without auth config."""
        features_data = {
            "cache": {"expire_s": 300}
        }
        
        feature_config = GatewayConfig._parse_features(features_data)
        
        assert feature_config.auth is None