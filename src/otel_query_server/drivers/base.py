"""Base driver interface for backend implementations."""

import asyncio
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncContextManager, Dict, List, Optional, Type, TypeVar

import structlog
from pydantic import BaseModel

from otel_query_server.config import BackendConfig
from otel_query_server.models import (
    LogEntry,
    LogSearchParams,
    LogSearchResponse,
    Metric,
    MetricQueryParams,
    MetricQueryResponse,
    ServiceHealth,
    Trace,
    TraceSearchParams,
    TraceSearchResponse,
)

# Type variable for configuration
TConfig = TypeVar("TConfig", bound=BackendConfig)

logger = structlog.get_logger(__name__)


class BackendError(Exception):
    """Base exception for backend errors."""
    pass


class ConnectionError(BackendError):
    """Error connecting to backend."""
    pass


class QueryError(BackendError):
    """Error executing query."""
    pass


class TimeoutError(BackendError):
    """Query timeout error."""
    pass


class RetryableError(BackendError):
    """Error that can be retried."""
    pass


class BaseDriver(ABC):
    """Abstract base class for backend drivers."""
    
    def __init__(self, config: BackendConfig) -> None:
        """Initialize the driver with configuration.
        
        Args:
            config: Backend-specific configuration
        """
        self.config = config
        self.logger = logger.bind(driver=self.__class__.__name__)
        self._connected = False
        self._lock = asyncio.Lock()
    
    @property
    def name(self) -> str:
        """Get the driver name."""
        return self.__class__.__name__.replace("Driver", "").lower()
    
    @property
    def is_connected(self) -> bool:
        """Check if driver is connected."""
        return self._connected
    
    async def initialize(self) -> None:
        """Initialize the driver (connect to backend)."""
        async with self._lock:
            if self._connected:
                return
            
            self.logger.info("Initializing driver")
            try:
                await self._connect()
                self._connected = True
                self.logger.info("Driver initialized successfully")
            except Exception as e:
                self.logger.error("Failed to initialize driver", error=str(e))
                raise ConnectionError(f"Failed to connect to {self.name}: {e}")
    
    async def close(self) -> None:
        """Close the driver connection."""
        async with self._lock:
            if not self._connected:
                return
            
            self.logger.info("Closing driver")
            try:
                await self._disconnect()
                self._connected = False
                self.logger.info("Driver closed successfully")
            except Exception as e:
                self.logger.error("Error closing driver", error=str(e))
    
    @asynccontextmanager
    async def ensure_connected(self) -> AsyncContextManager[None]:
        """Context manager to ensure driver is connected."""
        if not self._connected:
            await self.initialize()
        yield
    
    async def execute_with_retry(
        self,
        func: Any,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """Execute a function with retry logic.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result from func
            
        Raises:
            BackendError: If all retries fail
        """
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                return await func(*args, **kwargs)
            except RetryableError as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay_seconds * (2 ** attempt)
                    self.logger.warning(
                        "Retryable error, retrying",
                        attempt=attempt + 1,
                        max_attempts=self.config.max_retries,
                        delay=delay,
                        error=str(e)
                    )
                    await asyncio.sleep(delay)
                else:
                    self.logger.error("Max retries exceeded", error=str(e))
            except Exception as e:
                # Non-retryable error
                self.logger.error("Non-retryable error", error=str(e))
                raise
        
        # All retries failed
        raise last_error or BackendError("All retries failed")
    
    # Abstract methods that must be implemented by subclasses
    
    @abstractmethod
    async def _connect(self) -> None:
        """Connect to the backend.
        
        This method should establish connection to the backend service.
        """
        pass
    
    @abstractmethod
    async def _disconnect(self) -> None:
        """Disconnect from the backend.
        
        This method should close any open connections.
        """
        pass
    
    @abstractmethod
    async def search_traces(self, params: TraceSearchParams) -> TraceSearchResponse:
        """Search for traces.
        
        Args:
            params: Search parameters
            
        Returns:
            TraceSearchResponse containing matching traces
        """
        pass
    
    @abstractmethod
    async def search_logs(self, params: LogSearchParams) -> LogSearchResponse:
        """Search for logs.
        
        Args:
            params: Search parameters
            
        Returns:
            LogSearchResponse containing matching logs
        """
        pass
    
    @abstractmethod
    async def query_metrics(self, params: MetricQueryParams) -> MetricQueryResponse:
        """Query metrics.
        
        Args:
            params: Query parameters
            
        Returns:
            MetricQueryResponse containing matching metrics
        """
        pass
    
    @abstractmethod
    async def get_service_health(self, service_name: str) -> ServiceHealth:
        """Get health status for a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            ServiceHealth information
        """
        pass
    
    # Optional methods with default implementations
    
    async def get_services(self) -> List[str]:
        """Get list of available services.
        
        Returns:
            List of service names
        """
        # Default implementation - subclasses can override
        raise NotImplementedError(f"{self.name} does not support service discovery")
    
    async def get_operations(self, service_name: str) -> List[str]:
        """Get list of operations for a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            List of operation names
        """
        # Default implementation - subclasses can override
        raise NotImplementedError(f"{self.name} does not support operation discovery")
    
    async def validate_connection(self) -> bool:
        """Validate the backend connection.
        
        Returns:
            True if connection is valid, False otherwise
        """
        try:
            # Try a simple query to validate connection
            from datetime import timedelta
            from otel_query_server.models import TimeRange
            now = datetime.now()
            params = TraceSearchParams(
                time_range=TimeRange(
                    start=now - timedelta(minutes=1),
                    end=now
                ),
                limit=1
            )
            await self.search_traces(params)
            return True
        except Exception:
            return False


class DriverRegistry:
    """Registry for backend drivers."""
    
    _drivers: Dict[str, Type[BaseDriver]] = {}
    
    @classmethod
    def register(cls, name: str, driver_class: Type[BaseDriver]) -> None:
        """Register a driver class.
        
        Args:
            name: Driver name
            driver_class: Driver class
        """
        cls._drivers[name] = driver_class
    
    @classmethod
    def get(cls, name: str) -> Type[BaseDriver]:
        """Get a driver class by name.
        
        Args:
            name: Driver name
            
        Returns:
            Driver class
            
        Raises:
            KeyError: If driver not found
        """
        if name not in cls._drivers:
            raise KeyError(f"Driver '{name}' not registered")
        return cls._drivers[name]
    
    @classmethod
    def list(cls) -> List[str]:
        """List registered driver names.
        
        Returns:
            List of driver names
        """
        return list(cls._drivers.keys()) 