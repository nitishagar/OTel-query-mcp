"""Unit tests for configuration management."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from pydantic import ValidationError

from otel_query_server.config import (
    BackendsConfig,
    CacheConfig,
    Config,
    ElasticCloudConfig,
    GrafanaConfig,
    OTELCollectorConfig,
    OpenSearchConfig,
    ServerConfig,
    get_config,
    load_config,
    set_config,
)


class TestOTELCollectorConfig:
    """Test OTEL Collector configuration."""
    
    def test_valid_config(self):
        """Test creating valid OTEL Collector config."""
        config = OTELCollectorConfig(
            endpoint="localhost:4317",
            insecure=True,
            headers={"Authorization": "Bearer token"},
            compression="gzip"
        )
        
        assert config.endpoint == "localhost:4317"
        assert config.insecure is True
        assert config.headers["Authorization"] == "Bearer token"
        assert config.compression == "gzip"
    
    def test_endpoint_validation(self):
        """Test endpoint validation."""
        # Valid endpoints
        OTELCollectorConfig(endpoint="localhost:4317")
        OTELCollectorConfig(endpoint="http://localhost:4317")
        OTELCollectorConfig(endpoint="https://collector.example.com:4317")
        
        # Invalid endpoints
        with pytest.raises(ValidationError, match="Endpoint cannot be empty"):
            OTELCollectorConfig(endpoint="")
        
        with pytest.raises(ValidationError, match="Invalid endpoint format"):
            OTELCollectorConfig(endpoint="invalid-endpoint")
    
    def test_default_values(self):
        """Test default configuration values."""
        config = OTELCollectorConfig(endpoint="localhost:4317")
        
        assert config.enabled is True
        assert config.timeout_seconds == 30
        assert config.max_retries == 3
        assert config.retry_delay_seconds == 1.0
        assert config.headers == {}
        assert config.compression is None


class TestGrafanaConfig:
    """Test Grafana configuration."""
    
    def test_valid_config(self):
        """Test creating valid Grafana config."""
        config = GrafanaConfig(
            tempo_url="http://localhost:3200",
            loki_url="http://localhost:3100",
            prometheus_url="http://localhost:9090",
            api_key="test-key",
            org_id=1
        )
        
        assert config.tempo_url == "http://localhost:3200"
        assert config.loki_url == "http://localhost:3100"
        assert config.prometheus_url == "http://localhost:9090"
        assert config.api_key == "test-key"
        assert config.org_id == 1
    
    def test_url_validation(self):
        """Test URL validation."""
        # Valid URLs
        GrafanaConfig(tempo_url="http://localhost:3200")
        GrafanaConfig(tempo_url="https://tempo.example.com")
        
        # Invalid URLs
        with pytest.raises(ValidationError, match="URL must start with http:// or https://"):
            GrafanaConfig(tempo_url="localhost:3200")
    
    def test_optional_urls(self):
        """Test that all URLs are optional."""
        config = GrafanaConfig()
        assert config.tempo_url is None
        assert config.loki_url is None
        assert config.prometheus_url is None


class TestElasticCloudConfig:
    """Test Elastic Cloud configuration."""
    
    def test_cloud_id_config(self):
        """Test configuration with cloud ID."""
        config = ElasticCloudConfig(
            cloud_id="deployment:dXMtY2VudHJhbDEuZ2NwLmNsb3VkLmVzLmlvOjQ0MyQ...",
            username="elastic",
            password="password"
        )
        
        assert config.cloud_id == "deployment:dXMtY2VudHJhbDEuZ2NwLmNsb3VkLmVzLmlvOjQ0MyQ..."
        assert config.username == "elastic"
        assert config.password == "password"
    
    def test_elasticsearch_url_config(self):
        """Test configuration with Elasticsearch URL."""
        config = ElasticCloudConfig(
            elasticsearch_url="https://es.example.com:9243",
            api_key="test-api-key"
        )
        
        assert config.elasticsearch_url == "https://es.example.com:9243"
        assert config.api_key == "test-api-key"
    
    def test_validation_requires_cloud_id_or_url(self):
        """Test that either cloud_id or elasticsearch_url is required."""
        with pytest.raises(ValidationError, match="Either cloud_id or elasticsearch_url must be provided"):
            ElasticCloudConfig()


class TestOpenSearchConfig:
    """Test OpenSearch configuration."""
    
    def test_valid_config(self):
        """Test creating valid OpenSearch config."""
        config = OpenSearchConfig(
            hosts=["https://localhost:9200", "https://localhost:9201"],
            username="admin",
            password="admin",
            verify_certs=False,
            ca_certs="/path/to/ca.pem"
        )
        
        assert len(config.hosts) == 2
        assert config.hosts[0] == "https://localhost:9200"
        assert config.username == "admin"
        assert config.verify_certs is False
        assert config.ca_certs == "/path/to/ca.pem"
    
    def test_host_validation(self):
        """Test host validation."""
        # Valid hosts
        OpenSearchConfig(hosts=["http://localhost:9200"])
        OpenSearchConfig(hosts=["https://opensearch.example.com:9200"])
        
        # Invalid hosts
        with pytest.raises(ValidationError, match="At least one host must be provided"):
            OpenSearchConfig(hosts=[])
        
        with pytest.raises(ValidationError, match="Host must start with http:// or https://"):
            OpenSearchConfig(hosts=["localhost:9200"])


class TestConfig:
    """Test main configuration class."""
    
    def test_default_config(self):
        """Test creating config with defaults."""
        config = Config()
        
        assert config.server.name == "otel-query-server"
        assert config.server.version == "0.1.0"
        assert config.cache.enabled is True
        assert config.cache.max_size == 1000
    
    def test_from_yaml(self):
        """Test loading configuration from YAML."""
        yaml_content = """
server:
  name: test-server
  log_level: DEBUG

cache:
  enabled: false
  max_size: 500

backends:
  otel_collector:
    endpoint: test:4317
    insecure: false
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            try:
                config = Config.from_yaml(f.name)
                
                assert config.server.name == "test-server"
                assert config.server.log_level == "DEBUG"
                assert config.cache.enabled is False
                assert config.cache.max_size == 500
                assert config.backends.otel_collector.endpoint == "test:4317"
                assert config.backends.otel_collector.insecure is False
            finally:
                os.unlink(f.name)
    
    def test_from_env(self):
        """Test loading configuration from environment variables."""
        with patch.dict(os.environ, {
            "OTEL_QUERY_SERVER__NAME": "env-server",
            "OTEL_QUERY_SERVER__LOG_LEVEL": "ERROR",
            "OTEL_QUERY_CACHE__ENABLED": "false",
            "OTEL_QUERY_CACHE__MAX_SIZE": "200"
        }):
            config = Config.from_env()
            
            assert config.server.name == "env-server"
            assert config.server.log_level == "ERROR"
            assert config.cache.enabled is False
            assert config.cache.max_size == 200
    
    def test_get_enabled_backends(self):
        """Test getting list of enabled backends."""
        config = Config(
            backends=BackendsConfig(
                otel_collector=OTELCollectorConfig(endpoint="localhost:4317", enabled=True),
                grafana=GrafanaConfig(enabled=False),
                elastic_cloud=ElasticCloudConfig(
                    elasticsearch_url="https://es.example.com",
                    enabled=True
                )
            )
        )
        
        enabled = config.get_enabled_backends()
        assert "otel_collector" in enabled
        assert "grafana" not in enabled
        assert "elastic_cloud" in enabled
    
    def test_validate_backends(self):
        """Test backend validation."""
        # Valid config with at least one backend
        config = Config(
            backends=BackendsConfig(
                otel_collector=OTELCollectorConfig(endpoint="localhost:4317")
            )
        )
        config.validate_backends()  # Should not raise
        
        # Invalid config with no backends
        config = Config()
        with pytest.raises(ValueError, match="At least one backend must be configured"):
            config.validate_backends()


class TestConfigLoading:
    """Test configuration loading functions."""
    
    def test_load_config_with_path(self):
        """Test loading config with explicit path."""
        yaml_content = """
server:
  name: file-server
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            try:
                config = load_config(f.name)
                assert config.server.name == "file-server"
            finally:
                os.unlink(f.name)
    
    def test_load_config_from_default_location(self):
        """Test loading from default location."""
        # Create config.yaml in current directory
        yaml_content = """
server:
  name: default-server
"""
        
        with open("config.yaml", "w") as f:
            f.write(yaml_content)
        
        try:
            config = load_config()
            assert config.server.name == "default-server"
        finally:
            if Path("config.yaml").exists():
                os.unlink("config.yaml")
    
    def test_load_config_fallback_to_env(self):
        """Test fallback to environment variables."""
        # Ensure no default config files exist
        for path in ["config.yaml", "config.yml"]:
            if Path(path).exists():
                os.unlink(path)
        
        with patch.dict(os.environ, {"OTEL_QUERY_SERVER__NAME": "env-fallback"}):
            config = load_config()
            assert config.server.name == "env-fallback"
    
    def test_get_set_config(self):
        """Test global config getter and setter."""
        # Clear any existing config
        set_config(None)
        
        # First call should create config
        config1 = get_config()
        assert config1 is not None
        
        # Subsequent calls should return same instance
        config2 = get_config()
        assert config2 is config1
        
        # Setting new config should update
        new_config = Config(server=ServerConfig(name="new-server"))
        set_config(new_config)
        
        config3 = get_config()
        assert config3 is new_config
        assert config3.server.name == "new-server" 