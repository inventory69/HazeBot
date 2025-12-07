"""
Status Dashboard Cog
Maintains a live-updating status embed in a dedicated channel
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands, tasks

import Config
from Config import DATA_DIR, STATUS_CHANNEL_ID, STATUS_DASHBOARD_CONFIG
from Utils.EmbedUtils import set_pink_footer

logger = logging.getLogger(__name__)

# Data file for persistence
STATUS_DASHBOARD_FILE = f"{DATA_DIR}/status_dashboard.json"


class StatusDashboard(commands.Cog):
    """Maintains a live status dashboard in a dedicated channel"""
    
    # Cog Metadata for Admin Panel
    COG_METADATA = {
        "category": "monitoring",
        "display_name": "Status Dashboard",
        "description": (
            "Maintains a live-updating status embed in a dedicated channel "
            "with real-time service monitoring"
        ),
        "icon": "📊",
        "features": [
            "Live status embed updates every N minutes",
            "Service status monitoring (API, Bot, Database)",
            "Uptime tracking and display",
            "Automatic message persistence across restarts",
            "Configurable update intervals",
            "Optional Uptime Kuma integration",
        ],
        "dependencies": [],
        "requires_config": ["STATUS_CHANNEL_ID"],
    }

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.status_message_id: Optional[int] = None
        self.status_channel_id: Optional[int] = STATUS_CHANNEL_ID
        self._setup_complete = False  # Flag to prevent duplicate posts
        
        # Load saved data
        self._load_dashboard_data()
        
        # Start background task
        if STATUS_DASHBOARD_CONFIG.get('enabled', True):
            self.update_status_dashboard.start()
        else:
            logger.info("📊 [StatusDashboard] Status dashboard is disabled")

    def cog_unload(self):
        """Clean shutdown"""
        self.update_status_dashboard.cancel()
        logger.info("📊 [StatusDashboard] Background update task stopped")

    @tasks.loop(minutes=STATUS_DASHBOARD_CONFIG.get('update_interval_minutes', 5))
    async def update_status_dashboard(self):
        """Background task to update status embed"""
        try:
            if not STATUS_DASHBOARD_CONFIG.get('enabled', True):
                return
            
            # Skip first run if setup not complete yet (prevents duplicate post)
            if not self._setup_complete:
                return
            
            await self.post_or_update_status()
            logger.debug("📊 [StatusDashboard] Status updated successfully")
        except Exception as e:
            logger.error(f"📊 [StatusDashboard] Error updating status: {e}", exc_info=True)

    @update_status_dashboard.before_loop
    async def before_status_update(self):
        """Wait for bot to be ready"""
        await self.bot.wait_until_ready()
        logger.debug("📊 [StatusDashboard] Waiting for bot ready before starting updates")

    async def post_or_update_status(self):
        """Post new status message or update existing"""
        # Check if enabled
        if not STATUS_DASHBOARD_CONFIG.get('enabled', True):
            logger.debug("📊 [StatusDashboard] Status dashboard is disabled, skipping update")
            return
        
        # Check if channel is configured
        if not self.status_channel_id:
            logger.warning("📊 [StatusDashboard] STATUS_CHANNEL_ID not configured")
            return
        
        # Get channel
        channel = self.bot.get_channel(self.status_channel_id)
        if not channel:
            logger.error(f"📊 [StatusDashboard] Channel {self.status_channel_id} not found")
            return
        
        # Create embed
        embed = await self._create_status_embed()
        
        # Try to update existing message
        if self.status_message_id:
            try:
                message = await channel.fetch_message(self.status_message_id)
                await message.edit(embed=embed)
                logger.debug(f"📊 [StatusDashboard] Updated existing message {self.status_message_id}")
                self._save_dashboard_data()
                return
            except discord.NotFound:
                logger.warning(f"📊 [StatusDashboard] Message {self.status_message_id} not found, creating new one")
                self.status_message_id = None
            except discord.HTTPException as e:
                logger.error(f"📊 [StatusDashboard] Error updating message: {e}")
                return
        
        # Post new message
        try:
            message = await channel.send(embed=embed)
            self.status_message_id = message.id
            self._save_dashboard_data()
            logger.info(f"📊 [StatusDashboard] Posted new status message {message.id} in channel {channel.name}")
        except discord.HTTPException as e:
            logger.error(f"📊 [StatusDashboard] Error posting message: {e}")

    async def _create_status_embed(self) -> discord.Embed:
        """Create status embed with monitoring data"""
        # Get Utility cog for status creation
        utility_cog = self.bot.get_cog("Utility")
        
        # Fetch monitoring data if available
        monitoring_data = None
        if STATUS_DASHBOARD_CONFIG.get('show_monitoring', True) and utility_cog:
            if hasattr(utility_cog, 'fetch_monitoring_data'):
                try:
                    monitoring_data = await utility_cog.fetch_monitoring_data()
                except Exception as e:
                    logger.debug(f"📊 [StatusDashboard] Could not fetch monitoring data: {e}")
        
        # Create embed using Utility cog's method
        if utility_cog and hasattr(utility_cog, 'create_status_embed'):
            embed = utility_cog.create_status_embed(
                self.bot.user,
                self.bot.latency,
                len(self.bot.guilds),
                monitoring_data
            )
        else:
            # Fallback: Basic embed
            embed = discord.Embed(
                title="💖 HazeBot Status",
                description="The bot is online and fabulous!",
                color=Config.PINK,
            )
            embed.add_field(
                name="📊 Bot Status",
                value=(
                    f"• **Latency:** {round(self.bot.latency * 1000)}ms\n"
                    f"• **Guilds:** {len(self.bot.guilds)}"
                ),
                inline=False,
            )
            set_pink_footer(embed, bot=self.bot.user)
        
        # Add last updated timestamp
        embed.set_footer(text=f"{embed.footer.text} • Last Updated: {datetime.utcnow().strftime('%H:%M:%S')} UTC")
        
        return embed

    async def setup_persistent_status(self):
        """Setup persistent status dashboard - called on ready"""
        logger.info("📊 [StatusDashboard] Setting up persistent status dashboard...")
        
        # Check if enabled
        if not STATUS_DASHBOARD_CONFIG.get('enabled', True):
            logger.info("📊 [StatusDashboard] Status dashboard is disabled")
            return
        
        # Check if channel configured
        if not self.status_channel_id:
            logger.warning("📊 [StatusDashboard] STATUS_CHANNEL_ID not configured")
            return
        
        # Verify channel exists
        channel = self.bot.get_channel(self.status_channel_id)
        if not channel:
            logger.error(f"📊 [StatusDashboard] Channel {self.status_channel_id} not found")
            return
        
        # Verify message still exists if we have an ID
        if self.status_message_id:
            try:
                await channel.fetch_message(self.status_message_id)
                logger.info(
                    f"📊 [StatusDashboard] Found existing status message "
                    f"{self.status_message_id}"
                )
            except discord.NotFound:
                logger.warning(
                    f"📊 [StatusDashboard] Saved message {self.status_message_id} "
                    f"not found, will create new one"
                )
                self.status_message_id = None
        
        # Post or update status
        await self.post_or_update_status()
        
        # Mark setup as complete (allows background task to run)
        self._setup_complete = True
        
        logger.info("📊 [StatusDashboard] Status dashboard setup complete")
        update_interval = STATUS_DASHBOARD_CONFIG.get('update_interval_minutes', 5)
        logger.info(
            f"📊 [StatusDashboard] Background update task running "
            f"(interval: {update_interval} minutes)"
        )

    def _load_dashboard_data(self):
        """Load status dashboard data from file"""
        if not os.path.exists(STATUS_DASHBOARD_FILE):
            logger.debug("📊 [StatusDashboard] No saved dashboard data found")
            return
        
        try:
            with open(STATUS_DASHBOARD_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.status_message_id = data.get('message_id')
                self.status_channel_id = data.get('channel_id', STATUS_CHANNEL_ID)
                logger.debug(f"📊 [StatusDashboard] Loaded dashboard data: message_id={self.status_message_id}")
        except Exception as e:
            logger.error(f"📊 [StatusDashboard] Error loading dashboard data: {e}")

    def _save_dashboard_data(self):
        """Save status dashboard data to file"""
        try:
            data = {
                "message_id": self.status_message_id,
                "channel_id": self.status_channel_id,
                "last_update": datetime.utcnow().isoformat() + 'Z',
            }
            
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(STATUS_DASHBOARD_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"📊 [StatusDashboard] Saved dashboard data: message_id={self.status_message_id}")
        except Exception as e:
            logger.error(f"📊 [StatusDashboard] Error saving dashboard data: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        """Setup status dashboard when bot is ready"""
        await self.setup_persistent_status()


async def setup(bot: commands.Bot):
    await bot.add_cog(StatusDashboard(bot))
