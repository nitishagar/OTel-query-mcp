"""Configuration management for OpenTelemetry Query Server."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendConfig(BaseModel):
    """Base configuration for backend drivers."""
    
    enabled: bool = Field(default=True, description="Whether this backend is enabled")
    timeout_seconds: int = Field(default=30, description="Query timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum number of retries")
    retry_delay_seconds: float = Field(default=1.0, description="Delay between retries")


class OTELCollectorConfig(BackendConfig):
    """Configuration for OpenTelemetry Collector backend."""
    
    endpoint: str = Field(..., description="OTLP gRPC endpoint")
    insecure: bool = Field(default=True, description="Use insecure connection")
    headers: Dict[str, str] = Field(default_factory=dict, description="Additional headers")
    compression: Optional[str] = Field(default=None, description="Compression method (gzip, none)")
    
    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        """Validate endpoint format."""
        if not v:
            raise ValueError("Endpoint cannot be empty")
        if not (v.startswith("http://") or v.startswith("https://") or ":" in v):
            raise ValueError("Invalid endpoint format")
        return v


class GrafanaConfig(BackendConfig):
    """Configuration for Grafana backend."""
    
    tempo_url: Optional[str] = Field(default=None, description="Grafana Tempo URL")
    loki_url: Optional[str] = Field(default=None, description="Grafana Loki URL")
    prometheus_url: Optional[str] = Field(default=None, description="Prometheus URL")
    api_key: Optional[str] = Field(default=None, description="API key for authentication")
    org_id: Optional[int] = Field(default=None, description="Organization ID")
    
    @field_validator("tempo_url", "loki_url", "prometheus_url")
    @classmethod
    def validate_urls(cls, v: Optional[str]) -> Optional[str]:
        """Validate URL format."""
        if v and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class ElasticCloudConfig(BackendConfig):
    """Configuration for Elastic Cloud backend."""
    
    cloud_id: Optional[str] = Field(default=None, description="Elastic Cloud ID")
    elasticsearch_url: Optional[str] = Field(default=None, description="Elasticsearch URL")
    username: Optional[str] = Field(default=None, description="Username for authentication")
    password: Optional[str] = Field(default=None, description="Password for authentication")
    api_key: Optional[str] = Field(default=None, description="API key for authentication")
    apm_server_url: Optional[str] = Field(default=None, description="APM Server URL")
    
    @model_validator(mode="after")
    def validate_cloud_id_or_url(self) -> "ElasticCloudConfig":
        """Ensure either cloud_id or elasticsearch_url is provided."""
        if not self.cloud_id and not self.elasticsearch_url:
            raise ValueError("Either cloud_id or elasticsearch_url must be provided")
        return self


class OpenSearchConfig(BackendConfig):
    """Configuration for OpenSearch backend."""
    
    hosts: List[str] = Field(..., description="List of OpenSearch hosts")
    username: Optional[str] = Field(default=None, description="Username for authentication")
    password: Optional[str] = Field(default=None, description="Password for authentication")
    verify_certs: bool = Field(default=True, description="Verify SSL certificates")
    ca_certs: Optional[str] = Field(default=None, description="Path to CA certificates")
    
    @field_validator("hosts")
    @classmethod
    def validate_hosts(cls, v: List[str]) -> List[str]:
        """Validate host format."""
        if not v:
            raise ValueError("At least one host must be provided")
        for host in v:
            if not (host.startswith("http://") or host.startswith("https://")):
                raise ValueError(f"Host must start with http:// or https://: {host}")
        return v


class CacheConfig(BaseModel):
    """Configuration for caching layer."""
    
    enabled: bool = Field(default=True, description="Whether caching is enabled")
    max_size: int = Field(default=1000, description="Maximum number of cached items")
    ttl_seconds: int = Field(default=300, description="Default TTL in seconds")
    trace_ttl_seconds: int = Field(default=600, description="TTL for trace cache")
    log_ttl_seconds: int = Field(default=300, description="TTL for log cache")
    metric_ttl_seconds: int = Field(default=60, description="TTL for metric cache")


class ServerConfig(BaseModel):
    """Configuration for MCP server."""
    
    name: str = Field(default="otel-query-server", description="Server name")
    version: str = Field(default="0.1.0", description="Server version")
    description: str = Field(
        default="MCP server for querying observability data",
        description="Server description"
    )
    log_level: str = Field(default="INFO", description="Logging level")
    max_concurrent_requests: int = Field(default=10, description="Maximum concurrent requests")


class BackendsConfig(BaseModel):
    """Configuration for all backends."""
    
    otel_collector: Optional[OTELCollectorConfig] = Field(default=None)
    grafana: Optional[GrafanaConfig] = Field(default=None)
    elastic_cloud: Optional[ElasticCloudConfig] = Field(default=None)
    opensearch: Optional[OpenSearchConfig] = Field(default=None)


class Config(BaseSettings):
    """Main configuration class."""
    
    model_config = SettingsConfigDict(
        env_prefix="OTEL_QUERY_",
        env_nested_delimiter="__",
        case_sensitive=False
    )
    
    server: ServerConfig = Field(default_factory=ServerConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    backends: BackendsConfig = Field(default_factory=BackendsConfig)
    
    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "Config":
        """Load configuration from YAML file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        
        # Merge with environment variables
        return cls(**data)
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables only."""
        return cls()
    
    def get_enabled_backends(self) -> List[str]:
        """Get list of enabled backend names."""
        enabled = []
        for name, config in self.backends.model_dump().items():
            if config and config.get("enabled", True):
                enabled.append(name)
        return enabled
    
    def validate_backends(self) -> None:
        """Validate that at least one backend is configured."""
        if not any([
            self.backends.otel_collector,
            self.backends.grafana,
            self.backends.elastic_cloud,
            self.backends.opensearch
        ]):
            raise ValueError("At least one backend must be configured")


def load_config(config_path: Optional[Union[str, Path]] = None) -> Config:
    """Load configuration from file or environment."""
    if config_path:
        return Config.from_yaml(config_path)
    
    # Try to load from default locations
    default_paths = [
        Path("config.yaml"),
        Path("config.yml"),
        Path.home() / ".otel-query-server" / "config.yaml",
        Path("/etc/otel-query-server/config.yaml"),
    ]
    
    for path in default_paths:
        if path.exists():
            return Config.from_yaml(path)
    
    # Fall back to environment variables only
    return Config.from_env()


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config 