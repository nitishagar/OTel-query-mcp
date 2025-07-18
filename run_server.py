#!/usr/bin/env python3
"""Run the OTEL Query Server using FastMCP."""

import sys
import os
import subprocess

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def main():
    """Run the server using FastMCP CLI."""
    # Get config file from command line if provided
    config_file = None
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
        os.environ['OTEL_QUERY_CONFIG_FILE'] = config_file
    
    # Run using FastMCP
    cmd = ["fastmcp", "run", "otel_query_server.server:create_mcp"]
    
    print(f"Starting OTEL Query Server...")
    if config_file:
        print(f"Using config: {config_file}")
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 