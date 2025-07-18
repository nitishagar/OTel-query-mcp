# OpenTelemetry Query Server

An MCP (Model Context Protocol) server that provides tools for querying observability data from various backends including OpenTelemetry Collector, Grafana, Elastic Cloud, and OpenSearch.

## Features

- 🔍 **Multi-Backend Support**: Query traces, logs, and metrics from multiple observability platforms
- 🚀 **Fast & Async**: Built with async Python for high performance
- 🔧 **MCP Compatible**: Works with any MCP-enabled client
- 💾 **Smart Caching**: LRU cache with configurable TTL
- 🛡️ **Type Safe**: Full type annotations with Pydantic models
- 📊 **Rich Query Tools**: Search traces, logs, metrics, and correlate across signals

## Quick Start

```bash
# Install dependencies
pip install -e .

# Configure backends
cp examples/config.yaml config.yaml
# Edit config.yaml with your backend details

# Run the server
python -m otel_query_server.server
```

## Supported Backends

- OpenTelemetry Collector (OTLP)
- Grafana (Tempo, Loki, Prometheus)
- Elastic Cloud (APM, Elasticsearch)
- OpenSearch

## Available Tools

- `search_traces`: Search for distributed traces
- `search_logs`: Query application logs
- `query_metrics`: Retrieve and aggregate metrics
- `get_service_health`: Check service health status
- `correlate_trace_logs`: Correlate traces with logs

## Documentation

See the [docs](./docs) directory for detailed documentation.

## License

Apache License 2.0 - see [LICENSE](./LICENSE) for details. 