# Local Development Guide

This guide covers setting up and running the OpenTelemetry Query Server locally for development.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Running the Server](#running-the-server)
- [Configuration](#configuration)
- [Testing](#testing)
- [Common Issues](#common-issues)

## Prerequisites

- Python 3.9 or higher
- Git
- Docker (optional, for running backend services)
- An OpenTelemetry-compatible backend (OTEL Collector, Grafana, etc.)

## Initial Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/otel-query-server.git
cd otel-query-server
```

### 2. Create a Virtual Environment

```bash
# Using venv
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Or using conda
conda create -n otel-query-server python=3.11
conda activate otel-query-server
```

### 3. Install Dependencies

```bash
# Install in development mode with all extras
pip install -e ".[dev,test,docs]"

# Or just the essentials
pip install -e .
```

### 4. Set Up Pre-commit Hooks (Optional)

```bash
pre-commit install
```

## Running the Server

### Basic Usage

```bash
# Using the default configuration search paths
python -m otel_query_server.server

# With a specific configuration file
python -m otel_query_server.server --config config.yaml

# With environment variables
export OTEL_QUERY_SERVER__LOG_LEVEL=DEBUG
export OTEL_QUERY_BACKENDS__OTEL_COLLECTOR__ENDPOINT=localhost:4317
python -m otel_query_server.server
```

### Using FastMCP CLI

The server uses FastMCP, which provides additional CLI options:

```bash
# Run with stdio transport (default for MCP)
fastmcp run otel_query_server.server:mcp

# Run with HTTP transport (for testing)
fastmcp run otel_query_server.server:mcp --transport http --port 8080

# Run with WebSocket transport
fastmcp run otel_query_server.server:mcp --transport ws --port 8080
```

### Docker Compose Setup

For a complete local environment with backend services:

```bash
# Start all services
docker-compose -f examples/docker-compose.yaml up

# Start only specific services
docker-compose -f examples/docker-compose.yaml up otel-collector grafana

# Run in background
docker-compose -f examples/docker-compose.yaml up -d
```

## Configuration

### Configuration File Structure

Create a `config.yaml` file in your project root:

```yaml
# Server Configuration
server:
  name: otel-query-server-dev
  version: 0.1.0
  description: Development instance
  log_level: DEBUG  # DEBUG, INFO, WARNING, ERROR
  max_concurrent_requests: 10

# Cache Configuration
cache:
  enabled: true
  max_size: 1000
  ttl_seconds: 300
  trace_ttl_seconds: 600
  log_ttl_seconds: 300
  metric_ttl_seconds: 60

# Backend Configuration
backends:
  # OpenTelemetry Collector
  otel_collector:
    enabled: true
    endpoint: localhost:4317  # gRPC endpoint
    insecure: true  # Set to false for production
    timeout_seconds: 30
    max_retries: 3
    retry_delay_seconds: 1.0
    headers:
      # Custom headers if needed
      # Authorization: Bearer <token>
    compression: gzip  # none, gzip

  # Grafana (Tempo, Loki, Prometheus)
  grafana:
    enabled: false
    tempo_url: http://localhost:3200
    loki_url: http://localhost:3100
    prometheus_url: http://localhost:9090
    # api_key: your-api-key  # Uncomment if using API key auth
    # org_id: 1
    timeout_seconds: 30

  # Elastic Cloud
  elastic_cloud:
    enabled: false
    # Option 1: Cloud ID
    # cloud_id: deployment:base64data...
    # Option 2: Direct URL
    # elasticsearch_url: https://your-cluster.es.io:9243
    # username: elastic
    # password: changeme
    # Or use API key
    # api_key: base64apikey...
    timeout_seconds: 30

  # OpenSearch
  opensearch:
    enabled: false
    hosts:
      - https://localhost:9200
    username: admin
    password: admin
    verify_certs: false  # Set to true for production
    # ca_certs: /path/to/ca.pem
    timeout_seconds: 30
```

### Environment Variables

All configuration options can be overridden using environment variables:

```bash
# Server settings
export OTEL_QUERY_SERVER__NAME=my-dev-server
export OTEL_QUERY_SERVER__LOG_LEVEL=DEBUG

# Cache settings
export OTEL_QUERY_CACHE__ENABLED=true
export OTEL_QUERY_CACHE__MAX_SIZE=2000

# Backend settings
export OTEL_QUERY_BACKENDS__OTEL_COLLECTOR__ENDPOINT=production:4317
export OTEL_QUERY_BACKENDS__OTEL_COLLECTOR__INSECURE=false
export OTEL_QUERY_BACKENDS__GRAFANA__API_KEY=secret-key
```

### Configuration Priority

Configuration is loaded in the following order (later sources override earlier ones):

1. Default values in code
2. Configuration file (`config.yaml`)
3. Environment variables
4. Command-line arguments (if any)

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=otel_query_server --cov-report=html

# Run specific test categories
pytest tests/unit/          # Unit tests only
pytest tests/integration/   # Integration tests only
pytest -m "not slow"       # Skip slow tests

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_models.py

# Run tests in parallel
pytest -n auto
```

### Code Quality Checks

```bash
# Format code
black src tests

# Lint code
ruff check src tests

# Type checking
mypy src

# Security scanning
bandit -r src/

# All checks at once
make lint  # If Makefile is available
```

### Testing with Real Backends

1. **OpenTelemetry Collector**:
   ```bash
   # Start OTEL Collector
   docker run -p 4317:4317 -p 4318:4318 \
     -v $(pwd)/examples/otel-collector-config.yaml:/etc/otel-collector-config.yaml \
     otel/opentelemetry-collector:latest \
     --config=/etc/otel-collector-config.yaml
   ```

2. **Grafana Stack**:
   ```bash
   # Use the provided docker-compose
   docker-compose -f examples/docker-compose.yaml up tempo loki prometheus grafana
   ```

3. **Send Test Data**:
   ```bash
   # Use OTEL CLI or SDK to send test traces
   otel-cli span --service test-service --name test-span
   ```

## Common Issues

### Issue: Connection Refused to Backend

**Solution**: Ensure the backend service is running and accessible:

```bash
# Check if OTEL Collector is running
telnet localhost 4317

# Check Docker containers
docker ps

# Check service logs
docker logs otel-collector
```

### Issue: ImportError or ModuleNotFoundError

**Solution**: Ensure you've installed the package in development mode:

```bash
pip install -e .
```

### Issue: Configuration Not Loading

**Solution**: Check configuration file path and syntax:

```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('config.yaml'))"

# Check environment variables
env | grep OTEL_QUERY
```

### Issue: Permission Denied Errors

**Solution**: Ensure proper permissions for cache and log directories:

```bash
mkdir -p logs cache
chmod 755 logs cache
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes and Test

```bash
# Make your changes
vim src/otel_query_server/...

# Run tests
pytest tests/

# Check code quality
black src tests
ruff check src tests
mypy src
```

### 3. Test with MCP Client

```bash
# In one terminal, start the server
python -m otel_query_server.server --config config.yaml

# In another terminal, test with MCP client
mcp-client connect stdio -- python -m otel_query_server.server
```

### 4. Commit and Push

```bash
git add .
git commit -m "feat: add new feature"
git push origin feature/your-feature-name
```

## Advanced Configuration

### Multi-Backend Setup

Configure multiple backends for different data types:

```yaml
backends:
  # Use OTEL Collector for traces
  otel_collector:
    enabled: true
    endpoint: traces-collector:4317
  
  # Use Grafana Loki for logs
  grafana:
    enabled: true
    tempo_url: null  # Disable Tempo
    loki_url: http://localhost:3100
    prometheus_url: null  # Disable Prometheus
  
  # Use Elastic for metrics
  elastic_cloud:
    enabled: true
    elasticsearch_url: https://metrics.es.io:9243
    username: elastic
    password: changeme
```

### Performance Tuning

```yaml
server:
  max_concurrent_requests: 50  # Increase for high load

cache:
  max_size: 10000  # Increase cache size
  trace_ttl_seconds: 3600  # Cache traces for 1 hour

backends:
  otel_collector:
    timeout_seconds: 60  # Increase timeout for slow queries
    max_retries: 5  # More retries for unreliable networks
```

### Security Configuration

For production-like security in development:

```yaml
backends:
  otel_collector:
    insecure: false
    headers:
      Authorization: Bearer ${OTEL_AUTH_TOKEN}
  
  elastic_cloud:
    api_key: ${ELASTIC_API_KEY}
    # Use environment variables for secrets
```

## Next Steps

- Check out the [API Documentation](api.md) for available MCP tools
- See [examples/](../examples/) for more configuration examples
- Read the [Contributing Guide](../CONTRIBUTING.md) for development guidelines
- Join our [Discord/Slack] for help and discussions 