"""Backend driver implementations for various observability platforms."""

from otel_query_server.drivers.base import BaseDriver, DriverRegistry
from otel_query_server.drivers.elastic_cloud import ElasticCloudDriver

# Register available drivers
DriverRegistry.register("elastic_cloud", ElasticCloudDriver)

__all__ = ["BaseDriver", "DriverRegistry", "ElasticCloudDriver"] 