"""Test utilities for OpenTelemetry Query Server."""

import asyncio
import functools
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, TypeVar
from unittest.mock import AsyncMock, MagicMock

from otel_query_server.drivers.base import BaseDriver

T = TypeVar("T")


def async_test(timeout: float = 5.0):
    """Decorator for async tests with timeout.
    
    Args:
        timeout: Test timeout in seconds
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
        return wrapper
    return decorator


class MockAsyncIterator:
    """Mock async iterator for testing."""
    
    def __init__(self, items: List[Any]):
        self.items = items
        self.index = 0
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


class AsyncTimer:
    """Async context manager for timing operations."""
    
    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.duration: Optional[float] = None
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time


@asynccontextmanager
async def assert_async_raises(exception_class: type[Exception], match: Optional[str] = None):
    """Async context manager to assert exceptions in async code.
    
    Args:
        exception_class: Expected exception class
        match: Optional string to match in exception message
    """
    try:
        yield
    except exception_class as e:
        if match and match not in str(e):
            raise AssertionError(f"Exception message '{e}' does not contain '{match}'")
    else:
        raise AssertionError(f"Expected {exception_class.__name__} but no exception was raised")


class MockDriver(BaseDriver):
    """Mock driver for testing.
    
    This provides a complete mock implementation of BaseDriver
    that can be configured for different test scenarios.
    """
    
    def __init__(self, config: Any, name: str = "mock"):
        super().__init__(config)
        self._name = name
        self.connect_called = False
        self.disconnect_called = False
        self.search_traces_response = None
        self.search_logs_response = None
        self.query_metrics_response = None
        self.get_service_health_response = None
        self.should_fail = False
        self.failure_error = Exception("Mock failure")
    
    @property
    def name(self) -> str:
        return self._name
    
    async def _connect(self) -> None:
        self.connect_called = True
        if self.should_fail:
            raise self.failure_error
    
    async def _disconnect(self) -> None:
        self.disconnect_called = True
        if self.should_fail:
            raise self.failure_error
    
    async def search_traces(self, params):
        if self.should_fail:
            raise self.failure_error
        return self.search_traces_response
    
    async def search_logs(self, params):
        if self.should_fail:
            raise self.failure_error
        return self.search_logs_response
    
    async def query_metrics(self, params):
        if self.should_fail:
            raise self.failure_error
        return self.query_metrics_response
    
    async def get_service_health(self, service_name):
        if self.should_fail:
            raise self.failure_error
        return self.get_service_health_response


def create_mock_async_func(return_value: Any = None, side_effect: Any = None) -> AsyncMock:
    """Create a mock async function with proper async behavior.
    
    Args:
        return_value: Value to return from the mock
        side_effect: Side effect or exception to raise
        
    Returns:
        Configured AsyncMock
    """
    mock = AsyncMock()
    if return_value is not None:
        mock.return_value = return_value
    if side_effect is not None:
        mock.side_effect = side_effect
    return mock


async def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 1.0,
    interval: float = 0.01
) -> bool:
    """Wait for a condition to become true.
    
    Args:
        condition: Function that returns True when condition is met
        timeout: Maximum time to wait in seconds
        interval: Check interval in seconds
        
    Returns:
        True if condition was met, False if timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition():
            return True
        await asyncio.sleep(interval)
    return False


class AsyncBatchProcessor:
    """Helper for testing batch processing scenarios."""
    
    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size
        self.processed_items: List[Any] = []
    
    async def process_batch(self, items: List[Any]) -> List[Any]:
        """Process a batch of items."""
        results = []
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            # Simulate async processing
            await asyncio.sleep(0.01)
            results.extend(batch)
            self.processed_items.extend(batch)
        return results


def mock_backend_response(
    data: Any,
    delay: float = 0.0,
    error: Optional[Exception] = None
) -> Callable:
    """Create a mock backend response function.
    
    Args:
        data: Data to return
        delay: Simulated delay in seconds
        error: Optional error to raise
        
    Returns:
        Async function that returns the mock response
    """
    async def response_func(*args, **kwargs):
        if delay > 0:
            await asyncio.sleep(delay)
        if error:
            raise error
        return data
    
    return response_func


class ConcurrentTestHelper:
    """Helper for testing concurrent operations."""
    
    def __init__(self):
        self.active_tasks = 0
        self.max_concurrent = 0
        self.completed_tasks = 0
        self._lock = asyncio.Lock()
    
    async def track_task(self, coro):
        """Track concurrent execution of a coroutine."""
        async with self._lock:
            self.active_tasks += 1
            self.max_concurrent = max(self.max_concurrent, self.active_tasks)
        
        try:
            result = await coro
            return result
        finally:
            async with self._lock:
                self.active_tasks -= 1
                self.completed_tasks += 1
    
    async def run_concurrent(self, coros: List) -> List[Any]:
        """Run multiple coroutines concurrently and track execution."""
        tasks = [self.track_task(coro) for coro in coros]
        return await asyncio.gather(*tasks)


# Test data validation helpers
def assert_valid_trace(trace: Any) -> None:
    """Assert that a trace object is valid."""
    assert hasattr(trace, "trace_id")
    assert hasattr(trace, "spans")
    assert len(trace.spans) > 0
    assert hasattr(trace, "start_time")
    assert hasattr(trace, "end_time")
    assert hasattr(trace, "duration_ms")


def assert_valid_log(log: Any) -> None:
    """Assert that a log object is valid."""
    assert hasattr(log, "timestamp")
    assert hasattr(log, "level")
    assert hasattr(log, "message")
    assert hasattr(log, "service_name")


def assert_valid_metric(metric: Any) -> None:
    """Assert that a metric object is valid."""
    assert hasattr(metric, "name")
    assert hasattr(metric, "type")
    assert hasattr(metric, "service_name")
    assert hasattr(metric, "data_points")
    assert len(metric.data_points) > 0 