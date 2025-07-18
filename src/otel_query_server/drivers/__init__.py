"""Backend driver implementations for various observability platforms."""

from otel_query_server.drivers.base import BaseDriver, DriverRegistry
from otel_query_server.drivers.elastic_cloud import ElasticCloudDriver
from otel_query_server.drivers.otel_collector import OTELCollectorDriver

# Register available drivers
DriverRegistry.register("elastic_cloud", ElasticCloudDriver)
DriverRegistry.register("otel_collector", OTELCollectorDriver)

__all__ = ["BaseDriver", "DriverRegistry", "ElasticCloudDriver", "OTELCollectorDriver"] 