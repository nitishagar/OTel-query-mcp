#!/usr/bin/env python3
"""Test the improved driver registry functionality."""

import sys
sys.path.insert(0, 'src')

from otel_query_server.drivers import DriverRegistry


def test_driver_registry():
    """Test driver registry functionality."""
    print("Driver Registry Test")
    print("=" * 50)
    
    # List all registered drivers
    print("\n📋 Registered Drivers:")
    drivers = DriverRegistry.list()
    print(f"   Total: {len(drivers)}")
    for driver_name in drivers:
        print(f"   - {driver_name}")
    
    # Get detailed info for each driver
    print("\n📊 Driver Details:")
    drivers_info = DriverRegistry.list_with_info()
    
    for name, metadata in drivers_info.items():
        print(f"\n   {name}:")
        print(f"      Display Name: {metadata.display_name}")
        print(f"      Description: {metadata.description}")
        print(f"      Version: {metadata.version}")
        print(f"      Author: {metadata.author}")
        print(f"      Supported Backends: {', '.join(metadata.supported_backends)}")
        print(f"      Capabilities:")
        for cap, enabled in metadata.capabilities.items():
            status = "✅" if enabled else "❌"
            print(f"         - {cap}: {status}")
    
    # Test getting a specific driver
    print("\n🔍 Testing Driver Retrieval:")
    try:
        elastic_driver = DriverRegistry.get("elastic_cloud")
        print(f"   ✅ Retrieved: {elastic_driver.__name__}")
        
        elastic_info = DriverRegistry.get_info("elastic_cloud")
        print(f"   ✅ Metadata: {elastic_info.metadata.display_name}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test error handling
    print("\n🧪 Testing Error Handling:")
    try:
        DriverRegistry.get("non_existent_driver")
    except KeyError as e:
        print(f"   ✅ Correctly raised KeyError: {e}")
    
    # Test duplicate registration prevention
    print("\n🔒 Testing Duplicate Prevention:")
    try:
        from otel_query_server.drivers.elastic_cloud import ElasticCloudDriver
        DriverRegistry.register("elastic_cloud", ElasticCloudDriver)
    except ValueError as e:
        print(f"   ✅ Correctly prevented duplicate: {e}")
    
    print("\n✨ All tests completed!")


if __name__ == "__main__":
    test_driver_registry() 