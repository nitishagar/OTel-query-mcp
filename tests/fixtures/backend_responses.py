"""Mock backend response fixtures."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from otel_query_server.models import (
    LogEntry,
    LogLevel,
    LogSearchResponse,
    Metric,
    MetricDataPoint,
    MetricQueryResponse,
    MetricType,
    ServiceHealth,
    Span,
    SpanKind,
    SpanStatus,
    Trace,
    TraceSearchResponse,
    TraceStatus,
)


class BackendResponseFixtures:
    """Fixtures for mock backend responses."""
    
    @staticmethod
    def create_trace_response(count: int = 5) -> TraceSearchResponse:
        """Create a mock trace search response."""
        traces = []
        base_time = datetime.now(timezone.utc)
        
        for i in range(count):
            spans = []
            trace_start = base_time - timedelta(minutes=i)
            
            # Root span
            root_span = Span(
                trace_id=f"trace{i:04d}",
                span_id=f"span{i:04d}-0",
                parent_span_id=None,
                operation_name="HTTP GET /api/endpoint",
                service_name="frontend",
                kind=SpanKind.SERVER,
                start_time=trace_start,
                end_time=trace_start + timedelta(milliseconds=150),
                duration_ns=150_000_000,
                status=SpanStatus(code=TraceStatus.OK if i % 3 != 0 else TraceStatus.ERROR),
                attributes={
                    "http.method": "GET",
                    "http.url": f"/api/endpoint?id={i}",
                    "http.status_code": 200 if i % 3 != 0 else 500,
                    "user.id": f"user{i % 10}",
                }
            )
            spans.append(root_span)
            
            # Database span
            db_span = Span(
                trace_id=f"trace{i:04d}",
                span_id=f"span{i:04d}-1",
                parent_span_id=f"span{i:04d}-0",
                operation_name="SELECT FROM users",
                service_name="database",
                kind=SpanKind.CLIENT,
                start_time=trace_start + timedelta(milliseconds=20),
                end_time=trace_start + timedelta(milliseconds=120),
                duration_ns=100_000_000,
                status=SpanStatus(code=TraceStatus.OK),
                attributes={
                    "db.type": "postgresql",
                    "db.statement": "SELECT * FROM users WHERE id = ?",
                    "db.rows_affected": 1,
                }
            )
            spans.append(db_span)
            
            # Cache span
            cache_span = Span(
                trace_id=f"trace{i:04d}",
                span_id=f"span{i:04d}-2",
                parent_span_id=f"span{i:04d}-0",
                operation_name="cache.get",
                service_name="cache",
                kind=SpanKind.CLIENT,
                start_time=trace_start + timedelta(milliseconds=5),
                end_time=trace_start + timedelta(milliseconds=15),
                duration_ns=10_000_000,
                status=SpanStatus(code=TraceStatus.OK),
                attributes={
                    "cache.type": "redis",
                    "cache.hit": i % 2 == 0,
                    "cache.key": f"user:{i % 10}",
                }
            )
            spans.append(cache_span)
            
            trace = Trace.from_spans(f"trace{i:04d}", spans)
            traces.append(trace)
        
        return TraceSearchResponse(
            traces=traces,
            total_count=count * 2,  # Simulate having more results
            has_more=count < 10
        )
    
    @staticmethod
    def create_log_response(count: int = 20) -> LogSearchResponse:
        """Create a mock log search response."""
        logs = []
        base_time = datetime.now(timezone.utc)
        levels = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARN, LogLevel.ERROR]
        services = ["frontend", "backend", "database", "cache"]
        
        for i in range(count):
            log = LogEntry(
                timestamp=base_time - timedelta(seconds=i),
                level=levels[i % len(levels)],
                message=f"Log message {i}: Processing request" if i % 4 != 3 else f"Error {i}: Request failed",
                service_name=services[i % len(services)],
                trace_id=f"trace{i:04d}" if i % 3 == 0 else None,
                span_id=f"span{i:04d}-0" if i % 3 == 0 else None,
                attributes={
                    "component": services[i % len(services)],
                    "request_id": f"req{i:04d}",
                    "user_id": f"user{i % 10}" if i % 2 == 0 else None,
                    "error": i % 4 == 3,
                }
            )
            logs.append(log)
        
        return LogSearchResponse(
            logs=logs,
            total_count=count * 5,  # Simulate having more results
            has_more=count < 100
        )
    
    @staticmethod
    def create_metric_response(count: int = 10) -> MetricQueryResponse:
        """Create a mock metric query response."""
        metrics = []
        base_time = datetime.now(timezone.utc)
        services = ["frontend", "backend", "database", "cache"]
        
        # HTTP request rate metric
        for service in services[:2]:  # Only frontend and backend
            data_points = []
            for i in range(24):  # 24 hours of data
                timestamp = base_time - timedelta(hours=23-i)
                value = 100 + (i * 10) + (hash(service) % 50)
                data_points.append(
                    MetricDataPoint(
                        timestamp=timestamp,
                        value=float(value),
                        labels={
                            "service": service,
                            "environment": "production",
                            "region": "us-east-1",
                        }
                    )
                )
            
            metric = Metric(
                name="http_requests_per_minute",
                type=MetricType.GAUGE,
                unit="requests/min",
                description="HTTP requests per minute",
                service_name=service,
                data_points=data_points
            )
            metrics.append(metric)
        
        # Error rate metric
        for service in services:
            data_points = []
            for i in range(24):  # 24 hours of data
                timestamp = base_time - timedelta(hours=23-i)
                value = 0.01 + (0.001 * (i % 10))  # 1-2% error rate
                data_points.append(
                    MetricDataPoint(
                        timestamp=timestamp,
                        value=value,
                        labels={
                            "service": service,
                            "environment": "production",
                        }
                    )
                )
            
            metric = Metric(
                name="error_rate",
                type=MetricType.GAUGE,
                unit="ratio",
                description="Error rate as a ratio of failed requests",
                service_name=service,
                data_points=data_points
            )
            metrics.append(metric)
        
        # Response time percentiles
        percentiles = ["p50", "p95", "p99"]
        for service in services[:2]:  # Only frontend and backend
            for percentile in percentiles:
                data_points = []
                base_value = {"p50": 50, "p95": 200, "p99": 500}[percentile]
                
                for i in range(24):  # 24 hours of data
                    timestamp = base_time - timedelta(hours=23-i)
                    value = base_value + (i * 5) + (hash(f"{service}{percentile}") % 20)
                    data_points.append(
                        MetricDataPoint(
                            timestamp=timestamp,
                            value=float(value),
                            labels={
                                "service": service,
                                "percentile": percentile,
                                "environment": "production",
                            }
                        )
                    )
                
                metric = Metric(
                    name="response_time_ms",
                    type=MetricType.GAUGE,
                    unit="milliseconds",
                    description=f"Response time {percentile}",
                    service_name=service,
                    data_points=data_points
                )
                metrics.append(metric)
        
        return MetricQueryResponse(
            metrics=metrics[:count],  # Return requested number
            total_count=len(metrics)
        )
    
    @staticmethod
    def create_service_health_response(service_name: str) -> ServiceHealth:
        """Create a mock service health response."""
        # Simulate different health states based on service name
        if "unhealthy" in service_name:
            status = "unhealthy"
            error_rate = 0.15  # 15% error rate
            latency_p99 = 2000.0  # 2 seconds
        elif "degraded" in service_name:
            status = "degraded"
            error_rate = 0.05  # 5% error rate
            latency_p99 = 800.0  # 800ms
        else:
            status = "healthy"
            error_rate = 0.01  # 1% error rate
            latency_p99 = 250.0  # 250ms
        
        return ServiceHealth(
            service_name=service_name,
            status=status,
            uptime_seconds=86400.0 * 7,  # 7 days
            error_rate=error_rate,
            latency_p99_ms=latency_p99,
            request_rate=100.0 + hash(service_name) % 500,  # 100-600 req/s
            last_seen=datetime.now(timezone.utc),
            attributes={
                "version": "1.2.3",
                "deployment": "production",
                "region": "us-east-1",
                "instances": 3,
            }
        )
    
    @staticmethod
    def create_error_response(error_type: str = "timeout") -> Dict[str, Any]:
        """Create a mock error response."""
        errors = {
            "timeout": {
                "error": "Query timeout",
                "message": "The query took too long to execute",
                "code": "TIMEOUT_ERROR",
                "details": {
                    "timeout_seconds": 30,
                    "elapsed_seconds": 31.5
                }
            },
            "connection": {
                "error": "Connection failed",
                "message": "Unable to connect to backend service",
                "code": "CONNECTION_ERROR",
                "details": {
                    "endpoint": "localhost:4317",
                    "attempts": 3
                }
            },
            "invalid_query": {
                "error": "Invalid query",
                "message": "The query parameters are invalid",
                "code": "INVALID_QUERY",
                "details": {
                    "field": "time_range",
                    "reason": "Start time is after end time"
                }
            },
            "rate_limit": {
                "error": "Rate limit exceeded",
                "message": "Too many requests",
                "code": "RATE_LIMIT_ERROR",
                "details": {
                    "limit": 100,
                    "window": "1m",
                    "retry_after": 30
                }
            }
        }
        
        return errors.get(error_type, {
            "error": "Unknown error",
            "message": "An unknown error occurred",
            "code": "UNKNOWN_ERROR"
        }) 