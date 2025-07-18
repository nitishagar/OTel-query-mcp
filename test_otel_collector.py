#!/usr/bin/env python3
"""Test the OTEL Query Server with OTEL Collector."""

import asyncio
import sys
from datetime import datetime, timedelta, timezone

# Add src to path
sys.path.insert(0, 'src')

from otel_query_server.config import load_config
from otel_query_server.drivers import DriverRegistry
from otel_query_server.models import TraceSearchParams, TimeRange, LogSearchParams


async def test_otel_collector_driver():
    """Test the OTEL Collector driver functionality."""
    print("Loading configuration...")
    config = load_config("config-otel-test.yaml")
    
    print("\nInitializing OTEL Collector driver...")
    driver_class = DriverRegistry.get("otel_collector")
    driver = driver_class(config.backends.otel_collector)
    
    try:
        # Initialize connection
        await driver.initialize()
        print("✅ Driver initialized!")
        
        # Note: The OTEL Collector is a data pipeline, not a storage backend
        # So these queries will return empty results unless connected to a backend
        
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
            print(f"✅ Trace search completed (found {trace_response.total_count} traces)")
            print("   Note: OTEL Collector doesn't store data - connect to a backend like Jaeger")
        except Exception as e:
            print(f"❌ Trace search failed: {e}")
        
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
            print(f"✅ Log search completed (found {log_response.total_count} logs)")
            print("   Note: OTEL Collector doesn't store data - connect to a backend like Loki")
        except Exception as e:
            print(f"❌ Log search failed: {e}")
        
        # Test service health
        print("\n📊 Testing service health...")
        try:
            health = await driver.get_service_health("example-service")
            print(f"✅ Service health: {health.status}")
            print("   Note: Service health requires connection to metrics backend")
        except Exception as e:
            print(f"❌ Service health check failed: {e}")
        
        print("\n📝 OTEL Collector Driver Info:")
        print("   - Connects via gRPC to OTEL Collector")
        print("   - Supports OTLP protocol for traces, metrics, and logs")
        print("   - Acts as a pipeline - requires backend storage for queries")
        print("   - Common backends: Jaeger (traces), Prometheus (metrics), Loki (logs)")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        print("\n💡 Make sure OTEL Collector is running on localhost:4317")
        print("   You can start it with:")
        print("   docker run -p 4317:4317 otel/opentelemetry-collector:latest")
        
    finally:
        # Close connection
        print("\nClosing driver...")
        await driver.close()
        print("✅ Driver closed")


if __name__ == "__main__":
    print("OTEL Query Server - OTEL Collector Driver Test")
    print("=" * 50)
    asyncio.run(test_otel_collector_driver()) 