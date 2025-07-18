"""Pydantic models for OpenTelemetry Query Server."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class TimeRange(BaseModel):
    """Time range for queries."""
    
    start: datetime = Field(..., description="Start time of the range")
    end: datetime = Field(..., description="End time of the range")
    
    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: datetime, info) -> datetime:
        """Ensure end time is after start time."""
        if "start" in info.data and v <= info.data["start"]:
            raise ValueError("End time must be after start time")
        return v


class TraceStatus(str, Enum):
    """Trace status enumeration."""
    
    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


class SpanKind(str, Enum):
    """Span kind enumeration."""
    
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(BaseModel):
    """Span status information."""
    
    code: TraceStatus = Field(default=TraceStatus.UNSET)
    message: Optional[str] = Field(default=None)


class SpanEvent(BaseModel):
    """Event within a span."""
    
    name: str = Field(..., description="Event name")
    timestamp: datetime = Field(..., description="Event timestamp")
    attributes: Dict[str, Any] = Field(default_factory=dict)


class SpanLink(BaseModel):
    """Link to another span."""
    
    trace_id: str = Field(..., description="Linked trace ID")
    span_id: str = Field(..., description="Linked span ID")
    attributes: Dict[str, Any] = Field(default_factory=dict)


class Span(BaseModel):
    """Individual span within a trace."""
    
    trace_id: str = Field(..., description="Trace ID")
    span_id: str = Field(..., description="Span ID")
    parent_span_id: Optional[str] = Field(default=None)
    operation_name: str = Field(..., description="Operation name")
    service_name: str = Field(..., description="Service name")
    kind: SpanKind = Field(default=SpanKind.INTERNAL)
    start_time: datetime = Field(..., description="Span start time")
    end_time: datetime = Field(..., description="Span end time")
    duration_ns: int = Field(..., description="Duration in nanoseconds")
    status: SpanStatus = Field(default_factory=SpanStatus)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    events: List[SpanEvent] = Field(default_factory=list)
    links: List[SpanLink] = Field(default_factory=list)
    
    @field_validator("duration_ns")
    @classmethod
    def calculate_duration(cls, v: int, info) -> int:
        """Calculate duration from start and end times if not provided."""
        if v == 0 and "start_time" in info.data and "end_time" in info.data:
            duration = info.data["end_time"] - info.data["start_time"]
            return int(duration.total_seconds() * 1e9)
        return v


class Trace(BaseModel):
    """Distributed trace containing multiple spans."""
    
    trace_id: str = Field(..., description="Unique trace identifier")
    spans: List[Span] = Field(..., description="List of spans in the trace")
    start_time: datetime = Field(..., description="Trace start time")
    end_time: datetime = Field(..., description="Trace end time")
    duration_ms: float = Field(..., description="Total duration in milliseconds")
    service_names: List[str] = Field(..., description="Services involved in trace")
    
    @classmethod
    def from_spans(cls, trace_id: str, spans: List[Span]) -> "Trace":
        """Create a Trace from a list of spans."""
        if not spans:
            raise ValueError("Cannot create trace from empty span list")
        
        start_time = min(span.start_time for span in spans)
        end_time = max(span.end_time for span in spans)
        duration_ms = (end_time - start_time).total_seconds() * 1000
        service_names = list(set(span.service_name for span in spans))
        
        return cls(
            trace_id=trace_id,
            spans=spans,
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            service_names=service_names
        )


class LogLevel(str, Enum):
    """Log level enumeration."""
    
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"


class LogEntry(BaseModel):
    """Individual log entry."""
    
    timestamp: datetime = Field(..., description="Log timestamp")
    level: LogLevel = Field(..., description="Log level")
    message: str = Field(..., description="Log message")
    service_name: str = Field(..., description="Service that generated the log")
    trace_id: Optional[str] = Field(default=None)
    span_id: Optional[str] = Field(default=None)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    resource_attributes: Dict[str, Any] = Field(default_factory=dict)


class MetricType(str, Enum):
    """Metric type enumeration."""
    
    GAUGE = "gauge"
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class MetricDataPoint(BaseModel):
    """Single metric data point."""
    
    timestamp: datetime = Field(..., description="Data point timestamp")
    value: float = Field(..., description="Metric value")
    labels: Dict[str, str] = Field(default_factory=dict)


class Metric(BaseModel):
    """Metric time series data."""
    
    name: str = Field(..., description="Metric name")
    type: MetricType = Field(..., description="Metric type")
    unit: str = Field(default="", description="Metric unit")
    description: str = Field(default="", description="Metric description")
    service_name: str = Field(..., description="Service that reported the metric")
    data_points: List[MetricDataPoint] = Field(..., description="Time series data")


class ServiceHealth(BaseModel):
    """Service health status."""
    
    service_name: str = Field(..., description="Service name")
    status: str = Field(..., description="Health status")
    uptime_seconds: Optional[float] = Field(default=None)
    error_rate: Optional[float] = Field(default=None)
    latency_p99_ms: Optional[float] = Field(default=None)
    request_rate: Optional[float] = Field(default=None)
    last_seen: datetime = Field(..., description="Last time service was seen")
    attributes: Dict[str, Any] = Field(default_factory=dict)


# Query parameter models

class TraceSearchParams(BaseModel):
    """Parameters for trace search."""
    
    service_name: Optional[str] = Field(default=None)
    operation_name: Optional[str] = Field(default=None)
    trace_id: Optional[str] = Field(default=None)
    min_duration_ms: Optional[float] = Field(default=None)
    max_duration_ms: Optional[float] = Field(default=None)
    status: Optional[TraceStatus] = Field(default=None)
    time_range: TimeRange = Field(...)
    attributes: Dict[str, str] = Field(default_factory=dict)
    limit: int = Field(default=100, ge=1, le=1000)


class LogSearchParams(BaseModel):
    """Parameters for log search."""
    
    service_name: Optional[str] = Field(default=None)
    level: Optional[LogLevel] = Field(default=None)
    query: Optional[str] = Field(default=None, description="Full-text search query")
    trace_id: Optional[str] = Field(default=None)
    time_range: TimeRange = Field(...)
    attributes: Dict[str, str] = Field(default_factory=dict)
    limit: int = Field(default=1000, ge=1, le=10000)


class MetricQueryParams(BaseModel):
    """Parameters for metric queries."""
    
    metric_name: str = Field(..., description="Metric name pattern")
    service_name: Optional[str] = Field(default=None)
    time_range: TimeRange = Field(...)
    aggregation: Optional[str] = Field(default=None, pattern="^(avg|sum|min|max|count)$")
    group_by: List[str] = Field(default_factory=list)
    labels: Dict[str, str] = Field(default_factory=dict)


# Response models

class TraceSearchResponse(BaseModel):
    """Response for trace search."""
    
    traces: List[Trace] = Field(..., description="List of matching traces")
    total_count: int = Field(..., description="Total number of matches")
    has_more: bool = Field(default=False, description="Whether more results exist")


class LogSearchResponse(BaseModel):
    """Response for log search."""
    
    logs: List[LogEntry] = Field(..., description="List of matching logs")
    total_count: int = Field(..., description="Total number of matches")
    has_more: bool = Field(default=False, description="Whether more results exist")


class MetricQueryResponse(BaseModel):
    """Response for metric queries."""
    
    metrics: List[Metric] = Field(..., description="List of matching metrics")
    total_count: int = Field(..., description="Total number of matches")


class CorrelatedData(BaseModel):
    """Correlated trace and log data."""
    
    trace: Trace = Field(..., description="The trace")
    logs: List[LogEntry] = Field(..., description="Associated logs")
    correlation_score: float = Field(..., description="Correlation confidence score") 