"""FastMCP server for OpenTelemetry Query Server."""

import asyncio
import signal
import sys
from typing import Any, Dict, List, Optional

import structlog
from fastmcp import FastMCP
from pydantic import BaseModel

from otel_query_server import __version__
from otel_query_server.cache import init_cache
from otel_query_server.config import Config, get_config, load_config, set_config
from otel_query_server.drivers.base import BaseDriver, DriverRegistry

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class OTelQueryServer:
    """OpenTelemetry Query Server MCP implementation."""
    
    def __init__(self, config: Optional[Config] = None) -> None:
        """Initialize the server.
        
        Args:
            config: Server configuration
        """
        self.config = config or get_config()
        set_config(self.config)
        
        # Initialize FastMCP
        self.mcp = FastMCP(
            name=self.config.server.name,
            version=self.config.server.version
        )
        
        # Initialize cache
        self.cache = init_cache(self.config.cache)
        
        # Initialize drivers
        self.drivers: Dict[str, BaseDriver] = {}
        
        # Store server info
        self.server_info = {
            "name": self.config.server.name,
            "version": self.config.server.version,
            "description": self.config.server.description,
        }
        
        self.logger = logger.bind(server=self.config.server.name)
        
        # Register server capabilities
        self._setup_server_info()
        
        # Register tools
        self._register_tools()
    
    def _setup_server_info(self) -> None:
        """Set up server information and capabilities."""
        # Server will automatically handle capabilities based on registered tools
        self.logger.info(
            "Server initialized",
            name=self.config.server.name,
            version=self.config.server.version
        )
    
    def _register_tools(self) -> None:
        """Register MCP tools."""
        # Tools will be registered here as they are implemented
        # For now, register a basic health check tool
        
        # Store references for use in tool functions
        server_info = self.server_info
        config = self.config
        cache = self.cache
        
        @self.mcp.tool()
        async def get_server_info() -> Dict[str, Any]:
            """Get information about the OpenTelemetry Query Server.
            
            Returns server name, version, enabled backends, and cache statistics.
            """
            return {
                "server": server_info,
                "backends": {
                    "enabled": config.get_enabled_backends(),
                    "configured": {
                        "otel_collector": config.backends.otel_collector is not None,
                        "grafana": config.backends.grafana is not None,
                        "elastic_cloud": config.backends.elastic_cloud is not None,
                        "opensearch": config.backends.opensearch is not None,
                    }
                },
                "cache": cache.get_stats() if cache else {"enabled": False}
            }
        
        self.logger.info("Registered MCP tools", tools=["get_server_info"])
    
    async def initialize_drivers(self) -> None:
        """Initialize backend drivers."""
        self.logger.info("Initializing backend drivers")
        
        # Initialize each configured backend
        backends = self.config.backends
        
        if backends.otel_collector and backends.otel_collector.enabled:
            try:
                # Driver will be imported when implemented
                self.logger.info("OTEL Collector driver not yet implemented")
            except Exception as e:
                self.logger.error("Failed to initialize OTEL Collector driver", error=str(e))
        
        if backends.grafana and backends.grafana.enabled:
            try:
                # Driver will be imported when implemented
                self.logger.info("Grafana driver not yet implemented")
            except Exception as e:
                self.logger.error("Failed to initialize Grafana driver", error=str(e))
        
        if backends.elastic_cloud and backends.elastic_cloud.enabled:
            try:
                # Driver will be imported when implemented
                self.logger.info("Elastic Cloud driver not yet implemented")
            except Exception as e:
                self.logger.error("Failed to initialize Elastic Cloud driver", error=str(e))
        
        if backends.opensearch and backends.opensearch.enabled:
            try:
                # Driver will be imported when implemented
                self.logger.info("OpenSearch driver not yet implemented")
            except Exception as e:
                self.logger.error("Failed to initialize OpenSearch driver", error=str(e))
        
        if not self.drivers:
            self.logger.warning("No backend drivers initialized")
    
    async def close_drivers(self) -> None:
        """Close all backend drivers."""
        self.logger.info("Closing backend drivers")
        
        for name, driver in self.drivers.items():
            try:
                await driver.close()
                self.logger.info("Closed driver", driver=name)
            except Exception as e:
                self.logger.error("Error closing driver", driver=name, error=str(e))
    
    async def start(self) -> None:
        """Start the server."""
        self.logger.info("Starting OpenTelemetry Query Server")
        
        # Initialize drivers
        await self.initialize_drivers()
        
        # Run the MCP server
        await self.mcp.run()
    
    async def stop(self) -> None:
        """Stop the server."""
        self.logger.info("Stopping OpenTelemetry Query Server")
        
        # Close drivers
        await self.close_drivers()
        
        self.logger.info("Server stopped")


async def main(config_path: Optional[str] = None) -> None:
    """Main entry point for the server.
    
    Args:
        config_path: Optional path to configuration file
    """
    # Load configuration
    config = None
    try:
        config = load_config(config_path)
        config.validate_backends()
    except Exception as e:
        logger.error("Failed to load configuration", error=str(e))
        sys.exit(1)
        return  # For testing - won't reach here in production
    
    # Set up logging level
    import logging
    log_level = getattr(logging, config.server.log_level.upper())
    logging.basicConfig(level=log_level)
    
    # Create and start server
    server = OTelQueryServer(config)
    
    # Set up signal handlers
    loop = asyncio.get_event_loop()
    
    def signal_handler(sig: signal.Signals) -> None:
        """Handle shutdown signals."""
        logger.info("Received signal", signal=sig.name)
        loop.create_task(server.stop())
        loop.stop()
    
    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, lambda s, f: signal_handler(s))
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error("Server error", error=str(e), exc_info=True)
        sys.exit(1)
    finally:
        await server.stop()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenTelemetry Query Server")
    parser.add_argument(
        "-c", "--config",
        help="Path to configuration file",
        default=None
    )
    
    args = parser.parse_args()
    
    asyncio.run(main(args.config)) 