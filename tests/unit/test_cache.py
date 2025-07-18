"""Unit tests for caching layer."""

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from otel_query_server.cache import (
    Cache,
    CacheEntry,
    CacheStats,
    cache_key,
    get_cache,
    init_cache,
    set_cache,
)
from otel_query_server.config import CacheConfig
from otel_query_server.models import TimeRange, TraceSearchParams


class TestCacheStats:
    """Test CacheStats functionality."""
    
    def test_init(self):
        """Test stats initialization."""
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.errors == 0
    
    def test_total_requests(self):
        """Test total requests calculation."""
        stats = CacheStats()
        stats.hits = 10
        stats.misses = 5
        assert stats.total_requests == 15
    
    def test_hit_rate(self):
        """Test hit rate calculation."""
        stats = CacheStats()
        
        # No requests
        assert stats.hit_rate == 0.0
        
        # Some hits and misses
        stats.hits = 75
        stats.misses = 25
        assert stats.hit_rate == 0.75
        
        # All hits
        stats.hits = 100
        stats.misses = 0
        assert stats.hit_rate == 1.0
    
    def test_reset(self):
        """Test stats reset."""
        stats = CacheStats()
        stats.hits = 10
        stats.misses = 5
        stats.evictions = 3
        stats.errors = 1
        
        stats.reset()
        
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.errors == 0
    
    def test_to_dict(self):
        """Test stats dictionary conversion."""
        stats = CacheStats()
        stats.hits = 80
        stats.misses = 20
        stats.evictions = 5
        stats.errors = 2
        
        result = stats.to_dict()
        
        assert result["hits"] == 80
        assert result["misses"] == 20
        assert result["evictions"] == 5
        assert result["errors"] == 2
        assert result["total_requests"] == 100
        assert result["hit_rate"] == 0.8


class TestCacheEntry:
    """Test CacheEntry functionality."""
    
    def test_init(self):
        """Test entry initialization."""
        value = {"test": "data"}
        ttl = 300
        
        entry = CacheEntry(value, ttl)
        
        assert entry.value == value
        assert entry.ttl == ttl
        assert entry.access_count == 0
        assert entry.created_at > 0
        assert entry.last_accessed == entry.created_at
    
    def test_is_expired(self):
        """Test expiration check."""
        entry = CacheEntry("test", ttl=1)
        
        # Not expired initially
        assert not entry.is_expired
        
        # Expired after TTL
        time.sleep(1.1)
        assert entry.is_expired
    
    def test_access(self):
        """Test accessing entry."""
        value = {"test": "data"}
        entry = CacheEntry(value, ttl=300)
        
        # First access
        result = entry.access()
        assert result == value
        assert entry.access_count == 1
        assert entry.last_accessed > entry.created_at
        
        # Second access
        time.sleep(0.01)
        last_accessed = entry.last_accessed
        result = entry.access()
        assert result == value
        assert entry.access_count == 2
        assert entry.last_accessed > last_accessed


class TestCache:
    """Test Cache functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test cache configuration."""
        return CacheConfig(
            enabled=True,
            max_size=30,
            ttl_seconds=300,
            trace_ttl_seconds=600,
            log_ttl_seconds=300,
            metric_ttl_seconds=60
        )
    
    @pytest.fixture
    def cache(self, config):
        """Create test cache instance."""
        return Cache(config)
    
    def test_init(self, cache, config):
        """Test cache initialization."""
        assert cache.config == config
        assert cache.enabled is True
        assert isinstance(cache.stats, CacheStats)
        assert cache._trace_cache.maxsize == 10  # max_size // 3
        assert cache._log_cache.maxsize == 10
        assert cache._metric_cache.maxsize == 10
    
    def test_generate_key_with_dict(self):
        """Test key generation with dictionary."""
        params = {
            "service": "test-service",
            "limit": 100,
            "start_time": "2024-01-01T00:00:00Z"
        }
        
        key = Cache._generate_key("traces", params)
        
        assert key.startswith("traces:")
        assert len(key) > len("traces:")
        
        # Same params should generate same key
        key2 = Cache._generate_key("traces", params)
        assert key == key2
        
        # Different params should generate different key
        params["limit"] = 200
        key3 = Cache._generate_key("traces", params)
        assert key != key3
    
    def test_generate_key_with_model(self):
        """Test key generation with Pydantic model."""
        params = TraceSearchParams(
            time_range=TimeRange(
                start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end=datetime(2024, 1, 2, tzinfo=timezone.utc)
            ),
            service_name="test-service",
            limit=100
        )
        
        key = Cache._generate_key("traces", params)
        
        assert key.startswith("traces:")
        assert len(key) > len("traces:")
    
    def test_get_cache_for_prefix(self, cache):
        """Test getting cache by prefix."""
        assert cache._get_cache_for_prefix("traces") is cache._trace_cache
        assert cache._get_cache_for_prefix("logs") is cache._log_cache
        assert cache._get_cache_for_prefix("metrics") is cache._metric_cache
        assert cache._get_cache_for_prefix("unknown") is cache._trace_cache
    
    async def test_get_set(self, cache):
        """Test basic get and set operations."""
        key = "traces:test123"
        value = {"trace_id": "123", "spans": []}
        
        # Initially not in cache
        result = await cache.get(key)
        assert result is None
        assert cache.stats.misses == 1
        
        # Set value
        await cache.set(key, value)
        
        # Now in cache
        result = await cache.get(key)
        assert result == value
        assert cache.stats.hits == 1
    
    async def test_disabled_cache(self, config):
        """Test operations with disabled cache."""
        config.enabled = False
        cache = Cache(config)
        
        key = "traces:test"
        value = {"test": "data"}
        
        # Set should be no-op
        await cache.set(key, value)
        
        # Get should return None
        result = await cache.get(key)
        assert result is None
        
        # Stats should not be updated
        assert cache.stats.hits == 0
        assert cache.stats.misses == 0
    
    async def test_delete(self, cache):
        """Test delete operation."""
        key = "traces:test"
        value = {"test": "data"}
        
        # Set value
        await cache.set(key, value)
        
        # Delete existing key
        result = await cache.delete(key)
        assert result is True
        
        # Verify deleted
        result = await cache.get(key)
        assert result is None
        
        # Delete non-existing key
        result = await cache.delete(key)
        assert result is False
    
    async def test_clear_all(self, cache):
        """Test clearing all caches."""
        # Add values to different caches
        await cache.set("traces:1", {"trace": 1})
        await cache.set("logs:1", {"log": 1})
        await cache.set("metrics:1", {"metric": 1})
        
        # Clear all
        await cache.clear()
        
        # Verify all cleared
        assert await cache.get("traces:1") is None
        assert await cache.get("logs:1") is None
        assert await cache.get("metrics:1") is None
    
    async def test_clear_prefix(self, cache):
        """Test clearing specific cache."""
        # Add values to different caches
        await cache.set("traces:1", {"trace": 1})
        await cache.set("logs:1", {"log": 1})
        
        # Clear only traces
        await cache.clear("traces")
        
        # Verify only traces cleared
        assert await cache.get("traces:1") is None
        assert await cache.get("logs:1") == {"log": 1}
    
    async def test_eviction_tracking(self, cache):
        """Test eviction tracking."""
        # Fill trace cache to capacity
        for i in range(10):
            await cache.set(f"traces:{i}", {"value": i})
        
        assert cache.stats.evictions == 0
        
        # Adding one more should trigger eviction
        await cache.set("traces:10", {"value": 10})
        
        # cachetools handles eviction, so we track it
        assert cache.stats.evictions == 1
    
    async def test_error_handling(self, cache):
        """Test error handling in cache operations."""
        # Mock an error in get operation
        with patch.object(cache, "_get_cache_for_prefix", side_effect=Exception("Test error")):
            result = await cache.get("traces:test")
            assert result is None
            assert cache.stats.errors == 1
    
    def test_get_stats(self, cache):
        """Test getting cache statistics."""
        stats = cache.get_stats()
        
        assert stats["enabled"] is True
        assert "stats" in stats
        assert "sizes" in stats
        assert "max_sizes" in stats
        
        assert stats["sizes"]["traces"] == 0
        assert stats["max_sizes"]["traces"] == 10


class TestCacheDecorator:
    """Test cache_key decorator."""
    
    class MockService:
        """Mock service with cache."""
        
        def __init__(self, cache):
            self._cache = cache
        
        @cache_key("traces")
        async def search_traces(self, params):
            """Mock search method."""
            return {"result": "traces", "params": params}
    
    @pytest.fixture
    def cache_config(self):
        """Create test cache configuration."""
        return CacheConfig(enabled=True, max_size=10)
    
    @pytest.fixture
    def mock_cache(self, cache_config):
        """Create mock cache."""
        return Cache(cache_config)
    
    @pytest.fixture
    def service(self, mock_cache):
        """Create mock service."""
        return self.MockService(mock_cache)
    
    async def test_cache_decorator_miss_then_hit(self, service):
        """Test decorator with cache miss then hit."""
        params = {"service": "test"}
        
        # First call - cache miss
        result1 = await service.search_traces(params)
        assert result1["result"] == "traces"
        assert service._cache.stats.misses == 1
        assert service._cache.stats.hits == 0
        
        # Second call - cache hit
        result2 = await service.search_traces(params)
        assert result2 == result1
        assert service._cache.stats.misses == 1
        assert service._cache.stats.hits == 1
    
    async def test_cache_decorator_no_cache(self):
        """Test decorator without cache."""
        service = self.MockService(None)
        params = {"service": "test"}
        
        # Should work without cache
        result = await service.search_traces(params)
        assert result["result"] == "traces"


class TestGlobalCache:
    """Test global cache functions."""
    
    def test_get_set_cache(self):
        """Test global cache getter and setter."""
        # Initially None
        set_cache(None)
        assert get_cache() is None
        
        # Set cache
        config = CacheConfig()
        cache = Cache(config)
        set_cache(cache)
        
        # Get cache
        assert get_cache() is cache
    
    def test_init_cache(self):
        """Test cache initialization."""
        config = CacheConfig(enabled=True, max_size=100)
        
        cache = init_cache(config)
        
        assert cache is not None
        assert cache.config == config
        assert get_cache() is cache 