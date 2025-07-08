import base64
import pytest
from unittest.mock import AsyncMock, patch

from premier.features.auth import AuthConfig, BasicAuth, JWTAuth, create_auth_handler
from premier.features.auth.errors import (
    AuthError,
    InvalidCredentialsError,
    InvalidTokenError,
    MissingAuthHeaderError,
    InvalidAuthHeaderError,
)


class TestAuthConfig:
    """Test AuthConfig dataclass."""
    
    def test_basic_auth_config(self):
        """Test basic auth configuration."""
        config = AuthConfig(
            type="basic",
            username="testuser",
            password="testpass"
        )
        
        assert config.type == "basic"
        assert config.username == "testuser"
        assert config.password == "testpass"
        assert config.secret is None
        assert config.algorithm == "HS256"
    
    def test_jwt_auth_config(self):
        """Test JWT auth configuration."""
        config = AuthConfig(
            type="jwt",
            secret="mysecret",
            algorithm="HS256",
            audience="myapp",
            issuer="myissuer"
        )
        
        assert config.type == "jwt"
        assert config.secret == "mysecret"
        assert config.algorithm == "HS256"
        assert config.audience == "myapp"
        assert config.issuer == "myissuer"
        assert config.username is None
    
    def test_jwt_auth_config_defaults(self):
        """Test JWT auth configuration with defaults."""
        config = AuthConfig(
            type="jwt",
            secret="mysecret"
        )
        
        assert config.type == "jwt"
        assert config.secret == "mysecret"
        assert config.algorithm == "HS256"
        assert config.verify_signature is True
        assert config.verify_exp is True
        assert config.verify_nbf is True
        assert config.verify_iat is True
        assert config.verify_aud is True
        assert config.verify_iss is True


class TestBasicAuth:
    """Test BasicAuth handler."""
    
    @pytest.fixture
    def basic_auth(self):
        """Create BasicAuth handler."""
        config = AuthConfig(type="basic", username="testuser", password="testpass")
        return BasicAuth(config)
    
    @pytest.mark.asyncio
    async def test_valid_basic_auth(self, basic_auth):
        """Test valid basic authentication."""
        # Create valid basic auth header
        credentials = base64.b64encode(b"testuser:testpass").decode("utf-8")
        headers = {"authorization": f"Basic {credentials}"}
        
        result = await basic_auth.authenticate(headers)
        
        assert result["username"] == "testuser"
        assert result["auth_type"] == "basic"
    
    @pytest.mark.asyncio
    async def test_missing_auth_header(self, basic_auth):
        """Test missing authorization header."""
        headers = {}
        
        with pytest.raises(MissingAuthHeaderError):
            await basic_auth.authenticate(headers)
    
    @pytest.mark.asyncio
    async def test_invalid_auth_header_format(self, basic_auth):
        """Test invalid authorization header format."""
        headers = {"authorization": "Bearer token123"}
        
        with pytest.raises(InvalidAuthHeaderError):
            await basic_auth.authenticate(headers)
    
    @pytest.mark.asyncio
    async def test_invalid_base64_encoding(self, basic_auth):
        """Test invalid base64 encoding."""
        headers = {"authorization": "Basic invalid_base64!!!"}
        
        with pytest.raises(InvalidAuthHeaderError):
            await basic_auth.authenticate(headers)
    
    @pytest.mark.asyncio
    async def test_invalid_credentials_format(self, basic_auth):
        """Test invalid credentials format (missing colon)."""
        credentials = base64.b64encode(b"testuser_no_colon").decode("utf-8")
        headers = {"authorization": f"Basic {credentials}"}
        
        with pytest.raises(InvalidAuthHeaderError):
            await basic_auth.authenticate(headers)
    
    @pytest.mark.asyncio
    async def test_invalid_username(self, basic_auth):
        """Test invalid username."""
        credentials = base64.b64encode(b"wronguser:testpass").decode("utf-8")
        headers = {"authorization": f"Basic {credentials}"}
        
        with pytest.raises(InvalidCredentialsError):
            await basic_auth.authenticate(headers)
    
    @pytest.mark.asyncio
    async def test_invalid_password(self, basic_auth):
        """Test invalid password."""
        credentials = base64.b64encode(b"testuser:wrongpass").decode("utf-8")
        headers = {"authorization": f"Basic {credentials}"}
        
        with pytest.raises(InvalidCredentialsError):
            await basic_auth.authenticate(headers)


class TestJWTAuth:
    """Test JWTAuth handler."""
    
    @pytest.fixture
    def jwt_auth(self):
        """Create JWTAuth handler."""
        config = AuthConfig(type="jwt", secret="mysecret", algorithm="HS256")
        return JWTAuth(config)
    
    @pytest.mark.asyncio
    async def test_jwt_import_error(self, jwt_auth):
        """Test JWT import error when pyjwt is not installed."""
        with patch.dict('sys.modules', {'jwt': None}):
            with patch('builtins.__import__', side_effect=ImportError()):
                with pytest.raises(ImportError, match="pyjwt is required"):
                    await jwt_auth.authenticate({"authorization": "Bearer token123"})
    
    @pytest.mark.asyncio
    async def test_missing_auth_header(self, jwt_auth):
        """Test missing authorization header."""
        # Mock JWT module to avoid import error
        from unittest.mock import Mock
        mock_jwt = Mock()
        
        with patch.object(jwt_auth, '_get_jwt_module', return_value=mock_jwt):
            headers = {}
            
            with pytest.raises(MissingAuthHeaderError):
                await jwt_auth.authenticate(headers)
    
    @pytest.mark.asyncio
    async def test_invalid_auth_header_format(self, jwt_auth):
        """Test invalid authorization header format."""
        # Mock JWT module to avoid import error
        from unittest.mock import Mock
        mock_jwt = Mock()
        
        with patch.object(jwt_auth, '_get_jwt_module', return_value=mock_jwt):
            headers = {"authorization": "Basic token123"}
            
            with pytest.raises(InvalidAuthHeaderError):
                await jwt_auth.authenticate(headers)
    
    @pytest.mark.asyncio
    async def test_valid_jwt_token(self, jwt_auth):
        """Test valid JWT token."""
        # Mock JWT module
        from unittest.mock import Mock
        mock_jwt = Mock()
        mock_jwt.decode.return_value = {"sub": "user123", "exp": 1234567890}
        
        with patch.object(jwt_auth, '_get_jwt_module', return_value=mock_jwt):
            headers = {"authorization": "Bearer valid_token"}
            result = await jwt_auth.authenticate(headers)
            
            assert result["sub"] == "user123"
            assert result["exp"] == 1234567890
            assert result["auth_type"] == "jwt"
            
            # Verify JWT decode was called with correct parameters
            mock_jwt.decode.assert_called_once_with(
                "valid_token",
                "mysecret",
                algorithms=["HS256"],
                audience=None,
                issuer=None,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                }
            )
    
    @pytest.mark.asyncio
    async def test_jwt_decode_error(self, jwt_auth):
        """Test JWT decode error."""
        from unittest.mock import Mock
        
        # Create proper exception classes
        class MockDecodeError(Exception):
            pass
        
        mock_jwt = Mock()
        mock_jwt.DecodeError = MockDecodeError
        mock_jwt.InvalidTokenError = Exception
        mock_jwt.ExpiredSignatureError = Exception
        mock_jwt.InvalidAudienceError = Exception
        mock_jwt.InvalidIssuerError = Exception
        mock_jwt.InvalidSignatureError = Exception
        mock_jwt.InvalidKeyError = Exception
        mock_jwt.decode.side_effect = MockDecodeError("Invalid token")
        
        with patch.object(jwt_auth, '_get_jwt_module', return_value=mock_jwt):
            headers = {"authorization": "Bearer invalid_token"}
            
            with pytest.raises(InvalidTokenError, match="JWT decode error"):
                await jwt_auth.authenticate(headers)
    
    @pytest.mark.asyncio
    async def test_jwt_expired_token(self, jwt_auth):
        """Test JWT expired token."""
        from unittest.mock import Mock
        
        # Create proper exception classes
        class MockExpiredSignatureError(Exception):
            pass
        
        mock_jwt = Mock()
        mock_jwt.ExpiredSignatureError = MockExpiredSignatureError
        mock_jwt.InvalidTokenError = Exception
        mock_jwt.DecodeError = Exception
        mock_jwt.InvalidAudienceError = Exception
        mock_jwt.InvalidIssuerError = Exception
        mock_jwt.InvalidSignatureError = Exception
        mock_jwt.InvalidKeyError = Exception
        mock_jwt.decode.side_effect = MockExpiredSignatureError("Token expired")
        
        with patch.object(jwt_auth, '_get_jwt_module', return_value=mock_jwt):
            headers = {"authorization": "Bearer expired_token"}
            
            with pytest.raises(InvalidTokenError, match="JWT token has expired"):
                await jwt_auth.authenticate(headers)
    
    @pytest.mark.asyncio
    async def test_jwt_invalid_signature(self, jwt_auth):
        """Test JWT invalid signature."""
        from unittest.mock import Mock
        
        # Create proper exception classes
        class MockInvalidSignatureError(Exception):
            pass
        
        mock_jwt = Mock()
        mock_jwt.InvalidSignatureError = MockInvalidSignatureError
        mock_jwt.InvalidTokenError = Exception
        mock_jwt.DecodeError = Exception
        mock_jwt.ExpiredSignatureError = Exception
        mock_jwt.InvalidAudienceError = Exception
        mock_jwt.InvalidIssuerError = Exception
        mock_jwt.InvalidKeyError = Exception
        mock_jwt.decode.side_effect = MockInvalidSignatureError("Invalid signature")
        
        with patch.object(jwt_auth, '_get_jwt_module', return_value=mock_jwt):
            headers = {"authorization": "Bearer invalid_signature_token"}
            
            with pytest.raises(InvalidTokenError, match="Invalid JWT signature"):
                await jwt_auth.authenticate(headers)
    
    @pytest.mark.asyncio
    async def test_jwt_invalid_audience(self, jwt_auth):
        """Test JWT invalid audience."""
        from unittest.mock import Mock
        
        # Create proper exception classes
        class MockInvalidAudienceError(Exception):
            pass
        
        mock_jwt = Mock()
        mock_jwt.InvalidAudienceError = MockInvalidAudienceError
        mock_jwt.InvalidTokenError = Exception
        mock_jwt.DecodeError = Exception
        mock_jwt.ExpiredSignatureError = Exception
        mock_jwt.InvalidIssuerError = Exception
        mock_jwt.InvalidSignatureError = Exception
        mock_jwt.InvalidKeyError = Exception
        mock_jwt.decode.side_effect = MockInvalidAudienceError("Invalid audience")
        
        with patch.object(jwt_auth, '_get_jwt_module', return_value=mock_jwt):
            headers = {"authorization": "Bearer invalid_audience_token"}
            
            with pytest.raises(InvalidTokenError, match="Invalid JWT audience"):
                await jwt_auth.authenticate(headers)
    
    @pytest.mark.asyncio
    async def test_jwt_invalid_issuer(self, jwt_auth):
        """Test JWT invalid issuer."""
        from unittest.mock import Mock
        
        # Create proper exception classes
        class MockInvalidIssuerError(Exception):
            pass
        
        mock_jwt = Mock()
        mock_jwt.InvalidIssuerError = MockInvalidIssuerError
        mock_jwt.InvalidTokenError = Exception
        mock_jwt.DecodeError = Exception
        mock_jwt.ExpiredSignatureError = Exception
        mock_jwt.InvalidAudienceError = Exception
        mock_jwt.InvalidSignatureError = Exception
        mock_jwt.InvalidKeyError = Exception
        mock_jwt.decode.side_effect = MockInvalidIssuerError("Invalid issuer")
        
        with patch.object(jwt_auth, '_get_jwt_module', return_value=mock_jwt):
            headers = {"authorization": "Bearer invalid_issuer_token"}
            
            with pytest.raises(InvalidTokenError, match="Invalid JWT issuer"):
                await jwt_auth.authenticate(headers)


class TestCreateAuthHandler:
    """Test create_auth_handler factory function."""
    
    def test_create_basic_auth_handler(self):
        """Test creating basic auth handler."""
        config = AuthConfig(type="basic", username="user", password="pass")
        handler = create_auth_handler(config)
        
        assert isinstance(handler, BasicAuth)
        assert handler.config == config
    
    def test_create_jwt_auth_handler(self):
        """Test creating JWT auth handler."""
        config = AuthConfig(type="jwt", secret="secret")
        handler = create_auth_handler(config)
        
        assert isinstance(handler, JWTAuth)
        assert handler.config == config
    
    def test_unsupported_auth_type(self):
        """Test unsupported auth type."""
        config = AuthConfig(type="unsupported", secret="secret")
        
        with pytest.raises(ValueError, match="Unsupported auth type"):
            create_auth_handler(config)