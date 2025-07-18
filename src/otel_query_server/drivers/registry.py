"""Driver auto-discovery and registration utilities."""

import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Dict, List, Type

import structlog

from otel_query_server.drivers.base import BaseDriver, DriverRegistry

logger = structlog.get_logger(__name__)


def discover_drivers(package_path: Path) -> Dict[str, Type[BaseDriver]]:
    """Discover driver classes in a package.
    
    Args:
        package_path: Path to the package to scan
        
    Returns:
        Dictionary mapping driver names to driver classes
    """
    discovered = {}
    
    # Import the package
    package_name = "otel_query_server.drivers"
    
    # Walk through all modules in the package
    for importer, modname, ispkg in pkgutil.walk_packages(
        [str(package_path)], 
        prefix=f"{package_name}."
    ):
        if ispkg or modname.endswith((".base", ".registry", "__init__")):
            continue
            
        try:
            # Import the module
            module = importlib.import_module(modname)
            
            # Find all classes in the module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Check if it's a BaseDriver subclass (but not BaseDriver itself)
                if (issubclass(obj, BaseDriver) and 
                    obj is not BaseDriver and
                    obj.__module__ == modname):
                    
                    # Get driver name from class attribute or derive from class name
                    driver_name = getattr(obj, "DRIVER_NAME", None)
                    if not driver_name:
                        driver_name = obj.__name__.replace("Driver", "").lower()
                    
                    discovered[driver_name] = obj
                    logger.debug(
                        "Discovered driver",
                        driver_name=driver_name,
                        class_name=obj.__name__,
                        module=modname
                    )
                    
        except Exception as e:
            logger.warning(
                "Failed to import module during driver discovery",
                module=modname,
                error=str(e)
            )
    
    return discovered


def auto_register_drivers(package_path: Path = None) -> List[str]:
    """Automatically discover and register all drivers.
    
    Args:
        package_path: Path to drivers package. If None, uses default location.
        
    Returns:
        List of registered driver names
    """
    if package_path is None:
        # Get the drivers package location
        import otel_query_server.drivers
        package_path = Path(otel_query_server.drivers.__file__).parent
    
    # Discover drivers
    discovered = discover_drivers(package_path)
    
    # Register each discovered driver
    registered = []
    for driver_name, driver_class in discovered.items():
        try:
            # Skip if already registered
            if driver_name in DriverRegistry.list():
                logger.debug("Driver already registered", driver_name=driver_name)
                continue
                
            # Register the driver
            DriverRegistry.register(driver_name, driver_class)
            registered.append(driver_name)
            
        except Exception as e:
            logger.error(
                "Failed to register driver",
                driver_name=driver_name,
                error=str(e)
            )
    
    logger.info(
        "Auto-registration complete",
        discovered_count=len(discovered),
        registered_count=len(registered),
        registered_drivers=registered
    )
    
    return registered


def register_driver_by_name(driver_name: str, module_name: str = None) -> None:
    """Register a specific driver by name.
    
    Args:
        driver_name: Name of the driver to register
        module_name: Optional module name. If None, derives from driver_name.
        
    Raises:
        ImportError: If driver module cannot be imported
        ValueError: If driver class not found or invalid
    """
    if module_name is None:
        # Derive module name from driver name
        module_name = f"otel_query_server.drivers.{driver_name}"
    
    try:
        # Import the module
        module = importlib.import_module(module_name)
        
        # Find the driver class
        driver_class = None
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (issubclass(obj, BaseDriver) and 
                obj is not BaseDriver and
                obj.__module__ == module_name):
                
                # Check if this is the right driver
                class_driver_name = getattr(obj, "DRIVER_NAME", None)
                if class_driver_name == driver_name or not class_driver_name:
                    driver_class = obj
                    break
        
        if not driver_class:
            raise ValueError(f"No BaseDriver subclass found in {module_name}")
        
        # Register the driver
        DriverRegistry.register(driver_name, driver_class)
        
    except ImportError as e:
        raise ImportError(f"Failed to import driver module {module_name}: {e}")
    except Exception as e:
        raise ValueError(f"Failed to register driver {driver_name}: {e}") 