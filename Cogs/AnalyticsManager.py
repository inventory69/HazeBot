"""
Analytics Manager Cog
=====================
Manages the analytics system as a Discord Cog for better modularity.

Features:
- Start/Stop/Reload analytics system
- SQLite backend with real-time updates
- Integration with CogManager
- Graceful shutdown handling

Commands:
- None (managed via CogManager)

Usage:
    !reload AnalyticsManager  # Reload analytics system
    !stop AnalyticsManager    # Stop analytics (flushes pending data)
    !start AnalyticsManager   # Start analytics again
"""

import sys
from pathlib import Path

from discord.ext import commands

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
import Config
from Utils.Logger import Logger as logger


class AnalyticsManager(commands.Cog):
    """Manages the analytics system with SQLite backend"""

    def __init__(self, bot: commands.Bot):
        """
        Initialize Analytics Manager

        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.analytics = None
        self.error_tracker = None

        # Initialize analytics
        self._initialize_analytics()

    def _initialize_analytics(self) -> None:
        """Initialize analytics and error tracking systems"""
        try:
            import api.analytics as analytics_module
            import api.error_tracking as error_tracking_module

            # Initialize analytics aggregator (SQLite backend)
            analytics_file = Path(__file__).parent.parent / Config.DATA_DIR / "app_analytics.json"
            self.analytics = analytics_module.AnalyticsAggregator(
                analytics_file,
                batch_interval=300,  # Not used in SQLite mode, kept for compatibility
                cache_ttl=300,  # Not used in SQLite mode, kept for compatibility
            )

            # Initialize error tracker
            error_file = Path(__file__).parent.parent / Config.DATA_DIR / "error_analytics.json"
            self.error_tracker = error_tracking_module.ErrorTracker(error_file)

        except Exception as e:
            logger.error(f"Failed to initialize analytics: {e}", exc_info=True)
            raise

    def get_analytics(self):
        """
        Get analytics instance for use by API server

        Returns:
            AnalyticsAggregator instance or None
        """
        return self.analytics

    def get_error_tracker(self):
        """
        Get error tracker instance for use by API server

        Returns:
            ErrorTracker instance or None
        """
        return self.error_tracker

    async def cog_load(self) -> None:
        """Called when the cog is loaded"""
        pass  # Quiet loading

    async def cog_unload(self) -> None:
        """
        Called when the cog is unloaded
        Ensures graceful shutdown of analytics system
        """
        logger.info("Shutting down analytics system...")

        try:
            if self.analytics:
                # Graceful shutdown (closes DB connections)
                self.analytics.shutdown()

            if self.error_tracker:
                # Flush any pending errors
                pass

        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the bot is ready"""
        if self.analytics and self.error_tracker:
            logger.info("Analytics system online")


async def setup(bot: commands.Bot):
    """
    Setup function for loading the cog

    Args:
        bot: Discord bot instance
    """
    await bot.add_cog(AnalyticsManager(bot))
