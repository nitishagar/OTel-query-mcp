# OpenTelemetry Query Server

[![CI](https://github.com/nitishagar/OTel-query-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/nitishagar/OTel-query-mcp/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/nitishagar/OTel-query-mcp/branch/main/graph/badge.svg)](https://codecov.io/gh/nitishagar/OTel-query-mcp)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

An MCP (Model Context Protocol) server that provides tools for querying observability data from various backends including OpenTelemetry Collector, Grafana, Elastic Cloud, and OpenSearch.

## Features

- 🔍 **Multi-Backend Support**: Query traces, logs, and metrics from multiple observability platforms
- 🚀 **Fast & Async**: Built with async Python for high performance
- 🔧 **MCP Compatible**: Works with any MCP-enabled client
- 💾 **Smart Caching**: LRU cache with configurable TTL per data type
- 🛡️ **Type Safe**: Full type annotations with Pydantic models
- 📊 **Rich Query Tools**: Search traces, logs, metrics, and correlate across signals
- ⚡ **Production Ready**: Structured logging, retries, health checks, and graceful shutdown

## Quick Start

### Installation

```bash
# From source
git clone https://github.com/nitishagar/OTel-query-mcp.git
cd OTel-query-mcp
pip install -e .

# From PyPI (when published)
pip install otel-query-server
```

### Basic Usage

1. **Create configuration** (`config.yaml`):

```yaml
server:
  name: my-otel-server
  log_level: INFO

backends:
  otel_collector:
    enabled: true
    endpoint: localhost:4317
    insecure: true
```

2. **Run the server**:

```bash
# Using Python module
python -m otel_query_server.server --config config.yaml

# Using FastMCP CLI
fastmcp run otel_query_server.server:mcp

# With environment variables
export OTEL_QUERY_BACKENDS__OTEL_COLLECTOR__ENDPOINT=prod:4317
python -m otel_query_server.server
```

3. **Connect with MCP client**:

```bash
mcp-client connect stdio -- python -m otel_query_server.server
```

## Local Development

### Prerequisites

- Python 3.9+
- Docker (optional, for backend services)
- Git

### Setup

```bash
# Clone and setup
git clone https://github.com/nitishagar/OTel-query-mcp.git
cd OTel-query-mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev,test]"

# Run tests
pytest --cov=otel_query_server

# Start backend services
docker-compose -f examples/docker-compose.yaml up -d
```

### Configuration

The server supports configuration via:
1. YAML configuration file
2. Environment variables (prefix: `OTEL_QUERY_`)
3. Command-line arguments

**Key configuration options:**

```yaml
# Server settings
server:
  log_level: DEBUG  # DEBUG, INFO, WARNING, ERROR
  max_concurrent_requests: 10

# Caching
cache:
  enabled: true
  max_size: 1000
  trace_ttl_seconds: 600  # 10 minutes
  log_ttl_seconds: 300    # 5 minutes
  metric_ttl_seconds: 60  # 1 minute

# Backends (see examples/config.yaml for full options)
backends:
  otel_collector:
    endpoint: localhost:4317
    insecure: true
  grafana:
    tempo_url: http://localhost:3200
    loki_url: http://localhost:3100
  # ... more backends
```

See [docs/local-development.md](docs/local-development.md) for detailed setup instructions.

## Supported Backends

- **OpenTelemetry Collector** (OTLP gRPC/HTTP)
- **Grafana Stack**:
  - Tempo (traces)
  - Loki (logs)  
  - Prometheus (metrics)
- **Elastic Cloud** (APM, Elasticsearch)
- **OpenSearch**

## Available MCP Tools

- `search_traces`: Search for distributed traces
- `search_logs`: Query application logs
- `query_metrics`: Retrieve and aggregate metrics
- `get_service_health`: Check service health status
- `correlate_trace_logs`: Find logs related to a trace
- `get_server_info`: Get server configuration info

## CI/CD

This project uses GitHub Actions for continuous integration:

- **Automated Testing**: Tests run on every PR across Python 3.9-3.12 on Linux, macOS, and Windows
- **Code Quality**: Black formatting, Ruff linting, MyPy type checking
- **Security Scanning**: Trivy and Bandit security analysis
- **Coverage Reports**: Automatic upload to Codecov
- **Docker Builds**: Containerized builds on every commit

See [.github/workflows/ci.yml](.github/workflows/ci.yml) for the complete pipeline.

## Documentation

- [Local Development Guide](docs/local-development.md) - Detailed setup and configuration
- [API Documentation](docs/api.md) - MCP tools reference
- [Architecture Overview](docs/architecture.md) - System design and patterns

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache License 2.0 - see [LICENSE](./LICENSE) for details. 