#!/usr/bin/env python3
"""
Quick test script to verify Elastic Cloud connection before running the OTEL Query Server.
"""

import os
import sys
import urllib.request
import ssl
from elasticsearch import Elasticsearch
import warnings
warnings.filterwarnings('ignore')

def test_elastic_connection():
    # Configuration - update these values
    ELASTIC_URL = "https://dcsites-non-prod-usw2.es.us-west-2.aws.found.io:9243"
    # Try environment variable first, then use the one from config
    API_KEY = os.getenv("ELASTIC_API_KEY", "N2ljZ0hKZ0JHeFZHRVIycklpMVk6eWdNSk1KYllSZWVTb3RqaG9iSm9VUQ==")
    
    if not API_KEY:
        print("❌ Error: Please set ELASTIC_API_KEY environment variable")
        print("   export ELASTIC_API_KEY='your-base64-encoded-key'")
        return False
    
    print(f"🔍 Testing connection to: {ELASTIC_URL}")
    print(f"🔑 API Key (first 20 chars): {API_KEY[:20]}...")
    print(f"🔑 API Key length: {len(API_KEY)} characters")
    
    # Verify the API key looks like base64
    import base64
    try:
        base64.b64decode(API_KEY)
        print("✅ API key appears to be valid base64")
    except Exception:
        print("❌ API key does not appear to be valid base64!")
    
    # First test basic connectivity
    print("\n🌐 Testing basic network connectivity...")
    try:
        # Create a basic HTTPS request
        # Note: ApiKey should be sent as-is (it's already base64 encoded)
        req = urllib.request.Request(f"{ELASTIC_URL}/", headers={
            'Authorization': f'ApiKey {API_KEY}',
            'Content-Type': 'application/json'
        })
        
        # Try with SSL
        try:
            response = urllib.request.urlopen(req)
            print(f"✅ Basic HTTPS connection successful! Status: {response.status}")
        except urllib.error.HTTPError as e:
            print(f"⚠️  HTTP Error {e.code}: {e.reason}")
            if e.code == 401:
                print("❌ Authentication failed - API key may be invalid")
        except urllib.error.URLError as e:
            if "certificate verify failed" in str(e):
                print("⚠️  SSL certificate verification failed, trying without verification...")
                # Try without SSL verification
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                try:
                    response = urllib.request.urlopen(req, context=ctx)
                    print(f"✅ Connection works without SSL verification! Status: {response.status}")
                except Exception as e2:
                    print(f"❌ Still failed: {e2}")
            else:
                print(f"❌ Network error: {e}")
    except Exception as e:
        print(f"❌ Basic connectivity test failed: {e}")
    
    # Now try with Elasticsearch client
    print("\n📊 Testing with Elasticsearch client...")
    # First try with SSL verification
    print("🔐 Trying with SSL verification enabled...")
    try:
        # Create Elasticsearch client
        es = Elasticsearch(
            [ELASTIC_URL],
            api_key=API_KEY,
            verify_certs=True,
            request_timeout=30
        )
        
        # Try to get cluster info directly (sometimes ping() fails but info() works)
        try:
            info = es.info()
            print("✅ Connection successful!")
            print(f"📊 Cluster name: {info['cluster_name']}")
            print(f"📊 Version: {info['version']['number']}")
            
            # List indices
            try:
                indices = es.cat.indices(format="json")
                print(f"📊 Number of indices: {len(indices)}")
            except Exception as idx_error:
                print(f"⚠️  Could not list indices: {idx_error}")
            
            return True
        except Exception as info_error:
            print(f"❌ Could not get cluster info: {info_error}")
            
            # Try ping as fallback
            try:
                if es.ping():
                    print("✅ Ping successful but info() failed")
                    return True
                else:
                    print("❌ Connection failed - could not ping cluster")
            except Exception as ping_error:
                print(f"❌ Ping error: {ping_error}")
            
    except Exception as e:
        print(f"❌ SSL Connection error: {type(e).__name__}: {str(e)}")
        
        # Try without SSL verification
        print("\n🔓 Trying without SSL verification...")
        try:
            es_no_ssl = Elasticsearch(
                [ELASTIC_URL],
                api_key=API_KEY,
                verify_certs=False,
                ssl_show_warn=False,
                request_timeout=30
            )
            
            if es_no_ssl.ping():
                print("✅ Connection successful without SSL verification!")
                print("⚠️  Note: You should set 'verify_certs: false' in your config")
                
                # Get cluster info
                info = es_no_ssl.info()
                print(f"📊 Cluster name: {info['cluster_name']}")
                print(f"📊 Version: {info['version']['number']}")
                
                return True
            else:
                print("❌ Still failed without SSL verification")
                
        except Exception as e2:
            print(f"❌ Non-SSL Connection error: {type(e2).__name__}: {str(e2)}")
    
    return False

if __name__ == "__main__":
    print("OTEL Query Server - Elastic Cloud Connection Test")
    print("=" * 50)
    
    if test_elastic_connection():
        print("\n✅ Connection test passed! You can now run the OTEL Query Server.")
        print("\nNext steps:")
        print("1. Update config-elastic-test.yaml with your API key")
        print("2. Run: python -m otel_query_server.server --config config-elastic-test.yaml")
    else:
        print("\n❌ Connection test failed. Please check your configuration.")
        sys.exit(1) 