"""
Gaming Hub Cog - Manages game requests and persistent views
"""

import asyncio
import json
import logging
import os
from datetime import datetime

import discord
from discord.ext import commands, tasks

from Config import get_data_dir

logger = logging.getLogger(__name__)

GAME_REQUESTS_FILE = f"{get_data_dir()}/game_requests.json"


class GameRequestView(discord.ui.View):
    """Persistent view for game request buttons"""

    def __init__(self, requester_id: int, target_id: int, game_name: str, created_at: float):
        super().__init__(timeout=None)
        self.requester_id = requester_id
        self.target_id = target_id
        self.game_name = game_name
        self.created_at = created_at

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅", custom_id="game_request:accept")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only target can accept
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This request is not for you!", ephemeral=True)
            return

        # Update embed
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.add_field(
            name="✅ Accepted!",
            value=f"{interaction.user.mention} accepted the game request!",
            inline=False,
        )

        # Disable all buttons
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

        # Notify requester
        requester = interaction.guild.get_member(self.requester_id)
        if requester:
            try:
                await requester.send(
                    f"🎮 **{interaction.user.display_name}** accepted your game request!\n"
                    f"Game: **{self.game_name}**\n"
                    f"Jump to message: {interaction.message.jump_url}"
                )
            except Exception:
                pass  # User has DMs disabled

        # Remove from persistent storage
        cog = interaction.client.get_cog("GamingHub")
        if cog:
            cog._remove_game_request(interaction.channel.id, interaction.message.id)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌", custom_id="game_request:decline")
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only target can decline
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This request is not for you!", ephemeral=True)
            return

        # Update embed
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.add_field(
            name="❌ Declined",
            value=f"{interaction.user.mention} declined the game request.",
            inline=False,
        )

        # Disable all buttons
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

        # Notify requester
        requester = interaction.guild.get_member(self.requester_id)
        if requester:
            try:
                await requester.send(
                    f"🎮 **{interaction.user.display_name}** declined your game request.\n"
                    f"Game: **{self.game_name}**\n"
                    f"Maybe they're busy right now. Try again later!"
                )
            except Exception:
                pass  # User has DMs disabled

        # Remove from persistent storage
        cog = interaction.client.get_cog("GamingHub")
        if cog:
            cog._remove_game_request(interaction.channel.id, interaction.message.id)

    @discord.ui.button(
        label="Maybe Later", style=discord.ButtonStyle.secondary, emoji="⏰", custom_id="game_request:maybe"
    )
    async def maybe_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only target can respond
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This request is not for you!", ephemeral=True)
            return

        # Update embed
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.orange()
        embed.add_field(
            name="⏰ Maybe Later",
            value=f"{interaction.user.mention} might be interested later!",
            inline=False,
        )

        # Disable all buttons
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

        # Notify requester
        requester = interaction.guild.get_member(self.requester_id)
        if requester:
            try:
                await requester.send(
                    f"🎮 **{interaction.user.display_name}** might be interested later!\n"
                    f"Game: **{self.game_name}**\n"
                    f"Check back with them soon!"
                )
            except Exception:
                pass  # User has DMs disabled

        # Remove from persistent storage
        cog = interaction.client.get_cog("GamingHub")
        if cog:
            cog._remove_game_request(interaction.channel.id, interaction.message.id)


class GamingHub(commands.Cog):
    """Cog for managing gaming hub features and persistent game request views"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.game_requests_file = GAME_REQUESTS_FILE
        self.game_requests_data = []

        # Load game requests data
        if os.path.exists(self.game_requests_file):
            try:
                with open(self.game_requests_file, "r", encoding="utf-8") as f:
                    self.game_requests_data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load game requests data: {e}")
                self.game_requests_data = []
        else:
            os.makedirs(os.path.dirname(self.game_requests_file), exist_ok=True)
            self.game_requests_data = []

    async def cog_load(self) -> None:
        """Called when the cog is loaded (including reloads)."""
        if self.bot.is_ready():
            await self._restore_game_request_views()
            self.cleanup_expired_requests.start()

    async def cog_unload(self) -> None:
        """Called when the cog is unloaded."""
        self.cleanup_expired_requests.cancel()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Restore game request views when the bot is ready."""
        await self._restore_game_request_views()
        if not self.cleanup_expired_requests.is_running():
            self.cleanup_expired_requests.start()

    async def _restore_game_request_views(self) -> None:
        """Restore persistent game request views."""
        restored_count = 0
        cleaned_data = []
        from Config import get_local_now
        now = get_local_now().timestamp()

        for request_data in self.game_requests_data:
            channel_id = request_data.get("channel_id")
            message_id = request_data.get("message_id")
            requester_id = request_data.get("requester_id")
            target_id = request_data.get("target_id")
            game_name = request_data.get("game_name")
            created_at = request_data.get("created_at", now)

            if not all([channel_id, message_id, requester_id, target_id, game_name]):
                continue

            # Check if expired (7 days)
            if now - created_at > 7 * 24 * 3600:
                logger.info(f"Game request {message_id} expired (7 days old), removing from persistent storage")
                continue

            channel = self.bot.get_channel(channel_id)
            if not channel:
                logger.warning(f"Channel {channel_id} not found, skipping game request restoration")
                continue

            try:
                message = await channel.fetch_message(message_id)

                # Create and attach the view without editing the message
                view = GameRequestView(requester_id, target_id, game_name, created_at)
                self.bot.add_view(view, message_id=message_id)

                restored_count += 1
                cleaned_data.append(request_data)
                logger.info(f"Restored game request view for message {message_id} in channel {channel_id}")

                await asyncio.sleep(0.2)  # Rate limit protection

            except discord.NotFound:
                logger.warning(f"Message {message_id} not found, removing from game requests")
            except Exception as e:
                logger.error(f"Failed to restore game request view for message {message_id}: {e}")
                cleaned_data.append(request_data)  # Keep on other errors

        # Save cleaned data
        self.game_requests_data = cleaned_data
        self._save_game_requests()

        logger.info(f"Restored {restored_count} persistent game request views")

    def save_game_request(
        self, channel_id: int, message_id: int, requester_id: int, target_id: int, game_name: str
    ) -> None:
        """Save a game request to persistent storage."""
        # Check if already exists
        for request_data in self.game_requests_data:
            if request_data.get("channel_id") == channel_id and request_data.get("message_id") == message_id:
                logger.info(f"Game request for message {message_id} already in persistent storage")
                return

        # Add new entry
        from Config import get_local_now
        self.game_requests_data.append(
            {
                "channel_id": channel_id,
                "message_id": message_id,
                "requester_id": requester_id,
                "target_id": target_id,
                "game_name": game_name,
                "created_at": get_local_now().timestamp(),
            }
        )

        self._save_game_requests()
        logger.info(f"Saved game request for message {message_id} in channel {channel_id}")

    def _remove_game_request(self, channel_id: int, message_id: int) -> None:
        """Remove a game request from persistent storage."""
        original_count = len(self.game_requests_data)
        self.game_requests_data = [
            request_data
            for request_data in self.game_requests_data
            if not (request_data.get("channel_id") == channel_id and request_data.get("message_id") == message_id)
        ]

        if len(self.game_requests_data) < original_count:
            self._save_game_requests()
            logger.info(f"Removed game request for message {message_id}")

    def _save_game_requests(self) -> None:
        """Save game requests data to file."""
        try:
            with open(self.game_requests_file, "w", encoding="utf-8") as f:
                json.dump(self.game_requests_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save game requests: {e}")

    @tasks.loop(hours=6)
    async def cleanup_expired_requests(self):
        """Clean up expired game requests (older than 7 days)"""
        from Config import get_local_now
        now = get_local_now().timestamp()
        cleaned_count = 0

        for request_data in list(self.game_requests_data):
            created_at = request_data.get("created_at", now)
            message_id = request_data.get("message_id")
            channel_id = request_data.get("channel_id")

            # Check if expired (7 days)
            if now - created_at > 7 * 24 * 3600:
                self._remove_game_request(channel_id, message_id)
                cleaned_count += 1

        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired game requests")

    @cleanup_expired_requests.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GamingHub(bot))
