"""Pytest configuration and shared fixtures."""

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator

import pytest
import pytest_asyncio
from pydantic import BaseModel

from otel_query_server.cache import Cache
from otel_query_server.config import (
    BackendsConfig,
    CacheConfig,
    Config,
    OTELCollectorConfig,
    ServerConfig,
)
from otel_query_server.models import (
    LogEntry,
    LogLevel,
    Metric,
    MetricDataPoint,
    MetricType,
    ServiceHealth,
    Span,
    SpanKind,
    SpanStatus,
    TimeRange,
    Trace,
    TraceStatus,
)


# Configure asyncio for testing
@pytest.fixture(scope="session")
def event_loop_policy():
    """Set event loop policy for tests."""
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def test_config() -> Config:
    """Create a test configuration."""
    return Config(
        server=ServerConfig(
            name="test-server",
            version="1.0.0",
            description="Test server",
            log_level="DEBUG",
        ),
        cache=CacheConfig(
            enabled=True,
            max_size=100,
            ttl_seconds=60,
            trace_ttl_seconds=120,
            log_ttl_seconds=60,
            metric_ttl_seconds=30,
        ),
        backends=BackendsConfig(
            otel_collector=OTELCollectorConfig(
                endpoint="localhost:4317",
                insecure=True,
                enabled=True,
            )
        ),
    )


@pytest.fixture
def test_cache(test_config: Config) -> Cache:
    """Create a test cache instance."""
    return Cache(test_config.cache)


@pytest.fixture
def sample_time_range() -> TimeRange:
    """Create a sample time range."""
    now = datetime.now(timezone.utc)
    return TimeRange(
        start=now.replace(hour=0, minute=0, second=0, microsecond=0),
        end=now,
    )


@pytest.fixture
def sample_span() -> Span:
    """Create a sample span."""
    now = datetime.now(timezone.utc)
    return Span(
        trace_id="trace123",
        span_id="span456",
        parent_span_id="parent789",
        operation_name="test-operation",
        service_name="test-service",
        kind=SpanKind.SERVER,
        start_time=now,
        end_time=now,
        duration_ns=1000000,  # 1ms
        status=SpanStatus(code=TraceStatus.OK),
        attributes={"http.method": "GET", "http.status_code": 200},
    )


@pytest.fixture
def sample_trace(sample_span: Span) -> Trace:
    """Create a sample trace."""
    return Trace.from_spans("trace123", [sample_span])


@pytest.fixture
def sample_log_entry() -> LogEntry:
    """Create a sample log entry."""
    return LogEntry(
        timestamp=datetime.now(timezone.utc),
        level=LogLevel.INFO,
        message="Test log message",
        service_name="test-service",
        trace_id="trace123",
        span_id="span456",
        attributes={"component": "test"},
    )


@pytest.fixture
def sample_metric() -> Metric:
    """Create a sample metric."""
    now = datetime.now(timezone.utc)
    return Metric(
        name="test_metric",
        type=MetricType.GAUGE,
        unit="requests",
        description="Test metric",
        service_name="test-service",
        data_points=[
            MetricDataPoint(
                timestamp=now,
                value=42.0,
                labels={"env": "test"},
            )
        ],
    )


@pytest.fixture
def sample_service_health() -> ServiceHealth:
    """Create a sample service health."""
    return ServiceHealth(
        service_name="test-service",
        status="healthy",
        uptime_seconds=3600,
        error_rate=0.01,
        latency_p99_ms=100.0,
        request_rate=50.0,
        last_seen=datetime.now(timezone.utc),
        attributes={"version": "1.0.0"},
    )


# Test data generators
def generate_spans(count: int, trace_id: str = "trace123") -> list[Span]:
    """Generate multiple spans for testing."""
    spans = []
    base_time = datetime.now(timezone.utc)
    
    for i in range(count):
        span = Span(
            trace_id=trace_id,
            span_id=f"span{i}",
            parent_span_id=f"span{i-1}" if i > 0 else None,
            operation_name=f"operation-{i}",
            service_name=f"service-{i % 3}",  # Rotate between 3 services
            kind=SpanKind.SERVER if i % 2 == 0 else SpanKind.CLIENT,
            start_time=base_time,
            end_time=base_time,
            duration_ns=1000000 * (i + 1),  # Variable duration
            status=SpanStatus(code=TraceStatus.OK),
            attributes={"index": i},
        )
        spans.append(span)
        base_time = base_time.replace(microsecond=base_time.microsecond + 1000)
    
    return spans


def generate_logs(count: int) -> list[LogEntry]:
    """Generate multiple log entries for testing."""
    logs = []
    base_time = datetime.now(timezone.utc)
    levels = list(LogLevel)
    
    for i in range(count):
        log = LogEntry(
            timestamp=base_time,
            level=levels[i % len(levels)],
            message=f"Log message {i}",
            service_name=f"service-{i % 3}",
            trace_id=f"trace{i % 5}" if i % 2 == 0 else None,
            span_id=f"span{i}" if i % 2 == 0 else None,
            attributes={"index": i},
        )
        logs.append(log)
        base_time = base_time.replace(microsecond=base_time.microsecond + 1000)
    
    return logs


def generate_metrics(count: int) -> list[Metric]:
    """Generate multiple metrics for testing."""
    metrics = []
    base_time = datetime.now(timezone.utc)
    
    for i in range(count):
        data_points = []
        for j in range(5):  # 5 data points per metric
            data_points.append(
                MetricDataPoint(
                    timestamp=base_time,
                    value=float(i * 10 + j),
                    labels={"env": "test", "index": str(i)},
                )
            )
            base_time = base_time.replace(second=base_time.second + 1)
        
        metric = Metric(
            name=f"metric_{i}",
            type=MetricType.GAUGE if i % 2 == 0 else MetricType.COUNTER,
            unit="units",
            description=f"Test metric {i}",
            service_name=f"service-{i % 3}",
            data_points=data_points,
        )
        metrics.append(metric)
    
    return metrics


# Mock data fixtures
@pytest.fixture
def mock_traces() -> list[Trace]:
    """Create mock traces for testing."""
    traces = []
    for i in range(5):
        spans = generate_spans(3, trace_id=f"trace{i}")
        trace = Trace.from_spans(f"trace{i}", spans)
        traces.append(trace)
    return traces


@pytest.fixture
def mock_logs() -> list[LogEntry]:
    """Create mock logs for testing."""
    return generate_logs(20)


@pytest.fixture
def mock_metrics() -> list[Metric]:
    """Create mock metrics for testing."""
    return generate_metrics(10)


# Async test helpers
@pytest.fixture
async def async_test_timeout():
    """Provide a timeout for async tests."""
    return 5.0  # 5 seconds


# Environment setup
@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("OTEL_QUERY_SERVER__LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("OTEL_QUERY_TEST_MODE", "true")


# Temporary directory fixtures
@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    """Create a temporary config file."""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text("""
server:
  name: test-server
  version: 1.0.0
  log_level: DEBUG

cache:
  enabled: true
  max_size: 100

backends:
  otel_collector:
    endpoint: localhost:4317
    insecure: true
""")
    return config_file 