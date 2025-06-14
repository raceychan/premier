import pytest
import tempfile
from pathlib import Path
from premier.asgi import (
    GatewayConfig, 
    PathConfig, 
    FeatureConfig,
    CacheConfig,
    RetryConfig,
    TimeoutConfig,
    RateLimitConfig,
    MonitoringConfig
)


@pytest.fixture
def sample_yaml_config():
    """Sample YAML configuration content."""
    return """
premier:
  keyspace: "test-gateway"
  
  paths:
    - pattern: "/api/*"
      features:
        timeout:
          seconds: 5.0
        rate_limit:
          quota: 100
          duration: 60
          algorithm: "fixed_window"
        retry:
          max_attempts: 3
          wait: 1.0
    
    - pattern: "/health"
      features:
        monitoring:
          log_threshold: 0.1
  
  default_features:
    timeout:
      seconds: 10.0
    cache:
      expire_s: 300
"""


@pytest.fixture
def nested_yaml_config():
    """YAML configuration with nested namespace."""
    return """
tool:
  premier:
    keyspace: "nested-gateway"
    
    paths:
      - pattern: "/api/v1/*"
        features:
          timeout:
            seconds: 2.0
          cache:
            expire_s: 600
    
    default_features:
      monitoring:
        log_threshold: 0.05
"""


class TestConfigLoading:
    """Test YAML configuration loading functionality."""
    
    def test_load_config_from_yaml_file(self, sample_yaml_config):
        """Test loading configuration from YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(sample_yaml_config)
            f.flush()
            
            try:
                config = GatewayConfig.from_file(f.name, namespace="premier")
                
                # Check basic properties
                assert config.keyspace == "test-gateway"
                assert len(config.paths) == 2
                assert config.default_features is not None
                
                # Check first path
                path1 = config.paths[0]
                assert path1.pattern == "/api/*"
                assert path1.features.timeout is not None
                assert path1.features.timeout.seconds == 5.0
                assert path1.features.rate_limit is not None
                assert path1.features.rate_limit.quota == 100
                assert path1.features.rate_limit.duration == 60
                assert path1.features.rate_limit.algorithm == "fixed_window"
                assert path1.features.retry is not None
                assert path1.features.retry.max_attempts == 3
                assert path1.features.retry.wait == 1.0
                
                # Check second path
                path2 = config.paths[1]
                assert path2.pattern == "/health"
                assert path2.features.monitoring is not None
                assert path2.features.monitoring.log_threshold == 0.1
                
                # Check default features
                assert config.default_features.timeout is not None
                assert config.default_features.timeout.seconds == 10.0
                assert config.default_features.cache is not None
                assert config.default_features.cache.expire_s == 300
                
            finally:
                Path(f.name).unlink()
    
    def test_load_config_with_nested_namespace(self, nested_yaml_config):
        """Test loading configuration with nested namespace."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(nested_yaml_config)
            f.flush()
            
            try:
                config = GatewayConfig.from_file(f.name, namespace="tool.premier")
                
                assert config.keyspace == "nested-gateway"
                assert len(config.paths) == 1
                
                path = config.paths[0]
                assert path.pattern == "/api/v1/*"
                assert path.features.timeout.seconds == 2.0
                assert path.features.cache.expire_s == 600
                
                assert config.default_features.monitoring.log_threshold == 0.05
                
            finally:
                Path(f.name).unlink()
    
    def test_file_not_found_error(self):
        """Test error when configuration file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            GatewayConfig.from_file("/nonexistent/file.yaml")
    
    def test_namespace_not_found_error(self, sample_yaml_config):
        """Test error when namespace doesn't exist in file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(sample_yaml_config)
            f.flush()
            
            try:
                with pytest.raises(KeyError, match="Namespace 'nonexistent' not found"):
                    GatewayConfig.from_file(f.name, namespace="nonexistent")
            finally:
                Path(f.name).unlink()
    
    def test_minimal_config(self):
        """Test loading minimal configuration."""
        minimal_config = """
premier:
  paths: []
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(minimal_config)
            f.flush()
            
            try:
                config = GatewayConfig.from_file(f.name, namespace="premier")
                
                assert config.keyspace == "asgi-gateway"  # Default value
                assert config.paths == []
                assert config.default_features is None
                
            finally:
                Path(f.name).unlink()
    
    def test_config_with_all_features(self):
        """Test configuration with all possible features."""
        full_config = """
premier:
  keyspace: "full-gateway"
  
  paths:
    - pattern: "/api/*"
      features:
        timeout:
          seconds: 5.0
        cache:
          expire_s: 300
          cache_key: "custom_key"
        retry:
          max_attempts: 5
          wait: 2.0
        rate_limit:
          quota: 200
          duration: 120
          algorithm: "sliding_window"
          bucket_size: 50
        monitoring:
          log_threshold: 0.05
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(full_config)
            f.flush()
            
            try:
                config = GatewayConfig.from_file(f.name, namespace="premier")
                
                path = config.paths[0]
                features = path.features
                
                # Check all features are present
                assert features.timeout is not None
                assert features.cache is not None
                assert features.retry is not None
                assert features.rate_limit is not None
                assert features.monitoring is not None
                
                # Check specific values
                assert features.timeout.seconds == 5.0
                assert features.cache.expire_s == 300
                assert features.cache.cache_key == "custom_key"
                assert features.retry.max_attempts == 5
                assert features.retry.wait == 2.0
                assert features.rate_limit.quota == 200
                assert features.rate_limit.duration == 120
                assert features.rate_limit.algorithm == "sliding_window"
                assert features.rate_limit.bucket_size == 50
                assert features.monitoring.log_threshold == 0.05
                
            finally:
                Path(f.name).unlink()


class TestConfigDataclassCreation:
    """Test creating config dataclasses from dictionary data."""
    
    def test_parse_features_empty(self):
        """Test parsing empty features configuration."""
        features = GatewayConfig._parse_features({})
        
        assert features.cache is None
        assert features.retry is None
        assert features.timeout is None
        assert features.rate_limit is None
        assert features.monitoring is None
    
    def test_parse_cache_config(self):
        """Test parsing cache configuration."""
        cache_data = {
            "cache": {
                "expire_s": 600,
                "cache_key": "test_key"
            }
        }
        features = GatewayConfig._parse_features(cache_data)
        
        assert features.cache is not None
        assert features.cache.expire_s == 600
        assert features.cache.cache_key == "test_key"
        assert features.cache.encoder is None  # Can't be serialized
    
    def test_parse_retry_config(self):
        """Test parsing retry configuration."""
        retry_data = {
            "retry": {
                "max_attempts": 5,
                "wait": 2.5
            }
        }
        features = GatewayConfig._parse_features(retry_data)
        
        assert features.retry is not None
        assert features.retry.max_attempts == 5
        assert features.retry.wait == 2.5
        assert features.retry.exceptions == (Exception,)  # Default
        assert features.retry.on_fail is None  # Can't be serialized
        assert features.retry.logger is None  # Can't be serialized
    
    def test_parse_timeout_config(self):
        """Test parsing timeout configuration."""
        timeout_data = {
            "timeout": {
                "seconds": 3.5
            }
        }
        features = GatewayConfig._parse_features(timeout_data)
        
        assert features.timeout is not None
        assert features.timeout.seconds == 3.5
        assert features.timeout.logger is None  # Can't be serialized
    
    def test_parse_rate_limit_config(self):
        """Test parsing rate limit configuration."""
        rate_limit_data = {
            "rate_limit": {
                "quota": 150,
                "duration": 90,
                "algorithm": "token_bucket",
                "bucket_size": 25
            }
        }
        features = GatewayConfig._parse_features(rate_limit_data)
        
        assert features.rate_limit is not None
        assert features.rate_limit.quota == 150
        assert features.rate_limit.duration == 90
        assert features.rate_limit.algorithm == "token_bucket"
        assert features.rate_limit.bucket_size == 25
    
    def test_parse_monitoring_config(self):
        """Test parsing monitoring configuration."""
        monitoring_data = {
            "monitoring": {
                "log_threshold": 0.025
            }
        }
        features = GatewayConfig._parse_features(monitoring_data)
        
        assert features.monitoring is not None
        assert features.monitoring.log_threshold == 0.025