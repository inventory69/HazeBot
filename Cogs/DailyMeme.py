import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import os
import json
import random
from datetime import datetime, time
import logging
import asyncio
from bs4 import BeautifulSoup

from Config import (
    PINK,
    get_guild_id,
    get_data_dir,
    MEME_CHANNEL_ID,
    MEME_ROLE_ID,
    MEME_SUBREDDITS_FILE,
    DEFAULT_MEME_SUBREDDITS,
    MEME_LEMMY_FILE,
    DEFAULT_MEME_LEMMY,
    MEME_SOURCES,
    ADMIN_ROLE_ID,
    MODERATOR_ROLE_ID,
)
from Utils.EmbedUtils import set_pink_footer

logger = logging.getLogger(__name__)


def is_mod_or_admin(member: discord.Member) -> bool:
    """Check if member is a moderator or administrator"""
    return any(role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in member.roles)


class MemeHubView(discord.ui.View):
    """Interactive Meme Hub with buttons for users and mods"""

    def __init__(self, cog: "DailyMeme", is_admin_or_mod: bool):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.user_cooldowns = {}  # user_id -> last_use_timestamp
        self.cooldown_seconds = 10  # 10 second cooldown for regular users

        # Add "Choose Source" button for all users
        self.add_item(ChooseSourceButton())

        # Add management buttons only for mods/admins
        if is_admin_or_mod:
            self.add_item(SubredditManagementButton())
            self.add_item(LemmyManagementButton())
            self.add_item(SourceManagementButton())
            self.add_item(TestMemeButton())

    @discord.ui.button(label="🎭 Get Random Meme", style=discord.ButtonStyle.primary, row=0)
    async def get_meme_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button for all users to get a random meme (with rate limiting)"""
        user_id = interaction.user.id
        current_time = datetime.now().timestamp()

        # Check cooldown (skip for mods/admins)
        if not is_mod_or_admin(interaction.user):
            last_use = self.user_cooldowns.get(user_id, 0)
            if current_time - last_use < self.cooldown_seconds:
                remaining = int(self.cooldown_seconds - (current_time - last_use))
                await interaction.response.send_message(
                    f"⏳ Please wait {remaining} seconds before requesting another meme!", ephemeral=True
                )
                return

        # Update cooldown
        self.user_cooldowns[user_id] = current_time

        # Send loading message
        await interaction.response.send_message(
            "🔍 Fetching a fresh meme... Can take a little while, cause we do hidden / forbidden voodoo magic.",
            ephemeral=True,
        )

        # Fetch meme
        meme, embed = await self.cog.fetch_meme_and_create_embed()

        if meme and embed:
            await interaction.followup.send(embed=embed)
            source_name = meme.get("subreddit", "unknown")
            if source_name not in ["9gag"]:
                source_name = f"r/{source_name}"
            logger.info(f"Meme Hub: Meme requested by {interaction.user} from {source_name}")
        else:
            await interaction.followup.send("❌ Couldn't fetch a meme right now. Try again later!", ephemeral=True)


class ChooseSourceButton(discord.ui.Button):
    """Button to choose specific source (subreddit or Lemmy community)"""

    def __init__(self):
        super().__init__(label="🎯 Choose Source", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        cog: DailyMeme = interaction.client.get_cog("DailyMeme")

        embed = discord.Embed(
            title="🎯 Choose Meme Source",
            description="Select a specific subreddit or Lemmy community to fetch memes from.",
            color=PINK,
        )

        set_pink_footer(embed, bot=interaction.client.user)
        view = SourceSelectionView(cog)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class SourceSelectionView(discord.ui.View):
    """View with select menus for choosing subreddit or Lemmy community"""

    def __init__(self, cog: "DailyMeme"):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_cooldowns = {}
        self.cooldown_seconds = 10

        # Add Reddit subreddit select
        reddit_options = [
            discord.SelectOption(label=f"r/{sub}", value=f"reddit:{sub}", emoji="🔥")
            for sub in sorted(cog.meme_subreddits)[:25]  # Discord limit: 25 options
        ]
        if reddit_options:
            reddit_select = discord.ui.Select(
                placeholder="Choose a Reddit subreddit...",
                options=reddit_options,
                row=0,
            )
            reddit_select.callback = self._create_fetch_callback("reddit")
            self.add_item(reddit_select)

        # Add Lemmy community select
        lemmy_options = [
            discord.SelectOption(label=comm, value=f"lemmy:{comm}", emoji="🌐") for comm in sorted(cog.meme_lemmy)[:25]
        ]
        if lemmy_options:
            lemmy_select = discord.ui.Select(
                placeholder="Choose a Lemmy community...",
                options=lemmy_options,
                row=1,
            )
            lemmy_select.callback = self._create_fetch_callback("lemmy")
            self.add_item(lemmy_select)

    def _create_fetch_callback(self, source_type: str):
        """Create callback for fetching meme from selected source"""

        async def callback(interaction: discord.Interaction):
            user_id = interaction.user.id
            current_time = datetime.now().timestamp()

            # Check cooldown (skip for mods/admins)
            if not is_mod_or_admin(interaction.user):
                last_use = self.user_cooldowns.get(user_id, 0)
                if current_time - last_use < self.cooldown_seconds:
                    remaining = int(self.cooldown_seconds - (current_time - last_use))
                    await interaction.response.send_message(
                        f"⏳ Please wait {remaining} seconds before requesting another meme!", ephemeral=True
                    )
                    return

            # Update cooldown
            self.user_cooldowns[user_id] = current_time

            # Get selected value
            selected = interaction.data["values"][0]  # e.g., "reddit:memes" or "lemmy:lemmy.world@memes"
            source_type, source_name = selected.split(":", 1)

            # Send loading message
            await interaction.response.send_message(
                f"🔍 Fetching meme from {source_name}...",
                ephemeral=True,
            )

            # Fetch meme from specific source
            if source_type == "reddit":
                memes = await self.cog.fetch_reddit_meme(source_name)
            elif source_type == "lemmy":
                memes = await self.cog.fetch_lemmy_meme(source_name)
            else:
                await interaction.followup.send("❌ Unknown source type!", ephemeral=True)
                return

            if not memes:
                await interaction.followup.send(
                    f"❌ No memes found from {source_name}. Try another source!", ephemeral=True
                )
                return

            # Pick random meme and create embed
            meme = random.choice(memes)
            embed = discord.Embed(
                title=meme.get("title", "Meme"),
                url=meme.get("url"),
                color=PINK,
            )
            embed.set_image(url=meme.get("url"))

            # Set source info
            if source_type == "lemmy":
                source_display = source_name
            else:
                source_display = f"r/{source_name}"

            embed.add_field(name="📍 Source", value=source_display, inline=True)
            embed.add_field(name="👤 Author", value=meme.get("author", "Unknown"), inline=True)
            embed.add_field(name="⬆️ Score", value=f"{meme.get('score', 0):,}", inline=True)

            set_pink_footer(embed, bot=interaction.client.user)

            await interaction.followup.send(embed=embed)
            logger.info(f"Specific meme fetched by {interaction.user} from {source_name}")

        return callback


class SubredditManagementView(discord.ui.View):
    """Interactive view for subreddit management"""

    def __init__(self, cog: "DailyMeme"):
        super().__init__(timeout=300)
        self.cog = cog

    @discord.ui.button(label="➕ Add Subreddit", style=discord.ButtonStyle.success, row=0)
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a new subreddit via modal"""
        modal = AddSubredditModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="➖ Remove Subreddit", style=discord.ButtonStyle.danger, row=0)
    async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Remove a subreddit via modal"""
        modal = RemoveSubredditModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🔄 Reset to Defaults", style=discord.ButtonStyle.secondary, row=0)
    async def reset_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reset subreddits to defaults"""
        self.cog.meme_subreddits = DEFAULT_MEME_SUBREDDITS.copy()
        self.cog.save_subreddits()

        await interaction.response.send_message(
            f"✅ Reset to {len(self.cog.meme_subreddits)} default subreddits!", ephemeral=True
        )
        logger.info(f"Subreddits reset by {interaction.user}")


class AddSubredditModal(discord.ui.Modal, title="Add Subreddit"):
    """Modal for adding a subreddit"""

    subreddit_input = discord.ui.TextInput(
        label="Subreddit Name", placeholder="Enter subreddit name (without r/)", required=True, max_length=50
    )

    def __init__(self, cog: "DailyMeme"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        subreddit = self.subreddit_input.value.lower().strip().replace("r/", "")

        if subreddit in self.cog.meme_subreddits:
            await interaction.response.send_message(f"❌ r/{subreddit} is already in the list!", ephemeral=True)
            return

        self.cog.meme_subreddits.append(subreddit)
        self.cog.save_subreddits()

        await interaction.response.send_message(
            f"✅ Added r/{subreddit}! Now using {len(self.cog.meme_subreddits)} subreddits.", ephemeral=True
        )
        logger.info(f"Subreddit r/{subreddit} added by {interaction.user}")


class RemoveSubredditModal(discord.ui.Modal, title="Remove Subreddit"):
    """Modal for removing a subreddit"""

    subreddit_input = discord.ui.TextInput(
        label="Subreddit Name", placeholder="Enter subreddit name to remove (without r/)", required=True, max_length=50
    )

    def __init__(self, cog: "DailyMeme"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        subreddit = self.subreddit_input.value.lower().strip().replace("r/", "")

        if subreddit not in self.cog.meme_subreddits:
            await interaction.response.send_message(f"❌ r/{subreddit} is not in the list!", ephemeral=True)
            return

        if len(self.cog.meme_subreddits) <= 1:
            await interaction.response.send_message("❌ Cannot remove the last subreddit!", ephemeral=True)
            return

        self.cog.meme_subreddits.remove(subreddit)
        self.cog.save_subreddits()

        await interaction.response.send_message(
            f"✅ Removed r/{subreddit}! Now using {len(self.cog.meme_subreddits)} subreddits.", ephemeral=True
        )
        logger.info(f"Subreddit r/{subreddit} removed by {interaction.user}")


class LemmyManagementView(discord.ui.View):
    """Interactive view for Lemmy community management"""

    def __init__(self, cog: "DailyMeme"):
        super().__init__(timeout=300)
        self.cog = cog

    @discord.ui.button(label="➕ Add Community", style=discord.ButtonStyle.success, row=0)
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a new Lemmy community via modal"""
        modal = AddLemmyModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="➖ Remove Community", style=discord.ButtonStyle.danger, row=0)
    async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Remove a Lemmy community via modal"""
        modal = RemoveLemmyModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🔄 Reset to Defaults", style=discord.ButtonStyle.secondary, row=0)
    async def reset_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reset Lemmy communities to defaults"""
        self.cog.meme_lemmy = DEFAULT_MEME_LEMMY.copy()
        self.cog.save_lemmy_communities()

        await interaction.response.send_message(
            f"✅ Reset to {len(self.cog.meme_lemmy)} default Lemmy communities!", ephemeral=True
        )
        logger.info(f"Lemmy communities reset by {interaction.user}")


class AddLemmyModal(discord.ui.Modal, title="Add Lemmy Community"):
    """Modal for adding a Lemmy community"""

    community_input = discord.ui.TextInput(
        label="Community",
        placeholder="Enter instance@community (e.g., lemmy.world@memes)",
        required=True,
        max_length=100,
    )

    def __init__(self, cog: "DailyMeme"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        community = self.community_input.value.lower().strip()

        # Validate format
        if "@" not in community:
            await interaction.response.send_message(
                "❌ Invalid format! Use instance@community (e.g., lemmy.world@memes)", ephemeral=True
            )
            return

        if community in self.cog.meme_lemmy:
            await interaction.response.send_message(f"❌ {community} is already in the list!", ephemeral=True)
            return

        self.cog.meme_lemmy.append(community)
        self.cog.save_lemmy_communities()

        await interaction.response.send_message(
            f"✅ Added {community}! Now using {len(self.cog.meme_lemmy)} Lemmy communities.", ephemeral=True
        )
        logger.info(f"Lemmy community {community} added by {interaction.user}")


class RemoveLemmyModal(discord.ui.Modal, title="Remove Lemmy Community"):
    """Modal for removing a Lemmy community"""

    community_input = discord.ui.TextInput(
        label="Community",
        placeholder="Enter instance@community to remove",
        required=True,
        max_length=100,
    )

    def __init__(self, cog: "DailyMeme"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        community = self.community_input.value.lower().strip()

        if community not in self.cog.meme_lemmy:
            await interaction.response.send_message(f"❌ {community} is not in the list!", ephemeral=True)
            return

        if len(self.cog.meme_lemmy) <= 1:
            await interaction.response.send_message("❌ Cannot remove the last Lemmy community!", ephemeral=True)
            return

        self.cog.meme_lemmy.remove(community)
        self.cog.save_lemmy_communities()

        await interaction.response.send_message(
            f"✅ Removed {community}! Now using {len(self.cog.meme_lemmy)} Lemmy communities.", ephemeral=True
        )
        logger.info(f"Lemmy community {community} removed by {interaction.user}")


class SourceManagementView(discord.ui.View):
    """Interactive view for source management"""

    def __init__(self, cog: "DailyMeme"):
        super().__init__(timeout=300)
        self.cog = cog
        self._update_buttons()

    def _update_buttons(self):
        """Update button states based on current sources"""
        self.clear_items()

        # Add toggle buttons for each source
        # Note: Can be extended with more sources in the future
        source_info = [("reddit", "🔥 Reddit"), ("lemmy", "🌐 Lemmy")]

        for source_id, source_name in source_info:
            enabled = source_id in self.cog.meme_sources
            button = discord.ui.Button(
                label=f"{'✅' if enabled else '❌'} {source_name}",
                style=discord.ButtonStyle.success if enabled else discord.ButtonStyle.secondary,
                custom_id=f"toggle_{source_id}",
                row=0,
            )
            button.callback = self._create_toggle_callback(source_id, source_name)
            self.add_item(button)

        # Add reset button
        reset_btn = discord.ui.Button(label="🔄 Reset to Defaults", style=discord.ButtonStyle.danger, row=2)
        reset_btn.callback = self._reset_callback
        self.add_item(reset_btn)

    def _create_toggle_callback(self, source_id: str, source_name: str):
        """Create callback for toggling a source"""

        async def callback(interaction: discord.Interaction):
            if source_id in self.cog.meme_sources:
                # Disable source
                if len(self.cog.meme_sources) <= 1:
                    await interaction.response.send_message("❌ Cannot disable the last source!", ephemeral=True)
                    return

                self.cog.meme_sources.remove(source_id)
                self.cog.save_sources()
                await interaction.response.send_message(f"❌ Disabled {source_name}", ephemeral=True)
                logger.info(f"Source {source_id} disabled by {interaction.user}")
            else:
                # Enable source
                self.cog.meme_sources.append(source_id)
                self.cog.save_sources()
                await interaction.response.send_message(f"✅ Enabled {source_name}", ephemeral=True)
                logger.info(f"Source {source_id} enabled by {interaction.user}")

            # Update buttons to reflect new state
            self._update_buttons()
            await interaction.message.edit(view=self)

        return callback

    async def _reset_callback(self, interaction: discord.Interaction):
        """Reset sources to defaults"""
        self.cog.meme_sources = MEME_SOURCES.copy()
        self.cog.save_sources()

        await interaction.response.send_message(
            f"✅ Reset to {len(self.cog.meme_sources)} default sources!", ephemeral=True
        )
        logger.info(f"Sources reset by {interaction.user}")

        # Update buttons
        self._update_buttons()
        await interaction.message.edit(view=self)


class SubredditManagementButton(discord.ui.Button):
    """Button to manage subreddits (Mod/Admin only)"""

    def __init__(self):
        super().__init__(label="📋 Manage Subreddits", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        cog: DailyMeme = interaction.client.get_cog("DailyMeme")

        embed = discord.Embed(
            title="🎭 Subreddit Management",
            description=f"Currently using **{len(cog.meme_subreddits)}** subreddits.",
            color=PINK,
        )

        subreddit_list = "\n".join([f"• r/{sub}" for sub in sorted(cog.meme_subreddits)])
        embed.add_field(name="📍 Active Subreddits", value=subreddit_list[:1024] or "None", inline=False)

        embed.add_field(
            name="💡 Use the buttons below to manage",
            value="Add, remove, or reset subreddits",
            inline=False,
        )

        set_pink_footer(embed, bot=interaction.client.user)
        view = SubredditManagementView(cog)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class LemmyManagementButton(discord.ui.Button):
    """Button to manage Lemmy communities (Mod/Admin only)"""

    def __init__(self):
        super().__init__(label="🌐 Manage Lemmy", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        cog: DailyMeme = interaction.client.get_cog("DailyMeme")

        embed = discord.Embed(
            title="🎭 Lemmy Community Management",
            description=f"Currently using **{len(cog.meme_lemmy)}** Lemmy communities.",
            color=PINK,
        )

        community_list = "\n".join([f"• {comm}" for comm in sorted(cog.meme_lemmy)])
        embed.add_field(name="📍 Active Communities", value=community_list[:1024] or "None", inline=False)

        embed.add_field(
            name="💡 Use the buttons below to manage",
            value="Add, remove, or reset Lemmy communities\nFormat: instance@community (e.g., lemmy.world@memes)",
            inline=False,
        )

        set_pink_footer(embed, bot=interaction.client.user)
        view = LemmyManagementView(cog)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class SourceManagementButton(discord.ui.Button):
    """Button to manage meme sources (Mod/Admin only)"""

    def __init__(self):
        super().__init__(label="🌐 Manage Sources", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        cog: DailyMeme = interaction.client.get_cog("DailyMeme")

        embed = discord.Embed(
            title="🎭 Source Management",
            description=f"Currently using **{len(cog.meme_sources)}** meme sources.",
            color=PINK,
        )

        # Note: source_display can be extended when adding new sources
        source_display = {"reddit": "🔥 Reddit", "lemmy": "🌐 Lemmy"}

        enabled_list = "\n".join([f"• {source_display.get(src, src)}" for src in cog.meme_sources])
        embed.add_field(name="✅ Enabled", value=enabled_list or "None", inline=False)

        all_sources = ["reddit", "lemmy"]  # Extend this list when adding new sources
        disabled = [src for src in all_sources if src not in cog.meme_sources]
        if disabled:
            disabled_list = "\n".join([f"• {source_display.get(src, src)}" for src in disabled])
            embed.add_field(name="❌ Disabled", value=disabled_list, inline=False)

        embed.add_field(
            name="💡 Use the buttons below to toggle",
            value="Click to enable/disable sources\nMore sources can be added in the future",
            inline=False,
        )

        set_pink_footer(embed, bot=interaction.client.user)
        view = SourceManagementView(cog)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class TestMemeButton(discord.ui.Button):
    """Button to test daily meme function (Mod/Admin only)"""

    def __init__(self):
        super().__init__(label="🧪 Test Daily Meme", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("🧪 Testing daily meme function...", ephemeral=True)

        cog: DailyMeme = interaction.client.get_cog("DailyMeme")
        guild = interaction.guild
        channel = guild.get_channel(MEME_CHANNEL_ID)

        if not channel:
            await interaction.followup.send(f"❌ Meme channel {MEME_CHANNEL_ID} not found", ephemeral=True)
            return

        meme = await cog.get_daily_meme(allow_nsfw=True)

        if meme:
            await cog.post_meme(meme, channel)
            await interaction.followup.send("✅ Test meme posted successfully!", ephemeral=True)
            logger.info(f"Test meme posted by {interaction.user}")
        else:
            await interaction.followup.send("❌ Failed to fetch test meme", ephemeral=True)


class DailyMeme(commands.Cog):
    """
    🎭 Daily Meme Cog: Posts trending memes from multiple sources (Reddit, Lemmy)
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session = None
        self.subreddits_file = MEME_SUBREDDITS_FILE
        self.lemmy_file = MEME_LEMMY_FILE
        self.sources_file = os.path.join(get_data_dir(), "meme_sources.json")
        self._setup_done = False
        # Load subreddits from file or use defaults
        self.meme_subreddits = self.load_subreddits()
        # Load Lemmy communities from file or use defaults
        self.meme_lemmy = self.load_lemmy_communities()
        # Load meme sources from file or use defaults
        self.meme_sources = self.load_sources()
        # FlareSolverr for bypassing anti-bot measures (for future sources if needed)
        self.flaresolverr_url = os.getenv("FLARESOLVERR_URL")
        # Ensure HTTPS is used for FlareSolverr
        if self.flaresolverr_url and self.flaresolverr_url.startswith("http://"):
            self.flaresolverr_url = self.flaresolverr_url.replace("http://", "https://", 1)
            logger.warning(f"⚠️ FlareSolverr URL converted from HTTP to HTTPS: {self.flaresolverr_url}")
        # Rate limiting for FlareSolverr requests (30 seconds between calls)
        self._flaresolverr_lock = asyncio.Lock()
        self._last_flaresolverr_call = 0
        # Cache for shown memes (URL -> timestamp)
        self.meme_cache_hours = 24  # Keep memes in cache for 24 hours
        self.shown_memes_file = os.path.join(get_data_dir(), "shown_memes.json")
        self.shown_memes = self.load_shown_memes()

    def load_subreddits(self) -> list:
        """Load subreddit list from file or return defaults"""
        try:
            if os.path.exists(self.subreddits_file):
                with open(self.subreddits_file, "r") as f:
                    data = json.load(f)
                    subreddits = data.get("subreddits", DEFAULT_MEME_SUBREDDITS)
                    return subreddits
        except Exception as e:
            logger.error(f"Error loading subreddits: {e}")

        return DEFAULT_MEME_SUBREDDITS.copy()

    def save_subreddits(self) -> None:
        """Save current subreddit list to file"""
        try:
            os.makedirs(os.path.dirname(self.subreddits_file), exist_ok=True)
            with open(self.subreddits_file, "w") as f:
                json.dump({"subreddits": self.meme_subreddits}, f, indent=4)
            logger.info(f"Saved {len(self.meme_subreddits)} subreddits to config")
        except Exception as e:
            logger.error(f"Error saving subreddits: {e}")

    def load_lemmy_communities(self) -> list:
        """Load Lemmy communities from file or return defaults"""
        try:
            if os.path.exists(self.lemmy_file):
                with open(self.lemmy_file, "r") as f:
                    data = json.load(f)
                    communities = data.get("communities", DEFAULT_MEME_LEMMY)
                    return communities
        except Exception as e:
            logger.error(f"Error loading Lemmy communities: {e}")

        return DEFAULT_MEME_LEMMY.copy()

    def save_lemmy_communities(self) -> None:
        """Save current Lemmy community list to file"""
        try:
            os.makedirs(os.path.dirname(self.lemmy_file), exist_ok=True)
            with open(self.lemmy_file, "w") as f:
                json.dump({"communities": self.meme_lemmy}, f, indent=4)
            logger.info(f"Saved {len(self.meme_lemmy)} Lemmy communities to config")
        except Exception as e:
            logger.error(f"Error saving Lemmy communities: {e}")

    def load_sources(self) -> list:
        """Load meme sources from file or return defaults"""
        try:
            if os.path.exists(self.sources_file):
                with open(self.sources_file, "r") as f:
                    data = json.load(f)
                    sources = data.get("sources", MEME_SOURCES)
                    # Validate sources against available sources
                    valid_sources = ["reddit", "lemmy"]  # Extend when adding new sources
                    sources = [s for s in sources if s in valid_sources]
                    return sources if sources else MEME_SOURCES.copy()
        except Exception as e:
            logger.error(f"Error loading sources: {e}")

        return MEME_SOURCES.copy()

    def save_sources(self) -> None:
        """Save current source list to file"""
        try:
            os.makedirs(os.path.dirname(self.sources_file), exist_ok=True)
            with open(self.sources_file, "w") as f:
                json.dump({"sources": self.meme_sources}, f, indent=4)
            logger.info(f"Saved {len(self.meme_sources)} meme sources to config")
        except Exception as e:
            logger.error(f"Error saving sources: {e}")

    def load_shown_memes(self) -> dict:
        """Load shown memes cache from file"""
        try:
            if os.path.exists(self.shown_memes_file):
                with open(self.shown_memes_file, "r") as f:
                    data = json.load(f)
                    # Clean old entries (older than cache hours)
                    current_time = datetime.now().timestamp()
                    cache_seconds = self.meme_cache_hours * 3600
                    cleaned = {
                        url: timestamp for url, timestamp in data.items() if current_time - timestamp < cache_seconds
                    }
                    return cleaned
        except Exception as e:
            logger.error(f"Error loading shown memes cache: {e}")
        return {}

    def save_shown_memes(self) -> None:
        """Save shown memes cache to file"""
        try:
            os.makedirs(os.path.dirname(self.shown_memes_file), exist_ok=True)
            with open(self.shown_memes_file, "w") as f:
                json.dump(self.shown_memes, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving shown memes cache: {e}")

    def is_meme_shown_recently(self, url: str) -> bool:
        """Check if a meme was shown recently"""
        if url not in self.shown_memes:
            return False

        current_time = datetime.now().timestamp()
        cache_seconds = self.meme_cache_hours * 3600

        # Check if still in cache window
        if current_time - self.shown_memes[url] < cache_seconds:
            return True
        else:
            # Remove expired entry
            del self.shown_memes[url]
            return False

    def mark_meme_as_shown(self, url: str) -> None:
        """Mark a meme as shown"""
        self.shown_memes[url] = datetime.now().timestamp()
        self.save_shown_memes()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Set up Daily Meme when bot is ready"""
        if self._setup_done:
            return  # Only setup once

        self._setup_done = True

        # Create HTTP session
        self.session = aiohttp.ClientSession()

        # Start the daily meme task
        if not self.daily_meme_task.is_running():
            self.daily_meme_task.start()

            # Log configuration
            if os.path.exists(self.subreddits_file):
                logger.info(f"Loaded {len(self.meme_subreddits)} subreddits from config")
            else:
                logger.info(f"Using default {len(self.meme_subreddits)} subreddits")

            # Load Lemmy communities
            if os.path.exists(self.lemmy_file):
                logger.info(f"Loaded {len(self.meme_lemmy)} Lemmy communities from config")
            else:
                logger.info(f"Using default {len(self.meme_lemmy)} Lemmy communities")

            # Log enabled meme sources
            sources_str = ", ".join(self.meme_sources)
            logger.info(f"Enabled meme sources: {sources_str}")

            # FlareSolverr check - Required for Reddit (always returns 403) and other sources
            if "reddit" in self.meme_sources or any(src in self.meme_sources for src in ["9gag", "4chan"]):
                if self.flaresolverr_url:
                    logger.info(f"FlareSolverr configured: {self.flaresolverr_url}")
                else:
                    logger.warning("⚠️ FlareSolverr required for Reddit but URL not configured!")

            logger.info(f"Daily meme scheduled for 12:00 PM daily (Channel: {MEME_CHANNEL_ID})")
            logger.info("Daily Meme task started")

    async def cog_unload(self):
        """Called when the cog is unloaded"""
        if self.daily_meme_task.is_running():
            self.daily_meme_task.cancel()
            logger.info("Daily Meme task cancelled")

        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("HTTP session closed")

    async def _fetch_with_flaresolverr(self, url: str, timeout: int = 60000) -> dict:
        """
        Fetch URL using FlareSolverr with rate limiting (30 seconds between calls)

        Args:
            url: The URL to fetch
            timeout: FlareSolverr maxTimeout in milliseconds

        Returns:
            dict with 'status' and 'response' keys, or None on error
        """
        if not self.flaresolverr_url:
            logger.warning("FlareSolverr URL not configured")
            return None

        async with self._flaresolverr_lock:
            # Rate limiting: 30 seconds between FlareSolverr calls
            current_time = asyncio.get_event_loop().time()
            time_since_last_call = current_time - self._last_flaresolverr_call

            if time_since_last_call < 30:
                wait_time = 30 - time_since_last_call
                logger.debug(f"Rate limiting: waiting {wait_time:.1f}s before FlareSolverr call")
                await asyncio.sleep(wait_time)

            payload = {
                "cmd": "request.get",
                "url": url,
                "maxTimeout": timeout,
            }

            try:
                async with self.session.post(self.flaresolverr_url, json=payload, timeout=65) as response:
                    self._last_flaresolverr_call = asyncio.get_event_loop().time()

                    if response.status != 200:
                        logger.warning(f"FlareSolverr returned {response.status}")
                        return None

                    data = await response.json()
                    if data.get("status") != "ok":
                        logger.warning(f"FlareSolverr failed: {data.get('message')}")
                        return None

                    # Get the response text from FlareSolverr
                    solution = data.get("solution", {})
                    response_text = solution.get("response")
                    
                    if not response_text:
                        logger.warning("No response content from FlareSolverr")
                        logger.debug(f"Full FlareSolverr response: {data}")
                        return None
                    
                    # Debug: Log response type and preview
                    logger.debug(f"FlareSolverr response type: {type(response_text)}, length: {len(response_text) if response_text else 0}")
                    logger.debug(f"Response preview (first 200): {response_text[:200] if response_text else 'None'}")

                    return {"status": "ok", "response": response_text}

            except asyncio.TimeoutError:
                logger.error(f"FlareSolverr timeout for {url}")
                self._last_flaresolverr_call = asyncio.get_event_loop().time()
                return None
            except Exception as e:
                logger.error(f"FlareSolverr error: {e}")
                self._last_flaresolverr_call = asyncio.get_event_loop().time()
                return None

    async def fetch_reddit_meme(self, subreddit: str, sort: str = "hot") -> dict:
        """
        Fetch a meme from Reddit using FlareSolverr (Reddit blocks direct API access)
        sort: hot, top, new
        """
        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit=50&t=day"

        try:
            # Use FlareSolverr directly since Reddit always returns 403
            if not self.flaresolverr_url:
                logger.error("FlareSolverr not configured, cannot fetch from Reddit")
                return None
            
            logger.debug(f"Fetching r/{subreddit} via FlareSolverr...")
            flare_response = await self._fetch_with_flaresolverr(url)
            
            if not flare_response or flare_response.get("status") != "ok":
                logger.error(f"FlareSolverr failed for r/{subreddit}")
                return None
            
            # Parse JSON from response
            response_text = flare_response.get("response", "")
            
            # FlareSolverr might return HTML instead of JSON if Reddit blocks it
            # Try to extract JSON from the response
            if not response_text or not response_text.strip():
                logger.error(f"Empty response from FlareSolverr for r/{subreddit}")
                return None
            
            # Check if response is HTML (starts with <!DOCTYPE or <html)
            if response_text.strip().startswith(('<', '<!DOCTYPE', '<!doctype')):
                logger.debug(f"FlareSolverr returned HTML for r/{subreddit}, attempting to extract JSON from <pre> tag")
                
                # Parse HTML and extract JSON from <pre> tag (Reddit returns JSON in HTML)
                soup = BeautifulSoup(response_text, "html.parser")
                pre_tag = soup.find("pre")
                
                if not pre_tag or not pre_tag.text.strip():
                    logger.error(f"No <pre> tag found in HTML response for r/{subreddit}")
                    logger.debug(f"HTML preview: {response_text[:500]}...")
                    return None
                
                response_text = pre_tag.text.strip()
                logger.debug(f"Extracted JSON from <pre> tag, length: {len(response_text)}")
            
            try:
                # FlareSolverr returns the JSON response as text
                data = json.loads(response_text)
                logger.debug(f"Successfully parsed JSON from r/{subreddit}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from FlareSolverr response for r/{subreddit}: {e}")
                logger.debug(f"Response preview (first 500 chars): {response_text[:500]}...")
                logger.debug(f"Response preview (last 200 chars): ...{response_text[-200:]}")
                return None

            posts = data["data"]["children"]

            # Filter for image posts only
            image_posts = []
            for post in posts:
                post_data = post["data"]
                # Skip stickied posts, videos, and galleries
                if post_data.get("stickied") or post_data.get("is_video") or post_data.get("is_gallery"):
                    continue

                # Get image URL
                post_url = post_data.get("url", "")
                # Accept direct image links and imgur links
                if any(ext in post_url.lower() for ext in [".jpg", ".jpeg", ".png", ".gif"]) or "i.imgur.com" in post_url:
                    image_posts.append(
                        {
                            "title": post_data.get("title"),
                            "url": post_url,
                            "subreddit": subreddit,
                            "score": post_data.get("ups", 0),  # Use 'score' key for consistency
                            "upvotes": post_data.get("ups", 0),  # Keep upvotes for compatibility
                            "permalink": f"https://reddit.com{post_data.get('permalink')}",
                            "nsfw": post_data.get("over_18", False),
                            "author": post_data.get("author", "unknown"),
                        }
                    )

            logger.info(f"Fetched {len(image_posts)} memes from r/{subreddit}")
            return image_posts if image_posts else None

        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching meme from r/{subreddit}")
            return None
        except Exception as e:
            logger.error(f"Error fetching meme from r/{subreddit}: {e}")
            return None

    async def fetch_lemmy_meme(self, community: str) -> list:
        """
        Fetch memes from Lemmy communities

        Args:
            community: Format "instance@community" (e.g., "lemmy.world@memes")

        Returns:
            List of meme dicts or None
        """
        try:
            # Parse instance@community format
            if "@" not in community:
                logger.warning(f"Invalid Lemmy community format: {community} (expected instance@community)")
                return None

            instance, community_name = community.split("@", 1)

            # Build API URL
            url = f"https://{instance}/api/v3/post/list"
            params = {
                "community_name": community_name,
                "sort": "Hot",
                "limit": 50,
            }
            headers = {"User-Agent": "HazeBot/1.0"}

            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status != 200:
                    logger.warning(f"Lemmy API returned {response.status} for {instance}@{community_name}")
                    return None

                data = await response.json()
                posts = data.get("posts", [])

                # Filter for image posts
                image_posts = []
                for item in posts:
                    try:
                        post = item.get("post", {})
                        counts = item.get("counts", {})
                        creator = item.get("creator", {})

                        # Get image URL
                        post_url = post.get("url", "")
                        # Accept direct image links
                        image_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
                        if post_url and any(ext in post_url.lower() for ext in image_extensions):
                            image_posts.append(
                                {
                                    "title": post.get("name", "Meme from Lemmy")[:256],
                                    "url": post_url,
                                    "subreddit": f"lemmy:{instance}@{community_name}",  # Special format for Lemmy
                                    "score": counts.get("score", 0),  # Use 'score' key for consistency
                                    "upvotes": counts.get("score", 0),  # Keep upvotes for compatibility
                                    "permalink": post.get("ap_id", ""),
                                    "nsfw": post.get("nsfw", False),
                                    "author": creator.get("name", "unknown"),
                                }
                            )
                    except Exception as e:
                        logger.debug(f"Error parsing Lemmy post: {e}")
                        continue

                logger.info(f"Fetched {len(image_posts)} memes from {instance}@{community_name}")
                return image_posts if image_posts else None

        except Exception as e:
            logger.error(f"Error fetching meme from Lemmy {community}: {e}")
            return None

    async def get_daily_meme(self, subreddit: str = None, allow_nsfw: bool = False, source: str = None):
        """
        Get a high-quality meme from various sources

        Args:
            subreddit: Optional specific subreddit to fetch from. If None, uses all configured subreddits.
            allow_nsfw: Whether to allow NSFW content. True for daily posts, False for user commands.
            source: Optional specific source (e.g., "reddit"). If None, randomly selects from enabled sources.
        """
        # Try to get hot memes from specified or all sources
        all_memes = []

        # Determine which source(s) to use
        if source:
            sources_to_use = [source] if source in self.meme_sources else self.meme_sources
        else:
            # Randomly pick a source for variety
            sources_to_use = [random.choice(self.meme_sources)]

        for src in sources_to_use:
            if src == "reddit":
                if subreddit:
                    # Fetch from specific subreddit
                    memes = await self.fetch_reddit_meme(subreddit, sort="hot")
                    if memes:
                        all_memes.extend(memes)
                else:
                    # Fetch from all configured subreddits
                    for sub in self.meme_subreddits:
                        memes = await self.fetch_reddit_meme(sub, sort="hot")
                        if memes:
                            all_memes.extend(memes)

            elif src == "lemmy":
                # Fetch from all configured Lemmy communities
                for community in self.meme_lemmy:
                    memes = await self.fetch_lemmy_meme(community)
                    if memes:
                        all_memes.extend(memes)

            # Add more source types here (e.g., elif src == "newsource":)

        if not all_memes:
            logger.warning(f"No memes found from {source or 'any source'}")
            return None

        # Filter NSFW if not allowed
        if not allow_nsfw:
            all_memes = [meme for meme in all_memes if not meme.get("nsfw", False)]
            if not all_memes:
                logger.warning("No SFW memes found")
                return None

        # Filter out recently shown memes
        fresh_memes = [meme for meme in all_memes if not self.is_meme_shown_recently(meme["url"])]

        # If all memes were shown recently, clear cache and use all memes
        if not fresh_memes:
            logger.info("All memes were shown recently, clearing cache")
            self.shown_memes.clear()
            self.save_shown_memes()
            fresh_memes = all_memes

        # Sort by upvotes to get quality memes
        fresh_memes.sort(key=lambda x: x["upvotes"], reverse=True)

        # Pick from top 50 to balance quality and variety
        # This prevents always showing the same top 10 memes
        pool_size = min(50, len(fresh_memes))
        top_memes = fresh_memes[:pool_size]

        logger.debug(f"Selecting from pool of {len(top_memes)} memes (out of {len(fresh_memes)} fresh)")

        # Random pick from top memes pool for variety
        selected_meme = random.choice(top_memes)

        # Mark this meme as shown
        self.mark_meme_as_shown(selected_meme["url"])

        return selected_meme

    async def post_meme(self, meme: dict, channel: discord.TextChannel):
        """Post a meme to the channel"""
        embed = discord.Embed(
            title=meme["title"][:256],  # Discord title limit
            url=meme["permalink"],
            color=PINK,
            timestamp=datetime.now(),
        )
        embed.set_image(url=meme["url"])
        embed.add_field(name="👍 Upvotes", value=f"{meme['upvotes']:,}", inline=True)

        # Display source appropriately
        source_name = f"r/{meme['subreddit']}"  # Default to subreddit format
        # Add custom mappings for non-reddit sources here if needed
        if meme["subreddit"].startswith("lemmy:"):
            # Format: "lemmy:instance@community" -> "instance@community"
            source_name = meme["subreddit"].replace("lemmy:", "")
        # e.g., if meme["subreddit"] == "othersource": source_name = "Other Source"

        embed.add_field(name="📍 Source", value=source_name, inline=True)
        embed.add_field(name="👤 Author", value=f"u/{meme['author']}", inline=True)

        if meme.get("nsfw"):
            embed.add_field(name="⚠️", value="NSFW Content", inline=False)

        set_pink_footer(embed, bot=self.bot.user)

        # Mention the meme role
        role_mention = f"<@&{MEME_ROLE_ID}>"
        await channel.send(f"🎭 Daily Meme Alert! {role_mention}", embed=embed)

        # Format source for logging
        if meme["subreddit"].startswith("lemmy:"):
            source_display = meme["subreddit"].replace("lemmy:", "")
        elif meme["subreddit"] not in ["9gag"]:
            source_display = f"r/{meme['subreddit']}"
        else:
            source_display = meme["subreddit"]
        logger.info(f"Posted meme: {meme['title'][:50]}... from {source_display} ({meme['upvotes']} upvotes)")

    async def fetch_meme_and_create_embed(
        self, subreddit: str = None, allow_nsfw: bool = False
    ) -> tuple[dict, discord.Embed]:
        """
        Shared helper: Fetch meme and create embed (for hybrid commands)

        Args:
            subreddit: Optional specific subreddit to fetch from
            allow_nsfw: Whether to allow NSFW content

        Returns: (meme_dict, embed)
        """
        # Force Reddit source if specific subreddit is requested
        source = "reddit" if subreddit else None
        meme = await self.get_daily_meme(subreddit=subreddit, allow_nsfw=allow_nsfw, source=source)

        if not meme:
            return None, None

        embed = discord.Embed(
            title=meme["title"][:256],
            url=meme["permalink"],
            color=PINK,
        )
        embed.set_image(url=meme["url"])
        embed.add_field(name="👍 Upvotes", value=f"{meme['upvotes']:,}", inline=True)

        # Display source appropriately
        source_name = f"r/{meme['subreddit']}"  # Default to subreddit format
        # Add custom mappings for non-reddit sources here if needed
        if meme["subreddit"].startswith("lemmy:"):
            # Format: "lemmy:instance@community" -> "instance@community"
            source_name = meme["subreddit"].replace("lemmy:", "")

        embed.add_field(name="📍 Source", value=source_name, inline=True)
        embed.add_field(name="👤 Author", value=f"u/{meme['author']}", inline=True)

        if meme.get("nsfw"):
            embed.add_field(name="⚠️", value="NSFW Content", inline=False)

        set_pink_footer(embed, bot=self.bot.user)

        return meme, embed

    @tasks.loop(time=time(hour=12, minute=0))  # Daily at 12:00 PM
    async def daily_meme_task(self):
        """Post a daily meme at 12 PM"""
        try:
            guild = self.bot.get_guild(get_guild_id())
            if not guild:
                logger.error("Guild not found")
                return

            channel = guild.get_channel(MEME_CHANNEL_ID)
            if not channel:
                logger.error(f"Meme channel {MEME_CHANNEL_ID} not found")
                return

            logger.info("Fetching daily meme...")
            # Allow NSFW for daily posts in the configured channel
            meme = await self.get_daily_meme(allow_nsfw=True)

            if meme:
                await self.post_meme(meme, channel)
            else:
                logger.error("Failed to fetch daily meme")
                await channel.send("❌ Sorry, couldn't fetch today's meme. Try again later!")

        except Exception as e:
            logger.error(f"Error in daily_meme_task: {e}")

    @daily_meme_task.before_loop
    async def before_daily_meme(self):
        """Wait for bot to be ready before starting the task"""
        await self.bot.wait_until_ready()

    @commands.command(name="meme")
    async def meme_command(self, ctx: commands.Context, *, source: str = None):
        """
        🎭 Get a meme or open the Meme Hub
        Usage:
        - !meme - Open interactive Meme Hub
        - !meme memes - Get meme from r/memes
        - !meme lemmy.world@memes - Get meme from Lemmy community

        Regular users: Get memes with 10s cooldown
        Mods/Admins: Full management access + no cooldown
        """
        is_admin_or_mod = is_mod_or_admin(ctx.author)

        # If source is specified, fetch directly
        if source:
            # Check cooldown (skip for mods/admins)
            if not is_admin_or_mod:
                last_use = getattr(self, "_user_cooldowns", {}).get(ctx.author.id, 0)
                current_time = datetime.now().timestamp()
                if current_time - last_use < 10:
                    remaining = int(10 - (current_time - last_use))
                    await ctx.send(f"⏳ Please wait {remaining} seconds before requesting another meme!")
                    return

                # Update cooldown
                if not hasattr(self, "_user_cooldowns"):
                    self._user_cooldowns = {}
                self._user_cooldowns[ctx.author.id] = current_time

            # Determine if it's Lemmy or Reddit
            if "@" in source:
                # Lemmy community
                if source not in self.meme_lemmy:
                    await ctx.send(
                        f"❌ `{source}` is not configured. Use `!lemmycommunities` to see available communities."
                    )
                    return

                await ctx.send(f"🔍 Fetching meme from {source}...")
                memes = await self.fetch_lemmy_meme(source)
                source_display = source
            else:
                # Reddit subreddit
                subreddit = source.lower().replace("r/", "")
                if subreddit not in self.meme_subreddits:
                    await ctx.send(
                        f"❌ r/{subreddit} is not configured. Use `!memesubreddits` to see available subreddits."
                    )
                    return

                await ctx.send(f"🔍 Fetching meme from r/{subreddit}...")
                memes = await self.fetch_reddit_meme(subreddit)
                source_display = f"r/{subreddit}"

            if not memes:
                await ctx.send(f"❌ No memes found from {source_display}. Try another source!")
                return

            # Pick random meme and create embed
            meme = random.choice(memes)
            embed = discord.Embed(
                title=meme.get("title", "Meme"),
                url=meme.get("url"),
                color=PINK,
            )
            embed.set_image(url=meme.get("url"))

            embed.add_field(name="📍 Source", value=source_display, inline=True)
            embed.add_field(name="👤 Author", value=meme.get("author", "Unknown"), inline=True)
            embed.add_field(name="⬆️ Score", value=f"{meme.get('score', 0):,}", inline=True)

            set_pink_footer(embed, bot=self.bot.user)

            await ctx.send(embed=embed)
            logger.info(f"Meme fetched by {ctx.author} from {source_display} via command argument")
            return

        # No source specified, show Meme Hub
        embed = discord.Embed(
            title="🎭 Meme Hub",
            description=(
                "Welcome to the Meme Hub! Get trending memes from multiple sources.\n\n"
                "**Available Sources:** Reddit, Lemmy\n"
                "**Rate Limit:** 10 seconds between requests"
                if not is_admin_or_mod
                else "**Mod/Admin Access:** Full management + no cooldown"
            ),
            color=PINK,
        )

        if is_admin_or_mod:
            embed.add_field(
                name="🔧 Management",
                value=(
                    "Use the buttons below to:\n"
                    "• Get random memes (no cooldown)\n"
                    "• Choose specific source\n"
                    "• Manage subreddit sources\n"
                    "• Manage Lemmy communities\n"
                    "• Toggle meme sources\n"
                    "• Test daily meme function"
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="📝 How to Use",
                value=(
                    "• **🎭 Get Random Meme** - Random from all sources\n"
                    "• **🎯 Choose Source** - Pick specific subreddit/community\n"
                    "• Or use: `!meme <source>` - e.g., `!meme memes` or `!meme lemmy.world@memes`\n"
                    "*10 second cooldown between requests*"
                ),
                inline=False,
            )

        set_pink_footer(embed, bot=self.bot.user)

        view = MemeHubView(self, is_admin_or_mod)
        await ctx.send(embed=embed, view=view)
        logger.info(f"Meme Hub opened by {ctx.author} (Mod: {is_admin_or_mod})")

    async def meme_source_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for meme sources (subreddits and Lemmy communities)"""
        choices = []

        # Add Reddit subreddits
        for sub in self.meme_subreddits:
            display_name = f"🔥 r/{sub}"
            if current.lower() in sub.lower() or current.lower() in display_name.lower():
                choices.append(app_commands.Choice(name=display_name, value=sub))

        # Add Lemmy communities
        for comm in self.meme_lemmy:
            display_name = f"🌐 {comm}"
            if current.lower() in comm.lower() or current.lower() in display_name.lower():
                choices.append(app_commands.Choice(name=display_name, value=comm))

        # Limit to 25 choices (Discord limit)
        return choices[:25]

    @app_commands.command(name="meme", description="🎭 Get a meme from specific source or open Meme Hub")
    @app_commands.describe(source="Choose a subreddit or Lemmy community (optional)")
    @app_commands.autocomplete(source=meme_source_autocomplete)
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    async def meme_slash(self, interaction: discord.Interaction, source: str = None):
        """Slash command for Meme Hub with optional source"""
        is_admin_or_mod = is_mod_or_admin(interaction.user)

        # If source is specified, fetch directly
        if source:
            # Check cooldown (skip for mods/admins)
            if not is_admin_or_mod:
                last_use = getattr(self, "_user_cooldowns", {}).get(interaction.user.id, 0)
                current_time = datetime.now().timestamp()
                if current_time - last_use < 10:
                    remaining = int(10 - (current_time - last_use))
                    await interaction.response.send_message(
                        f"⏳ Please wait {remaining} seconds before requesting another meme!",
                        ephemeral=True,
                    )
                    return

                # Update cooldown
                if not hasattr(self, "_user_cooldowns"):
                    self._user_cooldowns = {}
                self._user_cooldowns[interaction.user.id] = current_time

            # Determine if it's Lemmy or Reddit
            if "@" in source:
                # Lemmy community
                if source not in self.meme_lemmy:
                    await interaction.response.send_message(
                        f"❌ `{source}` is not in the configured Lemmy communities.",
                        ephemeral=True,
                    )
                    return

                await interaction.response.send_message(f"🔍 Fetching meme from {source}...", ephemeral=True)
                memes = await self.fetch_lemmy_meme(source)
                source_display = source
            else:
                # Reddit subreddit
                subreddit = source.lower().replace("r/", "")
                if subreddit not in self.meme_subreddits:
                    await interaction.response.send_message(
                        f"❌ r/{subreddit} is not in the configured subreddits.", ephemeral=True
                    )
                    return

                await interaction.response.send_message(f"🔍 Fetching meme from r/{subreddit}...", ephemeral=True)
                memes = await self.fetch_reddit_meme(subreddit)
                source_display = f"r/{subreddit}"

            if not memes:
                await interaction.followup.send(
                    f"❌ No memes found from {source_display}. Try another source!", ephemeral=True
                )
                return

            # Pick random meme and create embed
            meme = random.choice(memes)
            embed = discord.Embed(
                title=meme.get("title", "Meme"),
                url=meme.get("url"),
                color=PINK,
            )
            embed.set_image(url=meme.get("url"))

            embed.add_field(name="📍 Source", value=source_display, inline=True)
            embed.add_field(name="👤 Author", value=meme.get("author", "Unknown"), inline=True)
            embed.add_field(name="⬆️ Score", value=f"{meme.get('score', 0):,}", inline=True)

            set_pink_footer(embed, bot=interaction.client.user)

            await interaction.followup.send(embed=embed)
            logger.info(f"Meme fetched by {interaction.user} from {source_display} via slash command")
            return

        # No source specified, show Meme Hub
        embed = discord.Embed(
            title="🎭 Meme Hub",
            description=(
                "Welcome to the Meme Hub! Get trending memes from multiple sources.\n\n"
                "**Available Sources:** Reddit, Lemmy\n"
                "**Rate Limit:** 10 seconds between requests"
                if not is_admin_or_mod
                else "**Mod/Admin Access:** Full management + no cooldown"
            ),
            color=PINK,
        )

        if is_admin_or_mod:
            embed.add_field(
                name="🔧 Management",
                value=(
                    "Use the buttons below to:\n"
                    "• Get random memes (no cooldown)\n"
                    "• Choose specific source\n"
                    "• Manage subreddit sources\n"
                    "• Manage Lemmy communities\n"
                    "• Toggle meme sources\n"
                    "• Test daily meme function"
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="📝 How to Use",
                value=(
                    "• **🎭 Get Random Meme** - Random from all sources\n"
                    "• **🎯 Choose Source** - Pick specific subreddit/community\n"
                    "• Or use: `/meme <source>` with autocomplete\n"
                    "*10 second cooldown between requests*"
                ),
                inline=False,
            )

        set_pink_footer(embed, bot=interaction.client.user)

        view = MemeHubView(self, is_admin_or_mod)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"Meme Hub opened by {interaction.user} (slash) (Mod: {is_admin_or_mod})")

    @commands.command(name="testmeme")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def test_meme(self, ctx: commands.Context):
        """
        🎭 Test the daily meme function (Mod/Admin only)
        Usage: !testmeme
        """
        await ctx.send("🧪 Testing daily meme...")

        guild = self.bot.get_guild(get_guild_id())
        if not guild:
            await ctx.send("❌ Guild not found")
            return

        channel = guild.get_channel(MEME_CHANNEL_ID)
        if not channel:
            await ctx.send(f"❌ Meme channel {MEME_CHANNEL_ID} not found")
            return

        # Allow NSFW for test posts in the configured channel
        meme = await self.get_daily_meme(allow_nsfw=True)

        if meme:
            await self.post_meme(meme, channel)
            await ctx.send(f"✅ Test meme posted to {channel.mention}")
        else:
            await ctx.send("❌ Failed to fetch test meme")

    @commands.command(name="memesubreddits")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def meme_subreddits(self, ctx: commands.Context):
        """
        🎭 List current meme subreddits (Mod/Admin only)
        Usage: !memesubreddits
        """
        embed = discord.Embed(
            title="🎭 Meme Subreddits Configuration",
            description=f"Currently using **{len(self.meme_subreddits)}** subreddits for meme sourcing.",
            color=PINK,
        )

        # Split into chunks of 10 for better display
        subreddit_list = "\n".join([f"• r/{sub}" for sub in sorted(self.meme_subreddits)])
        embed.add_field(name="📍 Active Subreddits", value=subreddit_list or "None", inline=False)

        embed.add_field(
            name="🔧 Management Commands",
            value=(
                "**!addsubreddit <name>** - Add a subreddit\n"
                "**!removesubreddit <name>** - Remove a subreddit\n"
                "**!resetsubreddits** - Reset to defaults"
            ),
            inline=False,
        )

        set_pink_footer(embed, bot=self.bot.user)
        await ctx.send(embed=embed)
        logger.info(f"Subreddit list viewed by {ctx.author}")

    @commands.command(name="addsubreddit")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def add_subreddit(self, ctx: commands.Context, subreddit: str):
        """
        🎭 Add a subreddit to the meme source list (Mod/Admin only)
        Usage: !addsubreddit <subreddit_name>
        Example: !addsubreddit funny
        """
        # Clean subreddit name (remove r/ if present)
        subreddit = subreddit.lower().strip().replace("r/", "")

        if not subreddit:
            await ctx.send("❌ Please provide a subreddit name.")
            return

        if subreddit in self.meme_subreddits:
            await ctx.send(f"❌ r/{subreddit} is already in the list.")
            return

        # Test if subreddit exists and has content
        await ctx.send(f"🔍 Testing r/{subreddit}...")
        test_memes = await self.fetch_reddit_meme(subreddit)

        if not test_memes:
            await ctx.send(
                f"⚠️ r/{subreddit} returned no valid memes. It might not exist or has no image posts.\n"
                "Add anyway? React with ✅ to confirm or ❌ to cancel."
            )
            # Simple confirmation without complex reaction handling
            return

        self.meme_subreddits.append(subreddit)
        self.save_subreddits()

        await ctx.send(f"✅ Added r/{subreddit} to meme sources!\nNow using {len(self.meme_subreddits)} subreddits.")
        logger.info(f"Subreddit r/{subreddit} added by {ctx.author}")

    @commands.command(name="removesubreddit")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def remove_subreddit(self, ctx: commands.Context, subreddit: str):
        """
        🎭 Remove a subreddit from the meme source list (Mod/Admin only)
        Usage: !removesubreddit <subreddit_name>
        Example: !removesubreddit funny
        """
        # Clean subreddit name
        subreddit = subreddit.lower().strip().replace("r/", "")

        if not subreddit:
            await ctx.send("❌ Please provide a subreddit name.")
            return

        if subreddit not in self.meme_subreddits:
            await ctx.send(f"❌ r/{subreddit} is not in the current list.")
            return

        if len(self.meme_subreddits) <= 1:
            await ctx.send("❌ Cannot remove the last subreddit. Add another one first.")
            return

        self.meme_subreddits.remove(subreddit)
        self.save_subreddits()

        await ctx.send(
            f"✅ Removed r/{subreddit} from meme sources.\nNow using {len(self.meme_subreddits)} subreddits."
        )
        logger.info(f"Subreddit r/{subreddit} removed by {ctx.author}")

    @commands.command(name="resetsubreddits")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def reset_subreddits(self, ctx: commands.Context):
        """
        🎭 Reset subreddit list to defaults (Mod/Admin only)
        Usage: !resetsubreddits
        """
        self.meme_subreddits = DEFAULT_MEME_SUBREDDITS.copy()
        self.save_subreddits()

        embed = discord.Embed(
            title="🔄 Subreddits Reset",
            description=f"Reset to default configuration with **{len(self.meme_subreddits)}** subreddits.",
            color=PINK,
        )

        subreddit_list = "\n".join([f"• r/{sub}" for sub in sorted(self.meme_subreddits)])
        embed.add_field(name="📍 Default Subreddits", value=subreddit_list, inline=False)

        set_pink_footer(embed, bot=self.bot.user)
        await ctx.send(embed=embed)
        logger.info(f"Subreddits reset to defaults by {ctx.author}")

    # === Lemmy Community Management Commands ===

    @commands.command(name="lemmycommunities")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def lemmy_communities(self, ctx: commands.Context):
        """
        🎭 List current Lemmy communities (Mod/Admin only)
        Usage: !lemmycommunities
        """
        embed = discord.Embed(
            title="🎭 Lemmy Communities Configuration",
            description=f"Currently using **{len(self.meme_lemmy)}** Lemmy communities for meme sourcing.",
            color=PINK,
        )

        # Split into chunks for better display
        community_list = "\n".join([f"• {comm}" for comm in sorted(self.meme_lemmy)])
        embed.add_field(name="📍 Active Communities", value=community_list or "None", inline=False)

        embed.add_field(
            name="🔧 Management Commands",
            value=(
                "**!addlemmy <instance@community>** - Add a Lemmy community\n"
                "**!removelemmy <instance@community>** - Remove a community\n"
                "**!resetlemmy** - Reset to defaults\n\n"
                "Format: instance@community (e.g., lemmy.world@memes)"
            ),
            inline=False,
        )

        set_pink_footer(embed, bot=self.bot.user)
        await ctx.send(embed=embed)
        logger.info(f"Lemmy community list viewed by {ctx.author}")

    @commands.command(name="addlemmy")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def add_lemmy(self, ctx: commands.Context, community: str):
        """
        🎭 Add a Lemmy community to the meme source list (Mod/Admin only)
        Usage: !addlemmy <instance@community>
        Example: !addlemmy lemmy.world@memes
        """
        # Clean community name
        community = community.lower().strip()

        # Validate format
        if "@" not in community:
            await ctx.send("❌ Invalid format! Use instance@community (e.g., lemmy.world@memes)")
            return

        if not community:
            await ctx.send("❌ Please provide a Lemmy community in format: instance@community")
            return

        if community in self.meme_lemmy:
            await ctx.send(f"❌ {community} is already in the list.")
            return

        # Test if community exists and has content
        await ctx.send(f"🔍 Testing {community}...")
        test_memes = await self.fetch_lemmy_meme(community)

        if not test_memes:
            await ctx.send(
                f"⚠️ {community} returned no valid memes. It might not exist or has no image posts.\n"
                "Add anyway? React with ✅ to confirm or ❌ to cancel."
            )
            # Simple confirmation without complex reaction handling
            return

        self.meme_lemmy.append(community)
        self.save_lemmy_communities()

        await ctx.send(f"✅ Added {community} to meme sources!\nNow using {len(self.meme_lemmy)} Lemmy communities.")
        logger.info(f"Lemmy community {community} added by {ctx.author}")

    @commands.command(name="removelemmy")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def remove_lemmy(self, ctx: commands.Context, community: str):
        """
        🎭 Remove a Lemmy community from the meme source list (Mod/Admin only)
        Usage: !removelemmy <instance@community>
        Example: !removelemmy lemmy.world@memes
        """
        # Clean community name
        community = community.lower().strip()

        if not community:
            await ctx.send("❌ Please provide a Lemmy community.")
            return

        if community not in self.meme_lemmy:
            await ctx.send(f"❌ {community} is not in the current list.")
            return

        if len(self.meme_lemmy) <= 1:
            await ctx.send("❌ Cannot remove the last Lemmy community. Add another one first.")
            return

        self.meme_lemmy.remove(community)
        self.save_lemmy_communities()

        await ctx.send(
            f"✅ Removed {community} from meme sources.\nNow using {len(self.meme_lemmy)} Lemmy communities."
        )
        logger.info(f"Lemmy community {community} removed by {ctx.author}")

    @commands.command(name="resetlemmy")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def reset_lemmy(self, ctx: commands.Context):
        """
        🎭 Reset Lemmy community list to defaults (Mod/Admin only)
        Usage: !resetlemmy
        """
        self.meme_lemmy = DEFAULT_MEME_LEMMY.copy()
        self.save_lemmy_communities()

        embed = discord.Embed(
            title="🔄 Lemmy Communities Reset",
            description=f"Reset to default configuration with **{len(self.meme_lemmy)}** Lemmy communities.",
            color=PINK,
        )

        community_list = "\n".join([f"• {comm}" for comm in sorted(self.meme_lemmy)])
        embed.add_field(name="📍 Default Communities", value=community_list, inline=False)

        set_pink_footer(embed, bot=self.bot.user)
        await ctx.send(embed=embed)
        logger.info(f"Lemmy communities reset to defaults by {ctx.author}")

    # === Source Management Commands ===

    @commands.command(name="memesources")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def meme_sources_cmd(self, ctx: commands.Context):
        """
        🎭 List all enabled meme sources (Mod/Admin only)
        Usage: !memesources
        """
        embed = discord.Embed(
            title="🎭 Active Meme Sources",
            description=f"Currently using **{len(self.meme_sources)}** meme sources.",
            color=PINK,
        )

        # Show enabled sources (extend source_display when adding new sources)
        source_display = {"reddit": "🔥 Reddit"}

        enabled_list = "\n".join([f"• {source_display.get(src, src)}" for src in self.meme_sources])
        embed.add_field(name="✅ Enabled Sources", value=enabled_list if enabled_list else "None", inline=False)

        # Show disabled sources (extend all_sources when adding new sources)
        all_sources = ["reddit"]
        disabled = [src for src in all_sources if src not in self.meme_sources]
        if disabled:
            disabled_list = "\n".join([f"• {source_display.get(src, src)}" for src in disabled])
            embed.add_field(name="❌ Disabled Sources", value=disabled_list, inline=False)

        embed.add_field(
            name="💡 Management",
            value=(
                "Use `!enablesource <source>` and `!disablesource <source>` to toggle sources.\n"
                "Currently available: `reddit`\n\n"
                "More sources can be added in the future"
            ),
            inline=False,
        )

        set_pink_footer(embed, bot=self.bot.user)
        await ctx.send(embed=embed)

    @commands.command(name="enablesource")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def enable_source(self, ctx: commands.Context, source: str):
        """
        🎭 Enable a meme source (Mod/Admin only)
        Usage: !enablesource <source>
        Example: !enablesource reddit
        """
        source = source.lower().strip()
        valid_sources = ["reddit"]  # Extend when adding new sources

        if source not in valid_sources:
            valid_list = ", ".join([f"`{s}`" for s in valid_sources])
            await ctx.send(f"❌ Invalid source: `{source}`\nValid sources: {valid_list}")
            return

        if source in self.meme_sources:
            await ctx.send(f"⚠️ Source `{source}` is already enabled!")
            return

        self.meme_sources.append(source)
        self.save_sources()

        await ctx.send(f"✅ Enabled `{source}` meme source.\nNow using {len(self.meme_sources)} sources.")
        logger.info(f"Source {source} enabled by {ctx.author}")

    @commands.command(name="disablesource")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def disable_source(self, ctx: commands.Context, source: str):
        """
        🎭 Disable a meme source (Mod/Admin only)
        Usage: !disablesource <source>
        Example: !disablesource 4chan
        """
        source = source.lower().strip()

        if source not in self.meme_sources:
            await ctx.send(f"⚠️ Source `{source}` is not currently enabled!")
            return

        if len(self.meme_sources) <= 1:
            await ctx.send("❌ Cannot disable last source! At least one source must be enabled.")
            return

        self.meme_sources.remove(source)
        self.save_sources()

        await ctx.send(f"✅ Disabled `{source}` meme source.\nNow using {len(self.meme_sources)} sources.")
        logger.info(f"Source {source} disabled by {ctx.author}")

    @commands.command(name="resetsources")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def reset_sources(self, ctx: commands.Context):
        """
        🎭 Reset meme sources to defaults (Mod/Admin only)
        Usage: !resetsources
        """
        self.meme_sources = MEME_SOURCES.copy()
        self.save_sources()

        embed = discord.Embed(
            title="🔄 Sources Reset",
            description=f"Reset to default configuration with **{len(self.meme_sources)}** sources.",
            color=PINK,
        )

        # Extend source_display when adding new sources
        source_display = {"reddit": "🔥 Reddit"}
        source_list = "\n".join([f"• {source_display.get(src, src)}" for src in self.meme_sources])
        embed.add_field(name="📍 Default Sources", value=source_list, inline=False)

        set_pink_footer(embed, bot=self.bot.user)
        await ctx.send(embed=embed)
        logger.info(f"Sources reset to defaults by {ctx.author}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DailyMeme(bot))
