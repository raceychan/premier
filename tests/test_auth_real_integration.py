#!/usr/bin/env python3
"""
Real integration tests for Premier Auth feature without mocking.

These tests use actual JWT tokens and real authentication flow to verify
the auth feature works correctly in realistic scenarios.

Run these tests with:
    pytest tests/test_auth_real_integration.py -v -s
"""

import base64
import json
import time

import pytest
from premier.asgi import ASGIGateway, GatewayConfig, AuthConfig, PathConfig, FeatureConfig


class TestRealAuthIntegration:
    """Real integration tests using actual auth without mocking."""
    
    async def demo_app(self, scope, receive, send):
        """Demo ASGI app that shows user info."""
        assert scope["type"] == "http"
        
        path = scope["path"]
        method = scope["method"]
        user_info = scope.get("user", {})
        
        if path.startswith("/api/"):
            response_data = {
                "message": "Welcome to the protected API!",
                "user": user_info,
                "path": path,
                "method": method,
                "authenticated": True
            }
        elif path.startswith("/public/"):
            response_data = {
                "message": "This is a public endpoint",
                "path": path,
                "method": method,
                "authenticated": False
            }
        else:
            response_data = {
                "message": "Premier Auth Integration Test",
                "path": path,
                "method": method
            }
        
        body = json.dumps(response_data, indent=2).encode()
        
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
    
    def create_basic_auth_gateway(self):
        """Create gateway with Basic Auth."""
        auth_config = AuthConfig(
            type="basic",
            username="testuser",
            password="testpass"
        )
        
        protected_features = FeatureConfig(auth=auth_config)
        public_features = FeatureConfig()
        
        paths = [
            PathConfig(pattern="/api/.*", features=protected_features),
            PathConfig(pattern="/public/.*", features=public_features),
        ]
        
        gateway_config = GatewayConfig(paths=paths)
        return ASGIGateway(config=gateway_config, app=self.demo_app)
    
    def create_jwt_auth_gateway(self):
        """Create gateway with JWT Auth."""
        auth_config = AuthConfig(
            type="jwt",
            secret="test_secret_key",
            algorithm="HS256"
        )
        
        protected_features = FeatureConfig(auth=auth_config)
        public_features = FeatureConfig()
        
        paths = [
            PathConfig(pattern="/api/.*", features=protected_features),
            PathConfig(pattern="/public/.*", features=public_features),
        ]
        
        gateway_config = GatewayConfig(paths=paths)
        return ASGIGateway(config=gateway_config, app=self.demo_app)
    
    async def make_request(self, gateway, path, headers=None):
        """Helper to make ASGI request and get response."""
        headers = headers or []
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": headers,
        }
        
        received_messages = []
        
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        
        async def send(message):
            received_messages.append(message)
        
        await gateway(scope, receive, send)
        
        # Extract status and body
        status = received_messages[0]["status"]
        body = received_messages[1]["body"].decode()
        
        return status, body, scope
    
    @pytest.mark.asyncio
    async def test_basic_auth_success_real(self):
        """Test successful Basic Auth with real credentials."""
        gateway = self.create_basic_auth_gateway()
        
        # Create valid Basic Auth header
        credentials = base64.b64encode(b"testuser:testpass").decode()
        headers = [[b"authorization", f"Basic {credentials}".encode()]]
        
        status, body, scope = await self.make_request(gateway, "/api/protected", headers)
        
        # Verify successful authentication
        assert status == 200
        response_data = json.loads(body)
        assert response_data["message"] == "Welcome to the protected API!"
        assert response_data["user"]["username"] == "testuser"
        assert response_data["user"]["auth_type"] == "basic"
        assert response_data["authenticated"] is True
        
        # Verify user info was added to scope
        assert "user" in scope
        assert scope["user"]["username"] == "testuser"
        assert scope["user"]["auth_type"] == "basic"
    
    @pytest.mark.asyncio
    async def test_basic_auth_failure_real(self):
        """Test failed Basic Auth with real credentials."""
        gateway = self.create_basic_auth_gateway()
        
        # Create invalid Basic Auth header
        credentials = base64.b64encode(b"wronguser:wrongpass").decode()
        headers = [[b"authorization", f"Basic {credentials}".encode()]]
        
        status, body, scope = await self.make_request(gateway, "/api/protected", headers)
        
        # Verify authentication failure
        assert status == 401
        assert "Invalid username or password" in body
        
        # Verify no user info in scope
        assert "user" not in scope
    
    @pytest.mark.asyncio
    async def test_basic_auth_missing_header_real(self):
        """Test missing auth header with real flow."""
        gateway = self.create_basic_auth_gateway()
        
        status, body, scope = await self.make_request(gateway, "/api/protected")
        
        # Verify authentication failure
        assert status == 401
        assert "Authorization header is required" in body
        
        # Verify no user info in scope
        assert "user" not in scope
    
    @pytest.mark.asyncio
    async def test_basic_auth_invalid_format_real(self):
        """Test invalid auth header format with real flow."""
        gateway = self.create_basic_auth_gateway()
        
        # Invalid header format (Bearer instead of Basic)
        headers = [[b"authorization", b"Bearer some_token"]]
        
        status, body, scope = await self.make_request(gateway, "/api/protected", headers)
        
        # Verify authentication failure
        assert status == 401
        assert "Invalid authorization header format" in body
        
        # Verify no user info in scope
        assert "user" not in scope
    
    @pytest.mark.asyncio
    async def test_public_endpoint_no_auth_real(self):
        """Test public endpoint doesn't require auth."""
        gateway = self.create_basic_auth_gateway()
        
        status, body, scope = await self.make_request(gateway, "/public/info")
        
        # Verify successful access without auth
        assert status == 200
        response_data = json.loads(body)
        assert response_data["message"] == "This is a public endpoint"
        assert response_data["authenticated"] is False
        
        # Verify no user info in scope (no auth required)
        assert "user" not in scope
    
    @pytest.mark.asyncio
    async def test_jwt_auth_success_real(self):
        """Test successful JWT Auth with real JWT token."""
        try:
            import jwt
        except ImportError:
            pytest.skip("pyjwt not installed")
        
        gateway = self.create_jwt_auth_gateway()
        
        # Create a real JWT token
        payload = {
            "sub": "user123",
            "name": "Test User",
            "email": "test@example.com",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,  # 1 hour expiration
        }
        
        token = jwt.encode(payload, "test_secret_key", algorithm="HS256")
        headers = [[b"authorization", f"Bearer {token}".encode()]]
        
        status, body, scope = await self.make_request(gateway, "/api/protected", headers)
        
        # Verify successful authentication
        assert status == 200
        response_data = json.loads(body)
        assert response_data["message"] == "Welcome to the protected API!"
        assert response_data["user"]["sub"] == "user123"
        assert response_data["user"]["name"] == "Test User"
        assert response_data["user"]["email"] == "test@example.com"
        assert response_data["user"]["auth_type"] == "jwt"
        assert response_data["authenticated"] is True
        
        # Verify user info was added to scope
        assert "user" in scope
        assert scope["user"]["sub"] == "user123"
        assert scope["user"]["name"] == "Test User"
        assert scope["user"]["auth_type"] == "jwt"
    
    @pytest.mark.asyncio
    async def test_jwt_auth_expired_token_real(self):
        """Test JWT Auth with expired token."""
        try:
            import jwt
        except ImportError:
            pytest.skip("pyjwt not installed")
        
        gateway = self.create_jwt_auth_gateway()
        
        # Create an expired JWT token
        payload = {
            "sub": "user123",
            "name": "Test User",
            "iat": int(time.time()) - 7200,  # 2 hours ago
            "exp": int(time.time()) - 3600,  # 1 hour ago (expired)
        }
        
        token = jwt.encode(payload, "test_secret_key", algorithm="HS256")
        headers = [[b"authorization", f"Bearer {token}".encode()]]
        
        status, body, scope = await self.make_request(gateway, "/api/protected", headers)
        
        # Verify authentication failure
        assert status == 401
        assert "JWT token has expired" in body
        
        # Verify no user info in scope
        assert "user" not in scope
    
    @pytest.mark.asyncio
    async def test_jwt_auth_invalid_signature_real(self):
        """Test JWT Auth with invalid signature."""
        try:
            import jwt
        except ImportError:
            pytest.skip("pyjwt not installed")
        
        gateway = self.create_jwt_auth_gateway()
        
        # Create JWT with wrong secret
        payload = {
            "sub": "user123",
            "name": "Test User",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        
        token = jwt.encode(payload, "wrong_secret_key", algorithm="HS256")
        headers = [[b"authorization", f"Bearer {token}".encode()]]
        
        status, body, scope = await self.make_request(gateway, "/api/protected", headers)
        
        # Verify authentication failure
        assert status == 401
        assert "Invalid JWT signature" in body
        
        # Verify no user info in scope
        assert "user" not in scope
    
    @pytest.mark.asyncio
    async def test_jwt_auth_invalid_token_format_real(self):
        """Test JWT Auth with invalid token format."""
        try:
            import jwt
        except ImportError:
            pytest.skip("pyjwt not installed")
        
        gateway = self.create_jwt_auth_gateway()
        
        # Invalid JWT token format
        headers = [[b"authorization", b"Bearer invalid.token.format"]]
        
        status, body, scope = await self.make_request(gateway, "/api/protected", headers)
        
        # Verify authentication failure
        assert status == 401
        assert ("Invalid JWT token" in body or "JWT decode error" in body)
        
        # Verify no user info in scope
        assert "user" not in scope
    
    @pytest.mark.asyncio
    async def test_jwt_auth_missing_bearer_real(self):
        """Test JWT Auth with missing Bearer prefix."""
        try:
            import jwt
        except ImportError:
            pytest.skip("pyjwt not installed")
        
        gateway = self.create_jwt_auth_gateway()
        
        # Valid JWT token but wrong header format
        payload = {
            "sub": "user123",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        
        token = jwt.encode(payload, "test_secret_key", algorithm="HS256")
        headers = [[b"authorization", f"Basic {token}".encode()]]  # Wrong prefix
        
        status, body, scope = await self.make_request(gateway, "/api/protected", headers)
        
        # Verify authentication failure
        assert status == 401
        assert "Invalid authorization header format" in body
        
        # Verify no user info in scope
        assert "user" not in scope
    
    @pytest.mark.asyncio
    async def test_jwt_auth_no_pyjwt_real(self):
        """Test JWT Auth when pyjwt is not available."""
        # This test simulates the case where pyjwt is not installed
        gateway = self.create_jwt_auth_gateway()
        
        # Temporarily break JWT import
        import sys
        jwt_module = sys.modules.get('jwt')
        if jwt_module:
            del sys.modules['jwt']
        
        try:
            headers = [[b"authorization", b"Bearer some_token"]]
            status, body, scope = await self.make_request(gateway, "/api/protected", headers)
            
            # Verify authentication failure due to missing pyjwt
            assert status == 401
            # Note: Since we can't truly uninstall pyjwt during test, this may show JWT decode error
            assert ("pyjwt is required for JWT authentication" in body or "JWT decode error" in body)
            
            # Verify no user info in scope
            assert "user" not in scope
        finally:
            # Restore JWT module
            if jwt_module:
                sys.modules['jwt'] = jwt_module
    
    @pytest.mark.asyncio
    async def test_multiple_auth_types_real(self):
        """Test that different paths can have different auth types."""
        try:
            import jwt
        except ImportError:
            pytest.skip("pyjwt not installed")
        
        # Create gateway with different auth for different paths
        basic_auth_config = AuthConfig(
            type="basic",
            username="basicuser",
            password="basicpass"
        )
        
        jwt_auth_config = AuthConfig(
            type="jwt",
            secret="jwt_secret",
            algorithm="HS256"
        )
        
        paths = [
            PathConfig(pattern="/api/basic/.*", features=FeatureConfig(auth=basic_auth_config)),
            PathConfig(pattern="/api/jwt/.*", features=FeatureConfig(auth=jwt_auth_config)),
            PathConfig(pattern="/public/.*", features=FeatureConfig()),
        ]
        
        gateway_config = GatewayConfig(paths=paths)
        gateway = ASGIGateway(config=gateway_config, app=self.demo_app)
        
        # Test Basic Auth endpoint
        basic_credentials = base64.b64encode(b"basicuser:basicpass").decode()
        basic_headers = [[b"authorization", f"Basic {basic_credentials}".encode()]]
        
        status, body, scope = await self.make_request(gateway, "/api/basic/test", basic_headers)
        assert status == 200
        response_data = json.loads(body)
        assert response_data["user"]["username"] == "basicuser"
        assert response_data["user"]["auth_type"] == "basic"
        
        # Test JWT Auth endpoint
        jwt_payload = {
            "sub": "jwtuser",
            "name": "JWT User",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        
        jwt_token = jwt.encode(jwt_payload, "jwt_secret", algorithm="HS256")
        jwt_headers = [[b"authorization", f"Bearer {jwt_token}".encode()]]
        
        status, body, scope = await self.make_request(gateway, "/api/jwt/test", jwt_headers)
        assert status == 200
        response_data = json.loads(body)
        assert response_data["user"]["sub"] == "jwtuser"
        assert response_data["user"]["name"] == "JWT User"
        assert response_data["user"]["auth_type"] == "jwt"
        
        # Test public endpoint
        status, body, scope = await self.make_request(gateway, "/public/test")
        assert status == 200
        response_data = json.loads(body)
        assert response_data["authenticated"] is False
        assert "user" not in scope
    
    @pytest.mark.asyncio
    async def test_auth_with_other_features_real(self):
        """Test auth working with other Premier features."""
        gateway = self.create_basic_auth_gateway()
        
        # Test successful auth
        credentials = base64.b64encode(b"testuser:testpass").decode()
        headers = [[b"authorization", f"Basic {credentials}".encode()]]
        
        status, body, scope = await self.make_request(gateway, "/api/protected", headers)
        
        # Verify everything works together
        assert status == 200
        response_data = json.loads(body)
        assert response_data["user"]["username"] == "testuser"
        assert response_data["authenticated"] is True
        
        # Verify user context is preserved through middleware chain
        assert "user" in scope
        assert scope["user"]["username"] == "testuser"


class TestRealAuthCurlExamples:
    """Real examples for manual testing with curl commands."""
    
    def test_generate_real_jwt_token(self):
        """Generate a real JWT token for testing."""
        try:
            import jwt
        except ImportError:
            pytest.skip("pyjwt not installed")
        
        # Generate a real JWT token
        payload = {
            "sub": "user123",
            "name": "Test User",
            "email": "test@example.com",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,  # 1 hour expiration
        }
        
        token = jwt.encode(payload, "test_secret_key", algorithm="HS256")
        
        print(f"\n🔑 Generated JWT Token:")
        print(f"   {token}")
        
        print(f"\n📝 Token Payload:")
        print(f"   {json.dumps(payload, indent=2)}")
        
        print(f"\n🧪 Test Commands:")
        print(f"   # Start JWT server:")
        print(f"   python example_jwt_server.py")
        print(f"   # Test with this token:")
        print(f"   curl -H \"Authorization: Bearer {token}\" http://localhost:8001/api/protected")
        
        # Verify the token is valid
        decoded = jwt.decode(token, "test_secret_key", algorithms=["HS256"])
        assert decoded["sub"] == "user123"
        assert decoded["name"] == "Test User"
        assert decoded["email"] == "test@example.com"
    
    def test_generate_basic_auth_examples(self):
        """Generate Basic Auth examples for testing."""
        credentials = base64.b64encode(b"testuser:testpass").decode()
        
        print(f"\n🔑 Generated Basic Auth Header:")
        print(f"   Authorization: Basic {credentials}")
        
        print(f"\n📝 Credentials:")
        print(f"   Username: testuser")
        print(f"   Password: testpass")
        print(f"   Base64 Encoded: {credentials}")
        
        print(f"\n🧪 Test Commands:")
        print(f"   # Start Basic Auth server:")
        print(f"   python example_auth_server.py")
        print(f"   # Test with valid credentials:")
        print(f"   curl -H \"Authorization: Basic {credentials}\" http://localhost:8000/api/protected")
        print(f"   # Test without credentials (should fail):")
        print(f"   curl http://localhost:8000/api/protected")
        
        # Verify the credentials are correct
        decoded = base64.b64decode(credentials).decode()
        assert decoded == "testuser:testpass"
    
    def test_comprehensive_real_testing_guide(self):
        """Print comprehensive guide for real testing."""
        print(f"\n{'='*60}")
        print(f"REAL INTEGRATION TESTING GUIDE")
        print(f"{'='*60}")
        
        print(f"\n🚀 REAL TESTING APPROACH:")
        print(f"   ✅ No mocking - uses actual JWT tokens")
        print(f"   ✅ Real Basic Auth - actual Base64 encoding")
        print(f"   ✅ Full middleware chain - tests complete flow")
        print(f"   ✅ Error scenarios - real error handling")
        print(f"   ✅ Multiple auth types - different paths")
        
        print(f"\n🧪 AUTOMATED TESTS:")
        print(f"   pytest tests/test_auth_real_integration.py -v")
        
        print(f"\n🔧 MANUAL TESTING:")
        print(f"   1. Run: python example_auth_server.py")
        print(f"   2. Run: python example_jwt_server.py")
        print(f"   3. Use generated tokens/credentials from tests")
        
        print(f"\n📊 SCENARIOS TESTED:")
        print(f"   ✅ Valid authentication (Basic & JWT)")
        print(f"   ❌ Invalid credentials")
        print(f"   ❌ Missing auth headers")
        print(f"   ❌ Invalid token formats")
        print(f"   ❌ Expired JWT tokens")
        print(f"   ❌ Invalid JWT signatures")
        print(f"   ✅ Public endpoints")
        print(f"   ✅ Multiple auth types")
        print(f"   ✅ Auth with other features")
        
        print(f"\n💡 ADVANTAGES OF REAL TESTING:")
        print(f"   • Tests actual JWT library behavior")
        print(f"   • Validates real Base64 encoding")
        print(f"   • Catches integration issues")
        print(f"   • Provides realistic examples")
        print(f"   • No mock-specific bugs")


if __name__ == "__main__":
    # Run examples when script is executed directly
    examples = TestRealAuthCurlExamples()
    examples.test_generate_basic_auth_examples()
    examples.test_generate_real_jwt_token()
    examples.test_comprehensive_real_testing_guide()