"""Caching layer for OpenTelemetry Query Server."""

import asyncio
import hashlib
import json
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional, TypeVar, Union

import structlog
from cachetools import TTLCache
from pydantic import BaseModel

from otel_query_server.config import CacheConfig

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class CacheStats:
    """Statistics for cache performance."""
    
    def __init__(self) -> None:
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.errors = 0
    
    @property
    def total_requests(self) -> int:
        """Total number of cache requests."""
        return self.hits + self.misses
    
    @property
    def hit_rate(self) -> float:
        """Cache hit rate (0.0 to 1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests
    
    def reset(self) -> None:
        """Reset all statistics."""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.errors = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "errors": self.errors,
            "total_requests": self.total_requests,
            "hit_rate": self.hit_rate
        }


class CacheEntry:
    """Entry in the cache with metadata."""
    
    def __init__(self, value: Any, ttl: int) -> None:
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
        self.access_count = 0
        self.last_accessed = self.created_at
    
    @property
    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        return time.time() - self.created_at > self.ttl
    
    def access(self) -> Any:
        """Access the cached value and update metadata."""
        self.access_count += 1
        self.last_accessed = time.time()
        return self.value


class Cache:
    """LRU cache with TTL support."""
    
    def __init__(self, config: CacheConfig) -> None:
        """Initialize cache with configuration.
        
        Args:
            config: Cache configuration
        """
        self.config = config
        self.enabled = config.enabled
        self.stats = CacheStats()
        self.logger = logger.bind(component="cache")
        
        # Create separate caches for different data types with specific TTLs
        self._trace_cache: TTLCache = TTLCache(
            maxsize=config.max_size // 3,
            ttl=config.trace_ttl_seconds
        )
        self._log_cache: TTLCache = TTLCache(
            maxsize=config.max_size // 3,
            ttl=config.log_ttl_seconds
        )
        self._metric_cache: TTLCache = TTLCache(
            maxsize=config.max_size // 3,
            ttl=config.metric_ttl_seconds
        )
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
    
    @staticmethod
    def _generate_key(prefix: str, params: Union[Dict[str, Any], BaseModel]) -> str:
        """Generate a cache key from parameters.
        
        Args:
            prefix: Key prefix (e.g., "traces", "logs")
            params: Parameters to include in key
            
        Returns:
            Cache key string
        """
        if isinstance(params, BaseModel):
            # Convert Pydantic model to dict
            params_dict = params.model_dump(mode="json")
        else:
            params_dict = params
        
        # Sort keys for consistent hashing
        sorted_params = json.dumps(params_dict, sort_keys=True, default=str)
        
        # Create hash of parameters
        param_hash = hashlib.md5(sorted_params.encode()).hexdigest()
        
        return f"{prefix}:{param_hash}"
    
    def _get_cache_for_prefix(self, prefix: str) -> TTLCache:
        """Get the appropriate cache based on prefix.
        
        Args:
            prefix: Cache key prefix
            
        Returns:
            TTLCache instance
        """
        if prefix == "traces":
            return self._trace_cache
        elif prefix == "logs":
            return self._log_cache
        elif prefix == "metrics":
            return self._metric_cache
        else:
            # Default to trace cache
            return self._trace_cache
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        if not self.enabled:
            return None
        
        try:
            prefix = key.split(":")[0]
            cache = self._get_cache_for_prefix(prefix)
            
            async with self._lock:
                if key in cache:
                    value = cache[key]
                    self.stats.hits += 1
                    self.logger.debug("Cache hit", key=key)
                    return value
                else:
                    self.stats.misses += 1
                    self.logger.debug("Cache miss", key=key)
                    return None
        except Exception as e:
            self.stats.errors += 1
            self.logger.error("Cache get error", key=key, error=str(e))
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional TTL override
        """
        if not self.enabled:
            return
        
        try:
            prefix = key.split(":")[0]
            cache = self._get_cache_for_prefix(prefix)
            
            async with self._lock:
                # Check if we're at capacity and would trigger eviction
                if len(cache) >= cache.maxsize:
                    self.stats.evictions += 1
                
                cache[key] = value
                self.logger.debug("Cache set", key=key)
        except Exception as e:
            self.stats.errors += 1
            self.logger.error("Cache set error", key=key, error=str(e))
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key was deleted, False if not found
        """
        if not self.enabled:
            return False
        
        try:
            prefix = key.split(":")[0]
            cache = self._get_cache_for_prefix(prefix)
            
            async with self._lock:
                if key in cache:
                    del cache[key]
                    self.logger.debug("Cache delete", key=key)
                    return True
                return False
        except Exception as e:
            self.stats.errors += 1
            self.logger.error("Cache delete error", key=key, error=str(e))
            return False
    
    async def clear(self, prefix: Optional[str] = None) -> None:
        """Clear cache entries.
        
        Args:
            prefix: Optional prefix to clear specific cache type
        """
        try:
            async with self._lock:
                if prefix:
                    cache = self._get_cache_for_prefix(prefix)
                    cache.clear()
                    self.logger.info("Cache cleared", prefix=prefix)
                else:
                    # Clear all caches
                    self._trace_cache.clear()
                    self._log_cache.clear()
                    self._metric_cache.clear()
                    self.logger.info("All caches cleared")
        except Exception as e:
            self.stats.errors += 1
            self.logger.error("Cache clear error", prefix=prefix, error=str(e))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary of cache statistics
        """
        return {
            "enabled": self.enabled,
            "stats": self.stats.to_dict(),
            "sizes": {
                "traces": len(self._trace_cache),
                "logs": len(self._log_cache),
                "metrics": len(self._metric_cache)
            },
            "max_sizes": {
                "traces": self._trace_cache.maxsize,
                "logs": self._log_cache.maxsize,
                "metrics": self._metric_cache.maxsize
            }
        }


def cache_key(prefix: str) -> Callable:
    """Decorator to generate cache keys for methods.
    
    Args:
        prefix: Cache key prefix
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(self: Any, params: Any, *args: Any, **kwargs: Any) -> Any:
            # Generate cache key from parameters
            key = Cache._generate_key(prefix, params)
            
            # Check cache first
            if hasattr(self, "_cache") and self._cache:
                cached_value = await self._cache.get(key)
                if cached_value is not None:
                    return cached_value
            
            # Call original function
            result = await func(self, params, *args, **kwargs)
            
            # Store in cache
            if hasattr(self, "_cache") and self._cache and result is not None:
                await self._cache.set(key, result)
            
            return result
        
        return wrapper
    return decorator


# Global cache instance
_cache: Optional[Cache] = None


def get_cache() -> Optional[Cache]:
    """Get the global cache instance."""
    return _cache


def set_cache(cache: Optional[Cache]) -> None:
    """Set the global cache instance."""
    global _cache
    _cache = cache


def init_cache(config: CacheConfig) -> Cache:
    """Initialize the global cache.
    
    Args:
        config: Cache configuration
        
    Returns:
        Cache instance
    """
    cache = Cache(config)
    set_cache(cache)
    return cache 