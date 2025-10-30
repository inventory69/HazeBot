import discord
from discord.ext import commands, tasks
import logging
import asyncio
from collections import deque
import os
from datetime import datetime, timedelta, timezone

from Config import PINK, ADMIN_ROLE_ID, COG_PREFIXES

logger = logging.getLogger(__name__)


class DiscordLogHandler(logging.Handler):
    """Custom logging handler that sends logs to Discord"""

    def __init__(self, bot: commands.Bot, channel_id: int):
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id
        self.log_queue = deque()
        self.batch_size = 10  # Send logs in batches
        self.max_message_length = 1900  # Discord limit is 2000, keep some buffer

    def emit(self, record):
        """Add log record to queue"""
        try:
            msg = self.format(record)
            self.log_queue.append(msg)
        except Exception:
            self.handleError(record)

    async def flush_logs(self):
        """Send queued logs to Discord"""
        if not self.log_queue:
            return

        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            return

        # Collect logs from queue
        logs_to_send = []
        while self.log_queue and len(logs_to_send) < self.batch_size:
            logs_to_send.append(self.log_queue.popleft())

        if not logs_to_send:
            return

        # Group logs into messages that fit Discord's limit
        current_message = "```ansi\n"
        for log in logs_to_send:
            # Check if adding this log would exceed the limit
            if len(current_message) + len(log) + 10 > self.max_message_length:
                # Send current message and start a new one
                current_message += "```"
                try:
                    await channel.send(current_message)
                    await asyncio.sleep(0.5)  # Rate limit protection
                except Exception as e:
                    logger.error(f"Failed to send log to Discord: {e}")
                current_message = "```ansi\n"

            current_message += log + "\n"

        # Send remaining logs
        if current_message != "```ansi\n":
            current_message += "```"
            try:
                await channel.send(current_message)
            except Exception as e:
                logger.error(f"Failed to send log to Discord: {e}")


class DiscordLogFormatter(logging.Formatter):
    """Custom formatter that converts Rich emoji logs to ANSI colors for Discord"""

    def __init__(self):
        super().__init__(datefmt="[%H:%M:%S]")
        # ANSI color codes for Discord
        self.colors = {
            "DEBUG": "\u001b[0;36m",  # Cyan
            "INFO": "\u001b[0;32m",  # Green
            "WARNING": "\u001b[0;33m",  # Yellow
            "ERROR": "\u001b[0;31m",  # Red
            "CRITICAL": "\u001b[0;35m",  # Magenta
            "RESET": "\u001b[0m",  # Reset
        }
        # Cog-specific colors for highlighting
        self.cog_colors = {
            "RocketLeague": "\u001b[0;33m",  # Yellow/Orange for Rocket League
            "DailyMeme": "\u001b[0;35m",  # Magenta/Pink for Daily Meme
            "TicketSystem": "\u001b[0;32m",  # Green for Tickets
            "DiscordLogging": "\u001b[0;35m",  # Magenta for Discord Logging
            "Welcome": "\u001b[0;36m",  # Cyan for Welcome
        }

    def format(self, record):
        # Get emoji based on level (matching Logger.py)
        emoji = (
            "💖"
            if record.levelno == logging.INFO
            else "🌸"
            if record.levelno == logging.WARNING
            else "🩷"
            if record.levelno == logging.ERROR
            else "🚨"
        )

        level = (
            "DEBUG"
            if record.levelno == logging.DEBUG
            else "INFO"
            if record.levelno == logging.INFO
            else "WARN"
            if record.levelno == logging.WARNING
            else "ERROR"
            if record.levelno == logging.ERROR
            else "CRITICAL"
        )

        time_str = self.formatTime(record, self.datefmt)

        # Define reset early so it's available everywhere
        reset = self.colors["RESET"]

        # Add cog prefix based on logger name
        prefix = self.get_cog_prefix(record.name)
        cog_name = self.get_cog_name(record.name)
        message = record.getMessage()
        
        # Color the entire message if it's from a specific cog
        cog_color = self.cog_colors.get(cog_name, "")
        
        if prefix:
            if cog_color:
                # Color the entire line (prefix + message) for specific cogs
                message = f"{cog_color}{prefix} {message}{reset}"
            else:
                message = f"{prefix} {message}"
        elif cog_color:
            # Color just the message if no prefix but cog matches
            message = f"{cog_color}{message}{reset}"

        # Add ANSI color for level
        color = self.colors.get(level, self.colors["RESET"])

        return f"{time_str} {emoji}  {color}{level:<7}{reset} │ {message}"

    def get_cog_name(self, name):
        """Extract cog name from logger name"""
        parts = name.split(".")
        if len(parts) >= 2 and parts[-2] == "Cogs":
            return parts[-1]
        return ""

    def get_cog_prefix(self, name):
        """Extract cog prefix (matching Logger.py)"""
        parts = name.split(".")
        if len(parts) >= 2 and parts[-2] == "Cogs":
            cog_name = parts[-1]
            return COG_PREFIXES.get(cog_name, "")
        return ""


class DiscordLogging(commands.Cog):
    """
    📡 Discord Logging: Send all bot logs to a Discord channel in real-time
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.discord_handler = None
        self.enabled = True
        self._setup_done = False

        # Determine channel ID based on PROD_MODE
        prod_mode = os.getenv("PROD_MODE", "false").lower() != "false"
        self.log_channel_id = 1433187806347526244 if prod_mode else 1433187651191701688

    @commands.Cog.listener()
    async def on_ready(self):
        """Set up Discord logging when bot is ready"""
        if self._setup_done:
            return  # Only setup once

        self._setup_done = True

        # Set up Discord logging handler
        self.discord_handler = DiscordLogHandler(self.bot, self.log_channel_id)
        self.discord_handler.setLevel(logging.DEBUG)  # Log ALL levels
        self.discord_handler.setFormatter(DiscordLogFormatter())

        # Add handler to root logger to catch all logs
        root_logger = logging.getLogger()
        root_logger.addHandler(self.discord_handler)

        # Start the flush task
        self.flush_logs_task.start()
        self.cleanup_old_logs_task.start()

        logger.info("Discord logging handler started - logs streaming to Discord")

    async def cog_unload(self):
        """Called when the cog is unloaded"""
        if self.flush_logs_task.is_running():
            self.flush_logs_task.cancel()

        if self.cleanup_old_logs_task.is_running():
            self.cleanup_old_logs_task.cancel()

        if self.discord_handler:
            # Remove handler from root logger
            root_logger = logging.getLogger()
            root_logger.removeHandler(self.discord_handler)

        logger.info("Discord logging handler stopped")

    @tasks.loop(seconds=5.0)
    async def flush_logs_task(self):
        """Periodically flush logs to Discord"""
        if self.enabled and self.discord_handler:
            await self.discord_handler.flush_logs()

    @flush_logs_task.before_loop
    async def before_flush_logs(self):
        """Wait for bot to be ready before starting the task"""
        await self.bot.wait_until_ready()

    @tasks.loop(hours=24.0)
    async def cleanup_old_logs_task(self):
        """Delete log messages older than 3 days"""
        try:
            channel = self.bot.get_channel(self.log_channel_id)
            if not channel:
                logger.warning("Log channel not found for cleanup")
                return

            # Calculate cutoff time (3 days ago)
            cutoff = datetime.now(timezone.utc) - timedelta(days=3)
            deleted_count = 0

            cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S UTC")
            logger.info(f"Starting log cleanup - deleting messages older than {cutoff_str}")

            # Fetch messages from oldest to newest
            async for message in channel.history(limit=None, oldest_first=True):
                # Stop if we reach messages newer than cutoff
                if message.created_at >= cutoff:
                    break

                # Only delete bot's own messages
                if message.author == self.bot.user:
                    try:
                        await message.delete()
                        deleted_count += 1
                        await asyncio.sleep(1)  # Rate limit protection
                    except discord.errors.NotFound:
                        # Message already deleted
                        pass
                    except Exception as e:
                        logger.error(f"Failed to delete log message: {e}")

            logger.info(f"Log cleanup completed - deleted {deleted_count} old messages")

        except Exception as e:
            logger.error(f"Error during log cleanup: {e}")

    @cleanup_old_logs_task.before_loop
    async def before_cleanup_old_logs(self):
        """Wait for bot to be ready before starting the task"""
        await self.bot.wait_until_ready()

    @commands.command(name="togglediscordlogs")
    async def toggle_discord_logs(self, ctx: commands.Context):
        """
        🔧 Toggle Discord logging on/off (Admin only)
        Usage: !togglediscordlogs
        """
        if not any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles):
            embed = discord.Embed(
                description="🚫 You do not have permission to use this command.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=5)
            return

        self.enabled = not self.enabled
        status = "enabled ✅" if self.enabled else "disabled ❌"

        embed = discord.Embed(
            title="📡 Discord Logging",
            description=f"Discord logging has been **{status}**",
            color=PINK if self.enabled else discord.Color.red(),
        )
        await ctx.send(embed=embed)
        logger.info(f"Discord logging {status} by {ctx.author}")

    @commands.command(name="testdiscordlog")
    async def test_discord_log(self, ctx: commands.Context):
        """
        🧪 Test Discord logging with sample messages (Admin only)
        Usage: !testdiscordlog
        """
        if not any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles):
            embed = discord.Embed(
                description="🚫 You do not have permission to use this command.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=5)
            return

        embed = discord.Embed(
            title="🧪 Testing Discord Logging",
            description="Sending test log messages...",
            color=PINK,
        )
        await ctx.send(embed=embed)

        # Send test logs at different levels
        logger.debug("This is a DEBUG test message")
        logger.info("This is an INFO test message")
        logger.warning("This is a WARNING test message")
        logger.error("This is an ERROR test message")

        await asyncio.sleep(6)  # Wait for flush task
        await ctx.send("✅ Test logs sent! Check the log channel.")


async def setup(bot: commands.Bot):
    await bot.add_cog(DiscordLogging(bot))
