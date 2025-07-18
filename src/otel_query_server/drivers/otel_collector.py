"""OpenTelemetry Collector driver implementation."""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import grpc
import structlog
from opentelemetry.proto.collector.logs.v1 import logs_service_pb2, logs_service_pb2_grpc
from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2, metrics_service_pb2_grpc
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2, trace_service_pb2_grpc
from opentelemetry.proto.common.v1 import common_pb2
from opentelemetry.proto.logs.v1 import logs_pb2
from opentelemetry.proto.metrics.v1 import metrics_pb2
from opentelemetry.proto.trace.v1 import trace_pb2

from otel_query_server.config import OTELCollectorConfig
from otel_query_server.drivers.base import (
    BaseDriver,
    BackendError,
    ConnectionError,
    QueryError,
    RetryableError,
)
from otel_query_server.models import (
    LogEntry,
    LogLevel,
    LogSearchParams,
    LogSearchResponse,
    Metric,
    MetricDataPoint,
    MetricQueryParams,
    MetricQueryResponse,
    ServiceHealth,
    Span,
    SpanKind,
    SpanStatus,
    TraceStatus,
    Trace,
    TraceSearchParams,
    TraceSearchResponse,
)

logger = structlog.get_logger(__name__)


class OTELCollectorDriver(BaseDriver):
    """Driver for OpenTelemetry Collector backend using OTLP gRPC."""
    
    # Driver metadata
    DRIVER_NAME = "otel_collector"
    DISPLAY_NAME = "OpenTelemetry Collector"
    DESCRIPTION = "Connect to OpenTelemetry Collector via OTLP gRPC protocol"
    VERSION = "1.0.0"
    AUTHOR = "OTEL Query Server Team"
    SUPPORTED_BACKENDS = ["OpenTelemetry Collector", "OTLP", "Jaeger", "Prometheus", "Loki"]
    
    def __init__(self, config: OTELCollectorConfig) -> None:
        """Initialize the OTEL Collector driver."""
        super().__init__(config)
        self.config: OTELCollectorConfig = config
        self.channel: Optional[grpc.aio.Channel] = None
        self.trace_client: Optional[trace_service_pb2_grpc.TraceServiceStub] = None
        self.metrics_client: Optional[metrics_service_pb2_grpc.MetricsServiceStub] = None
        self.logs_client: Optional[logs_service_pb2_grpc.LogsServiceStub] = None
        
        # Storage for received telemetry data (in-memory for demo)
        # In production, this would query a backend storage like Jaeger, Prometheus, etc.
        self._traces: List[Dict[str, Any]] = []
        self._logs: List[Dict[str, Any]] = []
        self._metrics: List[Dict[str, Any]] = []
        
    async def _connect(self) -> None:
        """Connect to the OTEL Collector via gRPC."""
        try:
            # Create channel options
            options = []
            
            # Add headers if configured
            if self.config.headers:
                metadata = [(k.lower(), v) for k, v in self.config.headers.items()]
                options.append(('grpc.default_metadata', metadata))
            
            # Configure compression
            if self.config.compression:
                options.append(('grpc.default_compression_algorithm', 
                              grpc.Compression.Gzip if self.config.compression == 'gzip' else grpc.Compression.NoCompression))
            
            # Create channel
            if self.config.insecure:
                self.channel = grpc.aio.insecure_channel(
                    self.config.endpoint,
                    options=options
                )
            else:
                # Load credentials for secure connection
                credentials = grpc.ssl_channel_credentials()
                self.channel = grpc.aio.secure_channel(
                    self.config.endpoint,
                    credentials,
                    options=options
                )
            
            # Create service stubs
            self.trace_client = trace_service_pb2_grpc.TraceServiceStub(self.channel)
            self.metrics_client = metrics_service_pb2_grpc.MetricsServiceStub(self.channel)
            self.logs_client = logs_service_pb2_grpc.LogsServiceStub(self.channel)
            
            # Test connection by sending empty requests
            try:
                # Set a short timeout for the connection test
                timeout = 5.0
                
                # Test trace service
                empty_trace_request = trace_service_pb2.ExportTraceServiceRequest()
                await self.trace_client.Export(empty_trace_request, timeout=timeout)
                
                self.logger.info("Connected to OTEL Collector", endpoint=self.config.endpoint)
            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.UNIMPLEMENTED:
                    # This is expected for some collectors
                    self.logger.info("Connected to OTEL Collector (export not implemented)", 
                                   endpoint=self.config.endpoint)
                elif e.code() == grpc.StatusCode.UNAVAILABLE:
                    raise ConnectionError(f"OTEL Collector unavailable at {self.config.endpoint}")
                else:
                    # Other errors might still indicate a working connection
                    self.logger.warning("Connection test returned error", 
                                      error=str(e), code=e.code())
            
        except Exception as e:
            raise ConnectionError(f"Failed to connect to OTEL Collector: {e}")
    
    async def _disconnect(self) -> None:
        """Disconnect from the OTEL Collector."""
        if self.channel:
            await self.channel.close()
            self.channel = None
            self.trace_client = None
            self.metrics_client = None
            self.logs_client = None
    
    async def search_traces(self, params: TraceSearchParams) -> TraceSearchResponse:
        """Search for traces.
        
        Note: OTEL Collector is primarily a data pipeline and doesn't store data.
        This implementation would need to be connected to a trace backend like Jaeger.
        For now, returning empty results as a placeholder.
        """
        async with self.ensure_connected():
            try:
                # In a real implementation, this would:
                # 1. Query the configured trace backend (Jaeger, Tempo, etc.)
                # 2. Convert the results to our Trace model
                # 3. Apply filtering based on params
                
                # For demo purposes, return empty results
                self.logger.info("Trace search not implemented for OTEL Collector",
                               hint="Connect to a trace backend like Jaeger")
                
                return TraceSearchResponse(
                    traces=[],
                    total_count=0,
                    has_more=False
                )
                
            except Exception as e:
                self.logger.error("Failed to search traces", error=str(e))
                raise QueryError(f"Failed to search traces: {e}")
    
    async def search_logs(self, params: LogSearchParams) -> LogSearchResponse:
        """Search for logs.
        
        Note: Similar to traces, logs would need to be queried from a backend.
        """
        async with self.ensure_connected():
            try:
                # For demo purposes, return empty results
                self.logger.info("Log search not implemented for OTEL Collector",
                               hint="Connect to a log backend like Loki")
                
                return LogSearchResponse(
                    logs=[],
                    total_count=0,
                    has_more=False
                )
                
            except Exception as e:
                self.logger.error("Failed to search logs", error=str(e))
                raise QueryError(f"Failed to search logs: {e}")
    
    async def query_metrics(self, params: MetricQueryParams) -> MetricQueryResponse:
        """Query metrics.
        
        Note: Metrics would need to be queried from a backend like Prometheus.
        """
        async with self.ensure_connected():
            try:
                # For demo purposes, return empty results
                self.logger.info("Metric query not implemented for OTEL Collector",
                               hint="Connect to a metrics backend like Prometheus")
                
                return MetricQueryResponse(
                    metrics=[],
                    has_more=False
                )
                
            except Exception as e:
                self.logger.error("Failed to query metrics", error=str(e))
                raise QueryError(f"Failed to query metrics: {e}")
    
    async def get_service_health(self, service_name: str) -> ServiceHealth:
        """Get health status for a service.
        
        This would typically query metrics to determine service health.
        """
        async with self.ensure_connected():
            try:
                # For demo purposes, return unknown status
                return ServiceHealth(
                    service_name=service_name,
                    status="UNKNOWN",
                    last_seen=datetime.now(timezone.utc),
                    attributes={
                        "message": "Service health requires connection to metrics backend"
                    }
                )
                
            except Exception as e:
                self.logger.error("Failed to get service health", error=str(e))
                return ServiceHealth(
                    service_name=service_name,
                    status="UNKNOWN",
                    last_seen=datetime.now(timezone.utc),
                    attributes={"error": str(e)}
                )
    
    # Additional methods for sending data to OTEL Collector (for testing)
    
    async def export_traces(self, traces: List[trace_pb2.TracesData]) -> None:
        """Export traces to the OTEL Collector."""
        if not self.trace_client:
            raise ConnectionError("Not connected to OTEL Collector")
        
        request = trace_service_pb2.ExportTraceServiceRequest()
        for trace_data in traces:
            request.resource_spans.extend(trace_data.resource_spans)
        
        try:
            response = await self.trace_client.Export(request)
            self.logger.debug("Exported traces", count=len(traces))
        except grpc.RpcError as e:
            self.logger.error("Failed to export traces", error=str(e))
            raise RetryableError(f"Failed to export traces: {e}")
    
    async def export_metrics(self, metrics: List[metrics_pb2.MetricsData]) -> None:
        """Export metrics to the OTEL Collector."""
        if not self.metrics_client:
            raise ConnectionError("Not connected to OTEL Collector")
        
        request = metrics_service_pb2.ExportMetricsServiceRequest()
        for metrics_data in metrics:
            request.resource_metrics.extend(metrics_data.resource_metrics)
        
        try:
            response = await self.metrics_client.Export(request)
            self.logger.debug("Exported metrics", count=len(metrics))
        except grpc.RpcError as e:
            self.logger.error("Failed to export metrics", error=str(e))
            raise RetryableError(f"Failed to export metrics: {e}")
    
    async def export_logs(self, logs: List[logs_pb2.LogsData]) -> None:
        """Export logs to the OTEL Collector."""
        if not self.logs_client:
            raise ConnectionError("Not connected to OTEL Collector")
        
        request = logs_service_pb2.ExportLogsServiceRequest()
        for logs_data in logs:
            request.resource_logs.extend(logs_data.resource_logs)
        
        try:
            response = await self.logs_client.Export(request)
            self.logger.debug("Exported logs", count=len(logs))
        except grpc.RpcError as e:
            self.logger.error("Failed to export logs", error=str(e))
            raise RetryableError(f"Failed to export logs: {e}")
    
    def _convert_otlp_span_kind(self, kind: trace_pb2.Span.SpanKind) -> SpanKind:
        """Convert OTLP span kind to our model."""
        kind_map = {
            trace_pb2.Span.SPAN_KIND_UNSPECIFIED: SpanKind.INTERNAL,
            trace_pb2.Span.SPAN_KIND_INTERNAL: SpanKind.INTERNAL,
            trace_pb2.Span.SPAN_KIND_SERVER: SpanKind.SERVER,
            trace_pb2.Span.SPAN_KIND_CLIENT: SpanKind.CLIENT,
            trace_pb2.Span.SPAN_KIND_PRODUCER: SpanKind.PRODUCER,
            trace_pb2.Span.SPAN_KIND_CONSUMER: SpanKind.CONSUMER,
        }
        return kind_map.get(kind, SpanKind.INTERNAL)
    
    def _convert_otlp_status(self, status: trace_pb2.Status) -> SpanStatus:
        """Convert OTLP status to our model."""
        if status.code == trace_pb2.Status.STATUS_CODE_OK:
            return SpanStatus(code=TraceStatus.OK)
        elif status.code == trace_pb2.Status.STATUS_CODE_ERROR:
            return SpanStatus(
                code=TraceStatus.ERROR,
                message=status.message if status.message else None
            )
        else:
            return SpanStatus(code=TraceStatus.UNSET)
    
    def _hex_to_string(self, hex_bytes: bytes) -> str:
        """Convert hex bytes to string representation."""
        return hex_bytes.hex()
    
    def _extract_attributes(self, attributes: List[common_pb2.KeyValue]) -> Dict[str, Any]:
        """Extract attributes from OTLP key-value pairs."""
        result = {}
        for attr in attributes:
            key = attr.key
            value = attr.value
            
            if value.HasField("string_value"):
                result[key] = value.string_value
            elif value.HasField("int_value"):
                result[key] = value.int_value
            elif value.HasField("double_value"):
                result[key] = value.double_value
            elif value.HasField("bool_value"):
                result[key] = value.bool_value
            elif value.HasField("array_value"):
                # Simplified array handling
                result[key] = [v for v in value.array_value.values]
            elif value.HasField("kvlist_value"):
                # Nested attributes
                result[key] = self._extract_attributes(value.kvlist_value.values)
        
        return result


# Note: This driver serves as a foundation for OTEL Collector integration.
# In a production environment, you would typically:
# 1. Configure the OTEL Collector to export to a storage backend
# 2. Query that backend (Jaeger for traces, Prometheus for metrics, etc.)
# 3. Or use the OTLP/HTTP endpoint if the collector exposes a query API 