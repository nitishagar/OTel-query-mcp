# CLAUDE_CODE.md

## MCP OpenTelemetry Query Server Development Guide

This document outlines the development approach for the `otel-query-server` project, designed for iterative development with frequent checkpointing and open-source collaboration. **Updated to incorporate the emerging MCP OpenTelemetry Trace Support proposal.**

## Project Overview \& MCP OTel Integration

Our `otel-query-server` sits at the intersection of two complementary initiatives:

1. **Core Mission**: Provide MCP tools for querying observability data from various backends
2. **MCP OTel Integration**: Support the proposed `notifications/otel/trace` capability for enhanced observability

The [MCP OTel Tracing Proposal](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/269) introduces mechanisms for MCP servers to emit trace data back to clients. Our server can both **consume** this capability (by implementing the OTel notification support) and **provide** it (by emitting traces of its own query operations).

## Project Structure - Updated

```
otel-query-server/
├── src/
│   ├── otel_query_server/
│   │   ├── __init__.py
│   │   ├── server.py              # FastMCP server with OTel capability
│   │   ├── config.py              # Configuration + OTel settings
│   │   ├── models.py              # Pydantic models + OTel trace models
│   │   ├── otel/                  # NEW: OpenTelemetry integration
│   │   │   ├── __init__.py
│   │   │   ├── tracer.py          # OTel tracer setup
│   │   │   ├── notifications.py   # OTel notification handling
│   │   │   └── correlation.py     # Trace correlation utilities
│   │   ├── tools/                 # MCP tool implementations
│   │   │   ├── __init__.py
│   │   │   ├── search_traces.py   # Enhanced with OTel emission
│   │   │   ├── search_logs.py
│   │   │   ├── query_metrics.py
│   │   │   ├── get_service_health.py
│   │   │   └── correlate_trace_logs.py
│   │   └── drivers/               # Backend integrations
│   │       ├── __init__.py
│   │       ├── base.py            # Base driver with OTel instrumentation
│   │       ├── otel_collector.py
│   │       ├── grafana.py
│   │       ├── elastic_cloud.py
│   │       └── opensearch.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── otel/                      # NEW: OTel-specific tests
│   └── fixtures/
├── examples/
│   ├── config.yaml                # Updated with OTel config
│   ├── otel-config.yaml           # NEW: OTel-specific config
│   └── docker-compose.yaml
├── docs/
│   ├── api.md
│   ├── otel-integration.md        # NEW: OTel integration docs
│   └── troubleshooting.md
├── Dockerfile
├── pyproject.toml                 # Updated with OTel dependencies
└── README.md
```


## Development Phases - Updated with OTel Integration

### Phase 1: Foundation (Commits 1-7) - Extended

**Goal**: Establish basic project structure and prepare for OTel integration

#### Commit 1: Project scaffolding

```bash
mkdir -p otel-query-server/{src/otel_query_server/{tools,drivers,otel},tests/{unit,integration,otel,fixtures},examples,docs}
cd otel-query-server
git init
git add .
git commit -m "feat: initial project structure with OTel integration support"
```


#### Commit 2: Enhanced dependencies

```bash
git add pyproject.toml
git commit -m "feat: add dependencies including opentelemetry-api, opentelemetry-sdk"
```

**Key additions to pyproject.toml:**

```toml
[project]
dependencies = [
    "fastmcp>=1.0.0",
    "opentelemetry-api>=1.20.0",
    "opentelemetry-sdk>=1.20.0",
    "opentelemetry-exporter-otlp>=1.20.0",
    "opentelemetry-instrumentation>=0.41b0",
    # ... existing dependencies
]
```


#### Commit 3: Core data models with OTel support

```bash
git add src/otel_query_server/models.py
git commit -m "feat: add Pydantic models with OTel ResourceSpans support"
```


#### Commit 4: Enhanced configuration system

```bash
git add src/otel_query_server/config.py examples/config.yaml
git commit -m "feat: implement configuration with OTel settings and traceToken support"
```


#### Commit 5: OTel tracer foundation

```bash
git add src/otel_query_server/otel/tracer.py
git commit -m "feat: implement OpenTelemetry tracer setup and configuration"
```


#### Commit 6: Base driver with OTel instrumentation

```bash
git add src/otel_query_server/drivers/base.py
git commit -m "feat: create base driver with automatic OTel span creation"
```


#### Commit 7: FastMCP server with OTel capability

```bash
git add src/otel_query_server/server.py
git commit -m "feat: implement FastMCP server with otel.traces capability"
```


### Phase 2: OTel Integration (Commits 8-15) - New Phase

**Goal**: Complete OpenTelemetry integration before tool implementation

#### Commit 8: OTel notification system

```bash
git add src/otel_query_server/otel/notifications.py
git commit -m "feat: implement notifications/otel/trace emission"
```


#### Commit 9: Trace correlation utilities

```bash
git add src/otel_query_server/otel/correlation.py
git commit -m "feat: add traceToken correlation and span stitching"
```


#### Commit 10: OTel configuration schema

```bash
git add examples/otel-config.yaml
git commit -m "feat: add OTel-specific configuration examples"
```


#### Commit 11: OTel unit tests

```bash
git add tests/otel/test_tracer.py tests/otel/test_notifications.py
git commit -m "test: add comprehensive OTel integration tests"
```


#### Commit 12: Enhanced server capabilities

```bash
git add src/otel_query_server/server.py
git commit -m "feat: implement MCP server capability declaration for otel.traces"
```


#### Commit 13: OTel middleware

```bash
git add src/otel_query_server/otel/middleware.py
git commit -m "feat: add OTel middleware for automatic span creation per MCP request"
```


#### Commit 14: Documentation for OTel integration

```bash
git add docs/otel-integration.md
git commit -m "docs: add comprehensive OTel integration documentation"
```


#### Commit 15: OTel integration testing

```bash
git add tests/integration/test_otel_integration.py
git commit -m "test: add integration tests for OTel notification emission"
```


### Phase 3: First Tool with OTel (Commits 16-20) - Modified

**Goal**: Implement one complete tool with full OTel integration

#### Commit 16: OpenTelemetry Collector driver with OTel

```bash
git add src/otel_query_server/drivers/otel_collector.py
git commit -m "feat: implement OTEL collector driver with automatic span emission"
```


#### Commit 17: Search traces tool with OTel

```bash
git add src/otel_query_server/tools/search_traces.py
git commit -m "feat: implement search_traces with traceToken handling and span emission"
```


#### Commit 18: Enhanced caching with OTel

```bash
git add src/otel_query_server/cache.py
git commit -m "feat: add LRU cache with OTel span tracking"
```


#### Commit 19: OTel-aware unit tests

```bash
git add tests/unit/test_search_traces.py
git commit -m "test: add unit tests for search_traces with OTel validation"
```


#### Commit 20: End-to-end OTel testing

```bash
git add tests/integration/test_otel_e2e.py
git commit -m "test: add end-to-end OTel trace emission and correlation tests"
```


### Phase 4: Remaining Backend Drivers (Commits 21-30) - Updated

**Goal**: Implement all backend drivers with consistent OTel integration

#### Commits 21-23: Grafana driver with OTel

```bash
git commit -m "feat: implement Grafana driver with OTel span emission"
git commit -m "feat: extend search_traces to support Grafana with OTel"
git commit -m "test: add OTel-aware tests for Grafana driver"
```


#### Commits 24-26: Elastic Cloud driver with OTel

```bash
git commit -m "feat: implement Elastic Cloud driver with OTel instrumentation"
git commit -m "feat: extend search_traces to support Elastic Cloud with OTel"
git commit -m "test: add OTel-aware tests for Elastic Cloud driver"
```


#### Commits 27-30: OpenSearch driver with OTel

```bash
git commit -m "feat: implement OpenSearch driver with OTel spans"
git commit -m "feat: extend search_traces to support OpenSearch with OTel"
git commit -m "test: add OTel-aware tests for OpenSearch driver"
git commit -m "test: add cross-backend OTel correlation tests"
```


## OTel Integration Specifications

### Server Capability Declaration

```python
# In server.py
capabilities = {
    "otel": {
        "traces": True  # Declares support for notifications/otel/trace
    },
    "tools": {...},
    "resources": {...}
}
```


### TraceToken Handling

```python
# In tools/search_traces.py
async def search_traces(
    service: str,
    time_range: str,
    _meta: Optional[Dict[str, Any]] = None
) -> List[Trace]:
    """Search traces with OTel emission support."""
    
    # Extract traceToken if provided
    trace_token = _meta.get("traceToken") if _meta else None
    
    # Create parent span
    with tracer.start_as_current_span(
        "search_traces",
        attributes={
            "mcp.tool": "search_traces",
            "mcp.service": service,
            "mcp.time_range": time_range
        }
    ) as span:
        # Perform search with child spans
        results = await _perform_search(service, time_range)
        
        # Emit OTel notification if traceToken provided
        if trace_token:
            await emit_otel_notification(
                trace_token=trace_token,
                spans=get_current_spans()
            )
        
        return results
```


### OTel Configuration Schema

```yaml
# examples/otel-config.yaml
otel:
  traces:
    enabled: true
    emit_to_client: true  # Emit via notifications/otel/trace
    export_to_collector: false  # Don't duplicate to external collector
    service_name: "otel-query-server"
    attributes:
      deployment.environment: "production"
      service.version: "1.0.0"
  
  instrumentation:
    auto_instrument: true
    include_sql_queries: false  # Security consideration
    include_http_headers: false  # Security consideration
    max_span_attributes: 100
```


## Key Implementation Considerations

### Security \& Privacy

Following the GitHub discussion concerns:

- **Span Sanitization**: Implement configurable span attribute filtering
- **Sensitive Data**: Never include API keys, SQL queries, or PII in spans
- **Optional Emission**: OTel notification emission is opt-in via traceToken


### Performance

- **Conditional Tracing**: Only create detailed spans when traceToken is provided
- **Async Emission**: OTel notifications sent asynchronously to avoid blocking
- **Span Limiting**: Configurable limits on span count and attribute size


### Compatibility

- **Backward Compatibility**: Non-OTel clients work unchanged
- **Progressive Enhancement**: OTel features enhance but don't break basic functionality
- **Standards Compliance**: Follow OpenTelemetry semantic conventions


## Testing Strategy - Updated

### OTel-Specific Tests

```python
# tests/otel/test_notifications.py
async def test_otel_notification_emission():
    """Test that OTel notifications are emitted correctly."""
    
    # Mock MCP client expecting OTel notifications
    mock_client = Mock()
    
    # Call tool with traceToken
    await search_traces(
        service="test-service",
        time_range="1h",
        _meta={"traceToken": "test-token-123"}
    )
    
    # Verify notification was sent
    mock_client.send_notification.assert_called_once()
    notification = mock_client.send_notification.call_args[^0][^0]
    
    assert notification["method"] == "notifications/otel/trace"
    assert notification["params"]["traceToken"] == "test-token-123"
    assert "resourceSpans" in notification["params"]
```


### Integration Tests

```python
# tests/integration/test_otel_e2e.py
async def test_end_to_end_otel_correlation():
    """Test complete OTel trace correlation flow."""
    
    # Start with client span
    with tracer.start_as_current_span("client_operation") as client_span:
        # Call MCP tool with traceToken
        trace_token = f"client-{client_span.get_span_context().trace_id}"
        
        results = await search_traces(
            service="test-service",
            time_range="1h",
            _meta={"traceToken": trace_token}
        )
        
        # Verify correlation
        assert len(results) > 0
        # Additional correlation assertions...
```


## Release Strategy - Updated

### Version 0.1.0: Core functionality without OTel

- Basic MCP server with 5 tools
- Backend drivers for all 4 systems
- Standard MCP capabilities


### Version 0.2.0: OTel integration

- OpenTelemetry trace emission
- MCP OTel capability declaration
- TraceToken correlation support
- Security-focused span sanitization


### Version 0.3.0: Advanced OTel features

- Metrics emission (if MCP spec supports)
- Enhanced correlation capabilities
- Performance optimizations
- Enterprise security features


## Community Alignment

### MCP Specification Compliance

- Track the GitHub discussion closely
- Implement according to emerging spec
- Contribute back to the specification process
- Maintain compatibility with reference implementations


### OpenTelemetry Standards

- Follow OTel semantic conventions
- Use standard span attributes
- Implement proper context propagation
- Maintain compatibility with OTel ecosystem

This updated approach ensures our `otel-query-server` not only provides excellent observability querying capabilities but also serves as a reference implementation for the emerging MCP OpenTelemetry integration standards.

<div style="text-align: center">⁂</div>

[^1]: https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/269

