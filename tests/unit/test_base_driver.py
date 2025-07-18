"""Unit tests for base driver."""

import asyncio
from datetime import datetime, timezone
from typing import List
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
import structlog

from otel_query_server.config import BackendConfig
from otel_query_server.drivers.base import (
    BackendError,
    BaseDriver,
    ConnectionError,
    DriverRegistry,
    QueryError,
    RetryableError,
    TimeoutError,
)
from otel_query_server.models import (
    LogSearchParams,
    LogSearchResponse,
    MetricQueryParams,
    MetricQueryResponse,
    ServiceHealth,
    TimeRange,
    TraceSearchParams,
    TraceSearchResponse,
)


class MockDriver(BaseDriver):
    """Mock implementation of BaseDriver for testing."""
    
    def __init__(self, config: BackendConfig):
        super().__init__(config)
        self.connect_called = False
        self.disconnect_called = False
        self.search_traces_called = False
        self.search_logs_called = False
        self.query_metrics_called = False
        self.get_service_health_called = False
    
    async def _connect(self) -> None:
        self.connect_called = True
    
    async def _disconnect(self) -> None:
        self.disconnect_called = True
    
    async def search_traces(self, params: TraceSearchParams) -> TraceSearchResponse:
        self.search_traces_called = True
        return TraceSearchResponse(traces=[], total_count=0)
    
    async def search_logs(self, params: LogSearchParams) -> LogSearchResponse:
        self.search_logs_called = True
        return LogSearchResponse(logs=[], total_count=0)
    
    async def query_metrics(self, params: MetricQueryParams) -> MetricQueryResponse:
        self.query_metrics_called = True
        return MetricQueryResponse(metrics=[], total_count=0)
    
    async def get_service_health(self, service_name: str) -> ServiceHealth:
        self.get_service_health_called = True
        return ServiceHealth(
            service_name=service_name,
            status="healthy",
            last_seen=datetime.now(timezone.utc)
        )


class TestBaseDriver:
    """Test BaseDriver functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return BackendConfig(
            enabled=True,
            timeout_seconds=30,
            max_retries=3,
            retry_delay_seconds=0.1
        )
    
    @pytest.fixture
    def driver(self, config):
        """Create test driver instance."""
        return MockDriver(config)
    
    def test_driver_initialization(self, driver, config):
        """Test driver initialization."""
        assert driver.config == config
        assert driver.name == "mock"
        assert not driver.is_connected
        assert driver._lock is not None
    
    async def test_initialize_success(self, driver):
        """Test successful initialization."""
        assert not driver.is_connected
        assert not driver.connect_called
        
        await driver.initialize()
        
        assert driver.is_connected
        assert driver.connect_called
    
    async def test_initialize_already_connected(self, driver):
        """Test initialization when already connected."""
        # First initialization
        await driver.initialize()
        driver.connect_called = False
        
        # Second initialization should be no-op
        await driver.initialize()
        assert not driver.connect_called
        assert driver.is_connected
    
    async def test_initialize_failure(self, driver):
        """Test initialization failure."""
        async def failing_connect():
            raise Exception("Connection failed")
        
        driver._connect = failing_connect
        
        with pytest.raises(ConnectionError, match="Failed to connect to mock"):
            await driver.initialize()
        
        assert not driver.is_connected
    
    async def test_close_success(self, driver):
        """Test successful close."""
        await driver.initialize()
        assert driver.is_connected
        
        await driver.close()
        
        assert not driver.is_connected
        assert driver.disconnect_called
    
    async def test_close_not_connected(self, driver):
        """Test close when not connected."""
        assert not driver.is_connected
        
        await driver.close()
        
        assert not driver.disconnect_called
    
    async def test_close_error_handling(self, driver):
        """Test error handling during close."""
        await driver.initialize()
        
        async def failing_disconnect():
            raise Exception("Disconnect failed")
        
        driver._disconnect = failing_disconnect
        
        # Should not raise, just log error
        await driver.close()
        assert driver.is_connected  # Still marked as connected
    
    async def test_ensure_connected_context_manager(self, driver):
        """Test ensure_connected context manager."""
        assert not driver.is_connected
        
        async with driver.ensure_connected():
            assert driver.is_connected
            assert driver.connect_called
    
    async def test_ensure_connected_already_connected(self, driver):
        """Test ensure_connected when already connected."""
        await driver.initialize()
        driver.connect_called = False
        
        async with driver.ensure_connected():
            assert driver.is_connected
            assert not driver.connect_called  # Should not reconnect
    
    async def test_execute_with_retry_success(self, driver):
        """Test successful execution with retry."""
        async def test_func(value):
            return value * 2
        
        result = await driver.execute_with_retry(test_func, 5)
        assert result == 10
    
    async def test_execute_with_retry_retryable_error(self, driver):
        """Test retry on retryable error."""
        call_count = 0
        
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("Temporary error")
            return "success"
        
        result = await driver.execute_with_retry(test_func)
        assert result == "success"
        assert call_count == 3
    
    async def test_execute_with_retry_max_retries_exceeded(self, driver):
        """Test max retries exceeded."""
        call_count = 0
        
        async def test_func():
            nonlocal call_count
            call_count += 1
            raise RetryableError(f"Error {call_count}")
        
        with pytest.raises(RetryableError):
            await driver.execute_with_retry(test_func)
        
        assert call_count == driver.config.max_retries
    
    async def test_execute_with_retry_non_retryable_error(self, driver):
        """Test non-retryable error."""
        async def test_func():
            raise ValueError("Non-retryable error")
        
        with pytest.raises(ValueError):
            await driver.execute_with_retry(test_func)
    
    async def test_get_services_not_implemented(self, driver):
        """Test get_services default implementation."""
        with pytest.raises(NotImplementedError, match="mock does not support service discovery"):
            await driver.get_services()
    
    async def test_get_operations_not_implemented(self, driver):
        """Test get_operations default implementation."""
        with pytest.raises(NotImplementedError, match="mock does not support operation discovery"):
            await driver.get_operations("test-service")
    
    async def test_validate_connection_success(self, driver):
        """Test successful connection validation."""
        result = await driver.validate_connection()
        assert result is True
        assert driver.search_traces_called
    
    async def test_validate_connection_failure(self, driver):
        """Test failed connection validation."""
        async def failing_search(params):
            raise Exception("Search failed")
        
        driver.search_traces = failing_search
        
        result = await driver.validate_connection()
        assert result is False


class TestDriverRegistry:
    """Test DriverRegistry functionality."""
    
    def setup_method(self):
        """Clear registry before each test."""
        DriverRegistry._drivers.clear()
    
    def test_register_driver(self):
        """Test registering a driver."""
        DriverRegistry.register("test", MockDriver)
        assert "test" in DriverRegistry._drivers
        assert DriverRegistry._drivers["test"] == MockDriver
    
    def test_get_driver(self):
        """Test getting a registered driver."""
        DriverRegistry.register("test", MockDriver)
        driver_class = DriverRegistry.get("test")
        assert driver_class == MockDriver
    
    def test_get_driver_not_found(self):
        """Test getting non-existent driver."""
        with pytest.raises(KeyError, match="Driver 'nonexistent' not registered"):
            DriverRegistry.get("nonexistent")
    
    def test_list_drivers(self):
        """Test listing registered drivers."""
        assert DriverRegistry.list() == []
        
        DriverRegistry.register("driver1", MockDriver)
        DriverRegistry.register("driver2", MockDriver)
        
        drivers = DriverRegistry.list()
        assert len(drivers) == 2
        assert "driver1" in drivers
        assert "driver2" in drivers


class TestExceptions:
    """Test custom exception classes."""
    
    def test_backend_error(self):
        """Test BackendError."""
        error = BackendError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    def test_connection_error(self):
        """Test ConnectionError."""
        error = ConnectionError("Connection failed")
        assert str(error) == "Connection failed"
        assert isinstance(error, BackendError)
    
    def test_query_error(self):
        """Test QueryError."""
        error = QueryError("Query failed")
        assert str(error) == "Query failed"
        assert isinstance(error, BackendError)
    
    def test_timeout_error(self):
        """Test TimeoutError."""
        error = TimeoutError("Query timeout")
        assert str(error) == "Query timeout"
        assert isinstance(error, BackendError)
    
    def test_retryable_error(self):
        """Test RetryableError."""
        error = RetryableError("Temporary failure")
        assert str(error) == "Temporary failure"
        assert isinstance(error, BackendError) 