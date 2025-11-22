"""
API Server Cog - Manages the Flask API server
"""

import logging
import os
import sys
import threading
from pathlib import Path

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class APIServer(commands.Cog):
    """Cog to manage the Flask API server"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_thread = None
        self.api_port = int(os.getenv("API_PORT", 5070))
        self._server = None
        self._shutdown_event = threading.Event()
        self._suppress_errors = False  # Flag to suppress Waitress errors during shutdown
        logger.info("Initializing API Server cog")

    async def cog_load(self):
        """Called when cog is loaded - starts the API server"""
        import asyncio

        logger.info(f"Starting API server on port {self.api_port}...")
        
        # Wait to ensure port is released (in case of reload)
        logger.info("Waiting for port to be released...")
        await asyncio.sleep(3)
        
        self.start_api_server()
        
        # Wait for server to start (retry logic will handle delays)
        await asyncio.sleep(2)
        logger.info("API server startup sequence complete")

    async def cog_unload(self):
        """Called when cog is unloaded - stops the API server"""
        import asyncio
        
        logger.info("Stopping API server...")
        self.stop_api_server()
        
        # Give the server thread more time to clean up and release the port
        logger.info("Waiting for API server to fully stop and release port...")
        await asyncio.sleep(5)
        logger.info("API server shutdown complete")

    def start_api_server(self):
        """Start the Flask API server in a separate thread"""
        if self.api_thread and self.api_thread.is_alive():
            logger.warning("API server is already running")
            return

        # Reset shutdown event
        self._shutdown_event.clear()

        def run_api():
            import time
            
            # Import API app
            sys.path.insert(0, str(Path(__file__).parent.parent / "api"))
            from api.app import app, set_bot_instance

            # Set bot instance for API to use
            set_bot_instance(self.bot)

            # Create a custom exception handler that filters shutdown-related errors
            class ShutdownErrorFilter(logging.Filter):
                def __init__(self, shutdown_event):
                    super().__init__()
                    self.shutdown_event = shutdown_event
                
                def filter(self, record):
                    # Suppress common shutdown errors
                    if self.shutdown_event.is_set():
                        msg = str(record.getMessage())
                        if any(err in msg for err in [
                            'Bad file descriptor',
                            'Invalid argument',
                            'Exception when servicing',
                            'server accept() threw'
                        ]):
                            return False
                    return True
            
            # Add filter to waitress logger
            waitress_logger = logging.getLogger('waitress')
            shutdown_filter = ShutdownErrorFilter(self._shutdown_event)
            waitress_logger.addFilter(shutdown_filter)

            # Use Waitress (production-ready, thread-safe WSGI server)
            from waitress import serve

            # Retry logic for port binding
            max_retries = 8
            retry_delay = 3  # seconds
            
            for attempt in range(1, max_retries + 1):
                # Check if shutdown was requested
                if self._shutdown_event.is_set():
                    logger.info("Shutdown requested before server start, aborting...")
                    return
                
                try:
                    logger.info(f"API server starting on port {self.api_port} (attempt {attempt}/{max_retries})...")
                    
                    # Suppress Waitress exceptions during shutdown
                    import warnings
                    warnings.filterwarnings("ignore", category=ResourceWarning)
                    
                    # Start the server (this blocks until server stops)
                    from waitress.server import create_server
                    self._server = create_server(
                        app, 
                        host="0.0.0.0", 
                        port=self.api_port, 
                        threads=8,
                        channel_timeout=1  # Shorter timeout for faster shutdown
                    )
                    logger.info(f"API server successfully bound to port {self.api_port}")
                    
                    # Run the server (suppress exceptions during shutdown)
                    try:
                        self._server.run()
                    except (OSError, IOError) as e:
                        # Expected during shutdown - ignore
                        if not self._shutdown_event.is_set():
                            raise
                    
                    # Only log if this was an intentional shutdown
                    if self._shutdown_event.is_set():
                        logger.debug("API server thread terminated (shutdown requested)")
                    else:
                        logger.info("API server stopped unexpectedly")
                    break  # Server stopped normally
                    
                except OSError as e:
                    if e.errno == 98:  # Address already in use
                        if attempt < max_retries:
                            logger.warning(f"Port {self.api_port} still in use, waiting {retry_delay}s before retry {attempt + 1}/{max_retries}...")
                            time.sleep(retry_delay)
                        else:
                            logger.error(f"Failed to bind port {self.api_port} after {max_retries} attempts ({max_retries * retry_delay}s total)")
                            return
                    else:
                        logger.error(f"Failed to start API server: {e}", exc_info=True)
                        return
                except Exception as e:
                    logger.error(f"Failed to start API server: {e}", exc_info=True)
                    return

        self.api_thread = threading.Thread(target=run_api, daemon=False, name="APIServerThread")
        self.api_thread.start()
        logger.info(f"API server thread started on port {self.api_port}")

    def stop_api_server(self):
        """Stop the API server"""
        if not self.api_thread or not self.api_thread.is_alive():
            logger.info("API server is not running")
            return
        
        # Signal shutdown and suppress Waitress errors
        self._shutdown_event.set()
        self._suppress_errors = True
        
        # Suppress Waitress logging during shutdown
        waitress_logger = logging.getLogger('waitress')
        old_level = waitress_logger.level
        waitress_logger.setLevel(logging.CRITICAL)
        
        # Close the server if it exists
        if self._server:
            logger.info("Shutting down API server gracefully...")
            try:
                # First, stop accepting new connections
                import socket
                try:
                    self._server.socket.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass  # Socket might already be closed
                
                # Then close the server
                self._server.close()
                logger.info("API server closed successfully")
            except Exception as e:
                logger.warning(f"Error during server shutdown: {e}")
        
        # Wait longer for thread to finish (with timeout)
        logger.info("Waiting for API server thread to terminate...")
        self.api_thread.join(timeout=8)
        
        # Restore Waitress logging
        waitress_logger.setLevel(old_level)
        self._suppress_errors = False
        
        if self.api_thread.is_alive():
            logger.debug("API server thread still running (background cleanup)")
        else:
            logger.info("API server thread terminated successfully")
        
        self._server = None

    @commands.command(name="apistatus", hidden=True)
    @commands.has_permissions(administrator=True)
    async def api_status(self, ctx: commands.Context):
        """Check API server status"""
        if self.api_thread and self.api_thread.is_alive():
            embed = discord.Embed(
                title="🌐 API Server Status",
                description=f"✅ Running on port {self.api_port}",
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="🌐 API Server Status",
                description="❌ Not running",
                color=discord.Color.red(),
            )
        await ctx.send(embed=embed)

    @commands.command(name="apirestart", hidden=True)
    @commands.has_permissions(administrator=True)
    async def api_restart(self, ctx: commands.Context):
        """Restart the API server"""
        logger.info("Restarting API server...")
        self.stop_api_server()

        # Wait a bit for the thread to stop
        import time

        time.sleep(1)

        self.start_api_server()

        # Wait for API to start
        time.sleep(2)

        embed = discord.Embed(
            title="🌐 API Server Restarted",
            description=f"✅ API server restarted on port {self.api_port}",
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(APIServer(bot))
