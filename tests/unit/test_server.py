"""Unit tests for the FastMCP server."""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from otel_query_server.config import BackendsConfig, CacheConfig, Config, ServerConfig
from otel_query_server.server import OTelQueryServer, main


class TestOTelQueryServer:
    """Test OTelQueryServer functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config(
            server=ServerConfig(
                name="test-server",
                version="1.0.0",
                description="Test server",
                log_level="INFO"
            ),
            cache=CacheConfig(enabled=True, max_size=100),
            backends=BackendsConfig()
        )
    
    @pytest.fixture
    def server(self, config):
        """Create test server instance."""
        with patch("otel_query_server.server.FastMCP"):
            with patch("otel_query_server.server.init_cache") as mock_cache:
                mock_cache.return_value = MagicMock()
                server = OTelQueryServer(config)
                return server
    
    def test_init(self, server, config):
        """Test server initialization."""
        assert server.config == config
        assert server.server_info["name"] == "test-server"
        assert server.server_info["version"] == "1.0.0"
        assert server.server_info["description"] == "Test server"
        assert server.drivers == {}
    
    def test_server_info_registration(self, server):
        """Test server info setup."""
        # The server should have called _setup_server_info
        assert server.logger is not None
    
    @patch("otel_query_server.server.set_config")
    def test_config_is_set(self, mock_set_config, config):
        """Test that config is set globally."""
        with patch("otel_query_server.server.FastMCP"):
            with patch("otel_query_server.server.init_cache"):
                server = OTelQueryServer(config)
                mock_set_config.assert_called_once_with(config)
    
    async def test_initialize_drivers_no_backends(self, server):
        """Test driver initialization with no backends configured."""
        await server.initialize_drivers()
        assert len(server.drivers) == 0
    
    async def test_initialize_drivers_with_backends(self, config):
        """Test driver initialization with backends configured."""
        from otel_query_server.config import OTELCollectorConfig
        
        config.backends.otel_collector = OTELCollectorConfig(
            endpoint="localhost:4317",
            enabled=True
        )
        
        with patch("otel_query_server.server.FastMCP"):
            with patch("otel_query_server.server.init_cache"):
                server = OTelQueryServer(config)
                await server.initialize_drivers()
                
                # Since drivers aren't implemented yet, should still be empty
                assert len(server.drivers) == 0
    
    async def test_close_drivers_empty(self, server):
        """Test closing drivers when none exist."""
        await server.close_drivers()
        # Should not raise any errors
    
    async def test_close_drivers_with_drivers(self, server):
        """Test closing drivers."""
        # Add mock drivers
        mock_driver1 = AsyncMock()
        mock_driver2 = AsyncMock()
        server.drivers = {
            "driver1": mock_driver1,
            "driver2": mock_driver2
        }
        
        await server.close_drivers()
        
        mock_driver1.close.assert_called_once()
        mock_driver2.close.assert_called_once()
    
    async def test_close_drivers_with_error(self, server):
        """Test closing drivers with error."""
        # Add mock driver that raises error
        mock_driver = AsyncMock()
        mock_driver.close.side_effect = Exception("Close failed")
        server.drivers = {"driver1": mock_driver}
        
        # Should not raise, just log error
        await server.close_drivers()
        mock_driver.close.assert_called_once()
    
    async def test_start(self, server):
        """Test starting the server."""
        server.initialize_drivers = AsyncMock()
        server.mcp.run = AsyncMock()
        
        await server.start()
        
        server.initialize_drivers.assert_called_once()
        server.mcp.run.assert_called_once()
    
    async def test_stop(self, server):
        """Test stopping the server."""
        server.close_drivers = AsyncMock()
        
        await server.stop()
        
        server.close_drivers.assert_called_once()


class TestMain:
    """Test main function."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = MagicMock()
        config.server = MagicMock()
        config.server.log_level = "INFO"
        config.validate_backends = MagicMock()
        return config
    
    @patch("otel_query_server.server.load_config")
    @patch("otel_query_server.server.OTelQueryServer")
    @patch("asyncio.get_event_loop")
    async def test_main_success(self, mock_loop, mock_server_class, mock_load_config, mock_config):
        """Test successful main execution."""
        mock_load_config.return_value = mock_config
        mock_server = AsyncMock()
        mock_server_class.return_value = mock_server
        
        # Mock the event loop
        mock_loop.return_value = MagicMock()
        
        # Run main without actually starting the server
        with patch.object(mock_server, "start", new=AsyncMock()):
            await main("/path/to/config.yaml")
        
        mock_load_config.assert_called_once_with("/path/to/config.yaml")
        mock_config.validate_backends.assert_called_once()
        mock_server_class.assert_called_once_with(mock_config)
    
    @patch("otel_query_server.server.load_config")
    @patch("sys.exit")
    async def test_main_config_error(self, mock_exit, mock_load_config):
        """Test main with configuration error."""
        mock_load_config.side_effect = Exception("Config error")
        
        await main("/path/to/config.yaml")
        
        mock_exit.assert_called_once_with(1)
    
    @patch("otel_query_server.server.load_config")
    @patch("otel_query_server.server.OTelQueryServer")
    @patch("sys.exit")
    async def test_main_server_error(self, mock_exit, mock_server_class, mock_load_config, mock_config):
        """Test main with server error."""
        mock_load_config.return_value = mock_config
        mock_server = AsyncMock()
        mock_server.start.side_effect = Exception("Server error")
        mock_server_class.return_value = mock_server
        
        with patch("asyncio.get_event_loop"):
            await main("/path/to/config.yaml")
        
        mock_exit.assert_called_once_with(1)
        mock_server.stop.assert_called_once()


class TestSignalHandling:
    """Test signal handling in main."""
    
    @patch("otel_query_server.server.signal.signal")
    @patch("otel_query_server.server.load_config")
    @patch("otel_query_server.server.OTelQueryServer")
    @patch("asyncio.get_event_loop")
    async def test_signal_handlers_registered(self, mock_loop, mock_server_class, mock_load_config, mock_signal):
        """Test that signal handlers are registered."""
        import signal
        
        mock_config = MagicMock()
        mock_config.server.log_level = "INFO"
        mock_load_config.return_value = mock_config
        
        mock_server = AsyncMock()
        mock_server_class.return_value = mock_server
        
        mock_loop_instance = MagicMock()
        mock_loop.return_value = mock_loop_instance
        
        with patch.object(mock_server, "start", new=AsyncMock()):
            await main()
        
        # Check that signal handlers were registered
        assert mock_signal.call_count == 2
        signal_calls = mock_signal.call_args_list
        
        # Should register SIGTERM and SIGINT
        registered_signals = {call[0][0] for call in signal_calls}
        assert signal.SIGTERM in registered_signals
        assert signal.SIGINT in registered_signals 