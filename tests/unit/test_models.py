"""Unit tests for Pydantic models."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from otel_query_server.models import (
    CorrelatedData,
    LogEntry,
    LogLevel,
    LogSearchParams,
    Metric,
    MetricDataPoint,
    MetricQueryParams,
    MetricType,
    ServiceHealth,
    Span,
    SpanKind,
    SpanStatus,
    TimeRange,
    Trace,
    TraceSearchParams,
    TraceStatus,
)


class TestTimeRange:
    """Test TimeRange model."""
    
    def test_valid_time_range(self):
        """Test creating a valid time range."""
        start = datetime.now(timezone.utc)
        end = start + timedelta(hours=1)
        
        time_range = TimeRange(start=start, end=end)
        assert time_range.start == start
        assert time_range.end == end
    
    def test_invalid_time_range_end_before_start(self):
        """Test that end time must be after start time."""
        start = datetime.now(timezone.utc)
        end = start - timedelta(hours=1)
        
        with pytest.raises(ValidationError, match="End time must be after start time"):
            TimeRange(start=start, end=end)
    
    def test_equal_start_end_invalid(self):
        """Test that start and end cannot be equal."""
        time = datetime.now(timezone.utc)
        
        with pytest.raises(ValidationError, match="End time must be after start time"):
            TimeRange(start=time, end=time)


class TestSpan:
    """Test Span model."""
    
    def test_create_minimal_span(self):
        """Test creating a span with minimal required fields."""
        start = datetime.now(timezone.utc)
        end = start + timedelta(milliseconds=100)
        
        span = Span(
            trace_id="trace123",
            span_id="span456",
            operation_name="test-operation",
            service_name="test-service",
            start_time=start,
            end_time=end,
            duration_ns=100_000_000  # 100ms in nanoseconds
        )
        
        assert span.trace_id == "trace123"
        assert span.span_id == "span456"
        assert span.operation_name == "test-operation"
        assert span.service_name == "test-service"
        assert span.kind == SpanKind.INTERNAL  # default
        assert span.parent_span_id is None
    
    def test_span_duration_calculation(self):
        """Test automatic duration calculation from timestamps."""
        start = datetime.now(timezone.utc)
        end = start + timedelta(milliseconds=250)
        
        span = Span(
            trace_id="trace123",
            span_id="span456",
            operation_name="test-operation",
            service_name="test-service",
            start_time=start,
            end_time=end,
            duration_ns=0  # Should be calculated
        )
        
        # 250ms = 250,000,000 nanoseconds
        assert span.duration_ns == 250_000_000
    
    def test_span_with_all_fields(self):
        """Test creating a span with all optional fields."""
        start = datetime.now(timezone.utc)
        end = start + timedelta(milliseconds=100)
        
        span = Span(
            trace_id="trace123",
            span_id="span456",
            parent_span_id="parent789",
            operation_name="test-operation",
            service_name="test-service",
            kind=SpanKind.SERVER,
            start_time=start,
            end_time=end,
            duration_ns=100_000_000,
            status=SpanStatus(code=TraceStatus.ERROR, message="Test error"),
            attributes={"http.method": "GET", "http.status_code": 500},
            events=[],
            links=[]
        )
        
        assert span.parent_span_id == "parent789"
        assert span.kind == SpanKind.SERVER
        assert span.status.code == TraceStatus.ERROR
        assert span.status.message == "Test error"
        assert span.attributes["http.method"] == "GET"


class TestTrace:
    """Test Trace model."""
    
    def test_create_trace_from_spans(self):
        """Test creating a trace from a list of spans."""
        base_time = datetime.now(timezone.utc)
        
        spans = [
            Span(
                trace_id="trace123",
                span_id="span1",
                operation_name="operation1",
                service_name="service1",
                start_time=base_time,
                end_time=base_time + timedelta(milliseconds=50),
                duration_ns=50_000_000
            ),
            Span(
                trace_id="trace123",
                span_id="span2",
                operation_name="operation2",
                service_name="service2",
                start_time=base_time + timedelta(milliseconds=25),
                end_time=base_time + timedelta(milliseconds=100),
                duration_ns=75_000_000
            ),
        ]
        
        trace = Trace.from_spans("trace123", spans)
        
        assert trace.trace_id == "trace123"
        assert len(trace.spans) == 2
        assert trace.start_time == base_time
        assert trace.end_time == base_time + timedelta(milliseconds=100)
        assert trace.duration_ms == 100.0
        assert set(trace.service_names) == {"service1", "service2"}
    
    def test_create_trace_from_empty_spans(self):
        """Test that creating a trace from empty spans raises error."""
        with pytest.raises(ValueError, match="Cannot create trace from empty span list"):
            Trace.from_spans("trace123", [])


class TestLogEntry:
    """Test LogEntry model."""
    
    def test_create_minimal_log(self):
        """Test creating a log with minimal fields."""
        timestamp = datetime.now(timezone.utc)
        
        log = LogEntry(
            timestamp=timestamp,
            level=LogLevel.INFO,
            message="Test log message",
            service_name="test-service"
        )
        
        assert log.timestamp == timestamp
        assert log.level == LogLevel.INFO
        assert log.message == "Test log message"
        assert log.service_name == "test-service"
        assert log.trace_id is None
        assert log.span_id is None
    
    def test_log_with_trace_context(self):
        """Test creating a log with trace context."""
        log = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level=LogLevel.ERROR,
            message="Error occurred",
            service_name="test-service",
            trace_id="trace123",
            span_id="span456",
            attributes={"error.type": "NullPointerException"}
        )
        
        assert log.trace_id == "trace123"
        assert log.span_id == "span456"
        assert log.attributes["error.type"] == "NullPointerException"


class TestMetric:
    """Test Metric model."""
    
    def test_create_metric(self):
        """Test creating a metric with data points."""
        base_time = datetime.now(timezone.utc)
        
        data_points = [
            MetricDataPoint(
                timestamp=base_time,
                value=42.5,
                labels={"env": "prod", "region": "us-east-1"}
            ),
            MetricDataPoint(
                timestamp=base_time + timedelta(minutes=1),
                value=45.7,
                labels={"env": "prod", "region": "us-east-1"}
            ),
        ]
        
        metric = Metric(
            name="http_requests_total",
            type=MetricType.COUNTER,
            unit="requests",
            description="Total HTTP requests",
            service_name="test-service",
            data_points=data_points
        )
        
        assert metric.name == "http_requests_total"
        assert metric.type == MetricType.COUNTER
        assert metric.unit == "requests"
        assert len(metric.data_points) == 2
        assert metric.data_points[0].value == 42.5


class TestQueryParams:
    """Test query parameter models."""
    
    def test_trace_search_params_minimal(self):
        """Test minimal trace search parameters."""
        time_range = TimeRange(
            start=datetime.now(timezone.utc) - timedelta(hours=1),
            end=datetime.now(timezone.utc)
        )
        
        params = TraceSearchParams(time_range=time_range)
        
        assert params.time_range == time_range
        assert params.limit == 100  # default
        assert params.service_name is None
        assert params.operation_name is None
    
    def test_trace_search_params_full(self):
        """Test trace search with all parameters."""
        time_range = TimeRange(
            start=datetime.now(timezone.utc) - timedelta(hours=1),
            end=datetime.now(timezone.utc)
        )
        
        params = TraceSearchParams(
            service_name="test-service",
            operation_name="GET /api/users",
            trace_id="trace123",
            min_duration_ms=100,
            max_duration_ms=1000,
            status=TraceStatus.ERROR,
            time_range=time_range,
            attributes={"http.method": "GET"},
            limit=50
        )
        
        assert params.service_name == "test-service"
        assert params.operation_name == "GET /api/users"
        assert params.min_duration_ms == 100
        assert params.max_duration_ms == 1000
        assert params.status == TraceStatus.ERROR
        assert params.limit == 50
    
    def test_log_search_params(self):
        """Test log search parameters."""
        time_range = TimeRange(
            start=datetime.now(timezone.utc) - timedelta(hours=1),
            end=datetime.now(timezone.utc)
        )
        
        params = LogSearchParams(
            service_name="test-service",
            level=LogLevel.ERROR,
            query="exception",
            time_range=time_range,
            limit=500
        )
        
        assert params.service_name == "test-service"
        assert params.level == LogLevel.ERROR
        assert params.query == "exception"
        assert params.limit == 500
    
    def test_metric_query_params(self):
        """Test metric query parameters."""
        time_range = TimeRange(
            start=datetime.now(timezone.utc) - timedelta(hours=1),
            end=datetime.now(timezone.utc)
        )
        
        params = MetricQueryParams(
            metric_name="http_requests_*",
            service_name="test-service",
            time_range=time_range,
            aggregation="sum",
            group_by=["status_code"],
            labels={"env": "prod"}
        )
        
        assert params.metric_name == "http_requests_*"
        assert params.aggregation == "sum"
        assert params.group_by == ["status_code"]
        assert params.labels["env"] == "prod"
    
    def test_invalid_aggregation(self):
        """Test that invalid aggregation is rejected."""
        time_range = TimeRange(
            start=datetime.now(timezone.utc) - timedelta(hours=1),
            end=datetime.now(timezone.utc)
        )
        
        with pytest.raises(ValidationError):
            MetricQueryParams(
                metric_name="test_metric",
                time_range=time_range,
                aggregation="invalid"  # Should fail pattern validation
            )


class TestServiceHealth:
    """Test ServiceHealth model."""
    
    def test_service_health_minimal(self):
        """Test minimal service health."""
        health = ServiceHealth(
            service_name="test-service",
            status="healthy",
            last_seen=datetime.now(timezone.utc)
        )
        
        assert health.service_name == "test-service"
        assert health.status == "healthy"
        assert health.uptime_seconds is None
        assert health.error_rate is None
    
    def test_service_health_full(self):
        """Test service health with all metrics."""
        health = ServiceHealth(
            service_name="test-service",
            status="degraded",
            uptime_seconds=3600.0,
            error_rate=0.05,
            latency_p99_ms=250.5,
            request_rate=100.0,
            last_seen=datetime.now(timezone.utc),
            attributes={"version": "1.2.3", "region": "us-east-1"}
        )
        
        assert health.status == "degraded"
        assert health.uptime_seconds == 3600.0
        assert health.error_rate == 0.05
        assert health.latency_p99_ms == 250.5
        assert health.request_rate == 100.0
        assert health.attributes["version"] == "1.2.3" 