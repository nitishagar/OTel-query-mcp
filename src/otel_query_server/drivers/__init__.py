"""Backend driver implementations for various observability platforms."""

from otel_query_server.drivers.base import BaseDriver, DriverRegistry, DriverMetadata, DriverInfo
from otel_query_server.drivers.registry import auto_register_drivers, register_driver_by_name

# Auto-register all available drivers
registered_drivers = auto_register_drivers()

# Export commonly used classes
__all__ = [
    "BaseDriver", 
    "DriverRegistry", 
    "DriverMetadata",
    "DriverInfo",
    "auto_register_drivers",
    "register_driver_by_name",
] 