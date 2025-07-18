#!/usr/bin/env python3
"""Test the OTEL Query Server with Elastic Cloud."""

import asyncio
import sys
from datetime import datetime, timedelta, timezone

# Add src to path
sys.path.insert(0, 'src')

from otel_query_server.config import load_config
from otel_query_server.drivers import DriverRegistry
from otel_query_server.models import TraceSearchParams, TimeRange, LogSearchParams


async def test_elastic_driver():
    """Test the Elastic Cloud driver functionality."""
    print("Loading configuration...")
    config = load_config("config-elastic-test.yaml")
    
    print("\nInitializing Elastic Cloud driver...")
    driver_class = DriverRegistry.get("elastic_cloud")
    driver = driver_class(config.backends.elastic_cloud)
    
    try:
        # Initialize connection
        await driver.initialize()
        print("✅ Driver connected successfully!")
        
        # Test trace search
        print("\n📊 Testing trace search...")
        now = datetime.now(timezone.utc)
        trace_params = TraceSearchParams(
            time_range=TimeRange(
                start=now - timedelta(hours=24),
                end=now
            ),
            limit=5
        )
        
        try:
            trace_response = await driver.search_traces(trace_params)
            print(f"✅ Found {trace_response.total_count} traces")
            if trace_response.traces:
                print(f"   First trace ID: {trace_response.traces[0].trace_id}")
        except Exception as e:
            print(f"⚠️  Trace search failed: {e}")
        
        # Test log search
        print("\n📊 Testing log search...")
        log_params = LogSearchParams(
            time_range=TimeRange(
                start=now - timedelta(hours=1),
                end=now
            ),
            limit=10
        )
        
        try:
            log_response = await driver.search_logs(log_params)
            print(f"✅ Found {log_response.total_count} logs")
            if log_response.logs:
                print(f"   First log: {log_response.logs[0].message[:50]}...")
        except Exception as e:
            print(f"⚠️  Log search failed: {e}")
        
        # Test service health
        print("\n📊 Testing service health...")
        try:
            # You might need to adjust this service name
            health = await driver.get_service_health("example-service")
            print(f"✅ Service health: {health.status}")
            print(f"   Error rate: {health.error_rate}%")
            print(f"   Latency P99: {health.latency_p99_ms}ms")
        except Exception as e:
            print(f"⚠️  Service health check failed: {e}")
        
    finally:
        # Close connection
        print("\nClosing driver...")
        await driver.close()
        print("✅ Driver closed")


if __name__ == "__main__":
    print("OTEL Query Server - Elastic Cloud Driver Test")
    print("=" * 50)
    asyncio.run(test_elastic_driver()) 