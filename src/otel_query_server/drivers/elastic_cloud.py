"""Elastic Cloud driver implementation."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import structlog
from elasticsearch import AsyncElasticsearch, AuthenticationException, ConnectionError as ESConnectionError
from elasticsearch.helpers import async_scan

from otel_query_server.config import ElasticCloudConfig
from otel_query_server.drivers.base import (
    BaseDriver,
    BackendError,
    ConnectionError,
    QueryError,
    RetryableError,
)
from otel_query_server.models import (
    LogEntry,
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


class ElasticCloudDriver(BaseDriver):
    """Driver for Elastic Cloud (Elasticsearch) backend."""
    
    def __init__(self, config: ElasticCloudConfig) -> None:
        """Initialize the Elastic Cloud driver."""
        super().__init__(config)
        self.config: ElasticCloudConfig = config
        self.client: Optional[AsyncElasticsearch] = None
        
    async def _connect(self) -> None:
        """Connect to Elastic Cloud."""
        try:
            # Build connection parameters
            kwargs: Dict[str, Any] = {
                "request_timeout": self.config.timeout_seconds,
                "verify_certs": getattr(self.config, "verify_certs", True),
            }
            
            # Configure authentication
            if self.config.api_key:
                kwargs["api_key"] = self.config.api_key
            elif self.config.username and self.config.password:
                kwargs["basic_auth"] = (self.config.username, self.config.password)
            
            # Configure hosts
            if self.config.cloud_id:
                kwargs["cloud_id"] = self.config.cloud_id
            elif self.config.elasticsearch_url:
                kwargs["hosts"] = [self.config.elasticsearch_url]
            else:
                raise ConnectionError("Either cloud_id or elasticsearch_url must be provided")
            
            # Add CA certs if provided
            if hasattr(self.config, "ca_certs") and self.config.ca_certs:
                kwargs["ca_certs"] = self.config.ca_certs
            
            # Create client
            self.client = AsyncElasticsearch(**kwargs)
            
            # Test connection
            info = await self.client.info()
            self.logger.info(
                "Connected to Elastic Cloud",
                cluster_name=info.get("cluster_name"),
                version=info.get("version", {}).get("number")
            )
            
        except AuthenticationException as e:
            raise ConnectionError(f"Authentication failed: {e}")
        except ESConnectionError as e:
            raise ConnectionError(f"Connection failed: {e}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Elastic Cloud: {e}")
    
    async def _disconnect(self) -> None:
        """Disconnect from Elastic Cloud."""
        if self.client:
            await self.client.close()
            self.client = None
    
    async def search_traces(self, params: TraceSearchParams) -> TraceSearchResponse:
        """Search for traces in Elastic APM."""
        async with self.ensure_connected():
            try:
                # Build query
                query = self._build_trace_query(params)
                
                # Search for transactions (root spans)
                index = "apm-*-transaction*"
                
                response = await self.client.search(
                    index=index,
                    body=query,
                    size=params.limit or 100
                )
                
                # Process results
                traces = []
                for hit in response["hits"]["hits"]:
                    trace = await self._build_trace_from_transaction(hit["_source"])
                    if trace:
                        traces.append(trace)
                
                return TraceSearchResponse(
                    traces=traces,
                    total_count=response["hits"]["total"]["value"],
                    has_more=response["hits"]["total"]["value"] > len(traces)
                )
                
            except Exception as e:
                self.logger.error("Failed to search traces", error=str(e))
                raise QueryError(f"Failed to search traces: {e}")
    
    async def search_logs(self, params: LogSearchParams) -> LogSearchResponse:
        """Search for logs in Elasticsearch."""
        async with self.ensure_connected():
            try:
                # Build query
                query = self._build_log_query(params)
                
                # Search in logs indices
                index = "logs-*,filebeat-*,logstash-*"
                
                response = await self.client.search(
                    index=index,
                    body=query,
                    size=params.limit or 100,
                    ignore_unavailable=True
                )
                
                # Process results
                logs = []
                for hit in response["hits"]["hits"]:
                    log = self._build_log_from_document(hit["_source"])
                    if log:
                        logs.append(log)
                
                return LogSearchResponse(
                    logs=logs,
                    total_count=response["hits"]["total"]["value"],
                    has_more=response["hits"]["total"]["value"] > len(logs)
                )
                
            except Exception as e:
                self.logger.error("Failed to search logs", error=str(e))
                raise QueryError(f"Failed to search logs: {e}")
    
    async def query_metrics(self, params: MetricQueryParams) -> MetricQueryResponse:
        """Query metrics from Elasticsearch."""
        async with self.ensure_connected():
            try:
                # Build aggregation query
                query = self._build_metric_query(params)
                
                # Search in metrics indices
                index = "metrics-*,metricbeat-*"
                
                response = await self.client.search(
                    index=index,
                    body=query,
                    size=0,  # We only need aggregations
                    ignore_unavailable=True
                )
                
                # Process aggregations
                metrics = self._process_metric_aggregations(
                    response.get("aggregations", {}),
                    params
                )
                
                return MetricQueryResponse(
                    metrics=metrics,
                    has_more=False
                )
                
            except Exception as e:
                self.logger.error("Failed to query metrics", error=str(e))
                raise QueryError(f"Failed to query metrics: {e}")
    
    async def get_service_health(self, service_name: str) -> ServiceHealth:
        """Get health status for a service."""
        async with self.ensure_connected():
            try:
                # Query for recent errors and response times
                now = datetime.now(timezone.utc)
                query = {
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"service.name": service_name}},
                                {"range": {
                                    "@timestamp": {
                                        "gte": "now-5m",
                                        "lte": "now"
                                    }
                                }}
                            ]
                        }
                    },
                    "aggs": {
                        "error_rate": {
                            "filter": {"term": {"event.outcome": "failure"}},
                            "aggs": {
                                "count": {"value_count": {"field": "event.outcome"}}
                            }
                        },
                        "total_requests": {
                            "value_count": {"field": "event.outcome"}
                        },
                        "avg_duration": {
                            "avg": {"field": "transaction.duration.us"}
                        }
                    }
                }
                
                response = await self.client.search(
                    index="apm-*-transaction*",
                    body=query,
                    size=0
                )
                
                aggs = response.get("aggregations", {})
                total = aggs.get("total_requests", {}).get("value", 0)
                errors = aggs.get("error_rate", {}).get("count", {}).get("value", 0)
                avg_duration = aggs.get("avg_duration", {}).get("value", 0)
                
                # Determine health status
                if total == 0:
                    status = "UNKNOWN"
                else:
                    error_rate = (errors / total) * 100 if total > 0 else 0
                    if error_rate > 10:
                        status = "UNHEALTHY"
                    elif error_rate > 5:
                        status = "DEGRADED"
                    else:
                        status = "HEALTHY"
                
                return ServiceHealth(
                    service_name=service_name,
                    status=status,
                    error_rate=error_rate if total > 0 else None,
                    latency_p99_ms=(avg_duration / 1000) if avg_duration else None,
                    last_seen=now
                )
                
            except Exception as e:
                self.logger.error("Failed to get service health", error=str(e))
                return ServiceHealth(
                    service_name=service_name,
                    status="UNKNOWN",
                    last_seen=datetime.now(timezone.utc),
                    attributes={"error": str(e)}
                )
    
    def _build_trace_query(self, params: TraceSearchParams) -> Dict[str, Any]:
        """Build Elasticsearch query for trace search."""
        must_clauses = []
        
        # Time range
        if params.time_range:
            must_clauses.append({
                "range": {
                    "@timestamp": {
                        "gte": params.time_range.start.isoformat(),
                        "lte": params.time_range.end.isoformat()
                    }
                }
            })
        
        # Service filter
        if params.service_name:
            must_clauses.append({"term": {"service.name": params.service_name}})
        
        # Operation filter
        if params.operation_name:
            must_clauses.append({"term": {"transaction.name": params.operation_name}})
        
        # Duration filter
        if params.min_duration_ms is not None:
            must_clauses.append({
                "range": {
                    "transaction.duration.us": {
                        "gte": params.min_duration_ms * 1000  # Convert to microseconds
                    }
                }
            })
        
        # Status filter
        if params.status == TraceStatus.ERROR:
            must_clauses.append({"term": {"event.outcome": "failure"}})
        
        # Attributes filter
        if params.attributes:
            for key, value in params.attributes.items():
                must_clauses.append({"term": {f"labels.{key}": value}})
        
        return {
            "query": {
                "bool": {
                    "must": must_clauses
                }
            },
            "sort": [
                {"@timestamp": {"order": "desc"}}
            ]
        }
    
    def _build_log_query(self, params: LogSearchParams) -> Dict[str, Any]:
        """Build Elasticsearch query for log search."""
        must_clauses = []
        
        # Time range
        if params.time_range:
            must_clauses.append({
                "range": {
                    "@timestamp": {
                        "gte": params.time_range.start.isoformat(),
                        "lte": params.time_range.end.isoformat()
                    }
                }
            })
        
        # Service filter
        if params.service_name:
            must_clauses.append({
                "bool": {
                    "should": [
                        {"term": {"service.name": params.service_name}},
                        {"term": {"fields.service": params.service_name}},
                        {"term": {"kubernetes.labels.app": params.service_name}}
                    ]
                }
            })
        
        # Level filter
        if params.level:
            must_clauses.append({
                "bool": {
                    "should": [
                        {"term": {"log.level": params.level.upper()}},
                        {"term": {"level": params.level.upper()}},
                        {"term": {"severity": params.level.upper()}}
                    ]
                }
            })
        
        # Search query
        if params.query:
            must_clauses.append({
                "multi_match": {
                    "query": params.query,
                    "fields": ["message", "log", "msg"],
                    "type": "phrase_prefix"
                }
            })
        
        # Trace ID filter
        if params.trace_id:
            must_clauses.append({
                "bool": {
                    "should": [
                        {"term": {"trace.id": params.trace_id}},
                        {"term": {"traceId": params.trace_id}}
                    ]
                }
            })
        
        return {
            "query": {
                "bool": {
                    "must": must_clauses
                }
            },
            "sort": [
                {"@timestamp": {"order": "desc"}}
            ]
        }
    
    def _build_metric_query(self, params: MetricQueryParams) -> Dict[str, Any]:
        """Build Elasticsearch query for metrics."""
        must_clauses = []
        
        # Time range
        if params.time_range:
            must_clauses.append({
                "range": {
                    "@timestamp": {
                        "gte": params.time_range.start.isoformat(),
                        "lte": params.time_range.end.isoformat()
                    }
                }
            })
        
        # Metric name filter
        if params.metric_name:
            must_clauses.append({
                "bool": {
                    "should": [
                        {"term": {"metricset.name": params.metric_name}},
                        {"term": {"prometheus.metrics.name": params.metric_name}},
                        {"wildcard": {"_doc_count": f"*{params.metric_name}*"}}
                    ]
                }
            })
        
        # Service filter
        if params.service_name:
            must_clauses.append({"term": {"service.name": params.service_name}})
        
        # Labels filter
        if params.labels:
            for key, value in params.labels.items():
                must_clauses.append({
                    "bool": {
                        "should": [
                            {"term": {f"labels.{key}": value}},
                            {"term": {f"prometheus.labels.{key}": value}}
                        ]
                    }
                })
        
        # Build aggregation
        interval = self._calculate_interval(params.time_range) if params.time_range else "1m"
        
        return {
            "query": {
                "bool": {
                    "must": must_clauses
                }
            },
            "aggs": {
                "metrics_over_time": {
                    "date_histogram": {
                        "field": "@timestamp",
                        "fixed_interval": interval,
                        "min_doc_count": 0
                    },
                    "aggs": {
                        "value": {
                            params.aggregation or "avg": {
                                "field": self._get_metric_value_field()
                            }
                        }
                    }
                }
            }
        }
    
    def _calculate_interval(self, time_range) -> str:
        """Calculate appropriate interval for time range."""
        if not time_range:
            return "1m"
        
        duration = time_range.end - time_range.start
        minutes = duration.total_seconds() / 60
        
        if minutes <= 60:
            return "1m"
        elif minutes <= 360:  # 6 hours
            return "5m"
        elif minutes <= 1440:  # 24 hours
            return "15m"
        elif minutes <= 10080:  # 7 days
            return "1h"
        else:
            return "1d"
    
    def _get_metric_value_field(self) -> str:
        """Get the field name for metric values."""
        # This would need to be more sophisticated in a real implementation
        return "system.cpu.total.pct"
    
    async def _build_trace_from_transaction(self, transaction: Dict[str, Any]) -> Optional[Trace]:
        """Build a Trace object from an Elasticsearch transaction document."""
        try:
            trace_id = transaction.get("trace", {}).get("id")
            if not trace_id:
                return None
            
            # Get all spans for this trace
            spans_query = {
                "query": {
                    "term": {"trace.id": trace_id}
                },
                "size": 1000,
                "sort": [{"@timestamp": {"order": "asc"}}]
            }
            
            response = await self.client.search(
                index="apm-*",
                body=spans_query
            )
            
            spans = []
            for hit in response["hits"]["hits"]:
                span = self._build_span_from_document(hit["_source"])
                if span:
                    spans.append(span)
            
            if not spans:
                return None
            
            # Calculate trace duration
            start_time = min(span.start_time for span in spans)
            end_time = max(span.end_time for span in spans)
            duration_ms = (end_time - start_time).total_seconds() * 1000
            
            return Trace(
                trace_id=trace_id,
                spans=spans,
                duration_ms=duration_ms,
                service_name=transaction.get("service", {}).get("name", "unknown"),
                operation_name=transaction.get("transaction", {}).get("name", "unknown"),
                start_time=start_time,
                status=self._get_trace_status(spans)
            )
            
        except Exception as e:
            self.logger.error("Failed to build trace", error=str(e))
            return None
    
    def _build_span_from_document(self, doc: Dict[str, Any]) -> Optional[Span]:
        """Build a Span object from an Elasticsearch document."""
        try:
            # Determine if this is a transaction or span
            is_transaction = "transaction" in doc
            
            if is_transaction:
                span_id = doc.get("transaction", {}).get("id")
                span_name = doc.get("transaction", {}).get("name")
                duration_us = doc.get("transaction", {}).get("duration", {}).get("us", 0)
                span_type = doc.get("transaction", {}).get("type")
                parent_id = None  # Transactions don't have parents in APM
                kind = SpanKind.SERVER
            else:
                span_id = doc.get("span", {}).get("id")
                span_name = doc.get("span", {}).get("name")
                duration_us = doc.get("span", {}).get("duration", {}).get("us", 0)
                span_type = doc.get("span", {}).get("type")
                parent_id = doc.get("parent", {}).get("id")
                kind = self._map_span_kind(span_type)
            
            if not span_id:
                return None
            
            # Parse timestamp
            timestamp_str = doc.get("@timestamp")
            if not timestamp_str:
                return None
            
            start_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            duration_ms = duration_us / 1000
            end_time = start_time + timedelta(milliseconds=duration_ms)
            
            # Get status
            outcome = doc.get("event", {}).get("outcome", "success")
            status = SpanStatus(
                code=TraceStatus.OK if outcome == "success" else TraceStatus.ERROR,
                message=doc.get("error", {}).get("message") if outcome != "success" else None
            )
            
            # Extract attributes
            attributes = {}
            
            # Add service attributes
            service = doc.get("service", {})
            if service:
                attributes["service.name"] = service.get("name")
                attributes["service.version"] = service.get("version")
            
            # Add HTTP attributes
            http = doc.get("http", {})
            if http:
                request = http.get("request", {})
                response = http.get("response", {})
                if request:
                    attributes["http.method"] = request.get("method")
                    attributes["http.url"] = request.get("url", {}).get("full")
                if response:
                    attributes["http.status_code"] = response.get("status_code")
            
            # Add custom labels
            labels = doc.get("labels", {})
            for key, value in labels.items():
                attributes[f"labels.{key}"] = value
            
            return Span(
                span_id=span_id,
                trace_id=doc.get("trace", {}).get("id"),
                parent_span_id=parent_id,
                operation_name=span_name or "unknown",
                kind=kind,
                start_time=start_time,
                end_time=end_time,
                duration_ns=int(duration_us * 1000),  # Convert microseconds to nanoseconds
                status=status,
                attributes=attributes,
                service_name=service.get("name", "unknown")
            )
            
        except Exception as e:
            self.logger.error("Failed to build span", error=str(e))
            return None
    
    def _build_log_from_document(self, doc: Dict[str, Any]) -> Optional[LogEntry]:
        """Build a LogEntry object from an Elasticsearch document."""
        try:
            # Parse timestamp
            timestamp_str = doc.get("@timestamp")
            if not timestamp_str:
                return None
            
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            
            # Get message
            message = (
                doc.get("message") or 
                doc.get("log") or 
                doc.get("msg") or 
                ""
            )
            
            # Get level
            level = (
                doc.get("log", {}).get("level") or
                doc.get("level") or
                doc.get("severity") or
                "INFO"
            ).upper()
            
            # Get service name
            service_name = (
                doc.get("service", {}).get("name") or
                doc.get("fields", {}).get("service") or
                doc.get("kubernetes", {}).get("labels", {}).get("app") or
                "unknown"
            )
            
            # Extract attributes
            attributes = {}
            
            # Add trace context if available
            trace_id = doc.get("trace", {}).get("id") or doc.get("traceId")
            if trace_id:
                attributes["trace_id"] = trace_id
            
            span_id = doc.get("span", {}).get("id") or doc.get("spanId")
            if span_id:
                attributes["span_id"] = span_id
            
            # Add other relevant fields
            if "error" in doc:
                attributes["error"] = doc["error"]
            
            # Add Kubernetes metadata if available
            k8s = doc.get("kubernetes", {})
            if k8s:
                attributes["k8s.pod"] = k8s.get("pod", {}).get("name")
                attributes["k8s.namespace"] = k8s.get("namespace")
                attributes["k8s.container"] = k8s.get("container", {}).get("name")
            
            return LogEntry(
                timestamp=timestamp,
                level=level,
                message=message,
                service_name=service_name,
                trace_id=trace_id,
                span_id=span_id,
                attributes=attributes
            )
            
        except Exception as e:
            self.logger.error("Failed to build log entry", error=str(e))
            return None
    
    def _process_metric_aggregations(
        self, 
        aggregations: Dict[str, Any], 
        params: MetricQueryParams
    ) -> List[Metric]:
        """Process metric aggregations from Elasticsearch."""
        metrics = []
        
        time_buckets = aggregations.get("metrics_over_time", {}).get("buckets", [])
        if not time_buckets:
            return metrics
        
        # Create metric object
        data_points = []
        for bucket in time_buckets:
            timestamp = datetime.fromisoformat(
                bucket["key_as_string"].replace("Z", "+00:00")
            )
            value = bucket.get("value", {}).get("value", 0)
            
            data_points.append(MetricDataPoint(
                timestamp=timestamp,
                value=value
            ))
        
        metric = Metric(
            name=params.metric_name or "unknown",
            labels=params.labels or {},
            data_points=data_points,
            unit=params.unit,
            description=None
        )
        
        metrics.append(metric)
        return metrics
    
    def _map_span_kind(self, span_type: Optional[str]) -> SpanKind:
        """Map Elastic APM span type to SpanKind."""
        if not span_type:
            return SpanKind.INTERNAL
        
        span_type = span_type.lower()
        
        if span_type in ["request", "http", "grpc"]:
            return SpanKind.SERVER
        elif span_type in ["external", "http_client", "db"]:
            return SpanKind.CLIENT
        elif span_type in ["producer", "messaging.send"]:
            return SpanKind.PRODUCER
        elif span_type in ["consumer", "messaging.receive"]:
            return SpanKind.CONSUMER
        else:
            return SpanKind.INTERNAL
    
    def _get_trace_status(self, spans: List[Span]) -> SpanStatus:
        """Determine overall trace status from spans."""
        for span in spans:
            if span.status.code == TraceStatus.ERROR:
                return SpanStatus(
                    code=TraceStatus.ERROR,
                    message="Trace contains errors"
                )
        
        return SpanStatus(code=TraceStatus.OK) 