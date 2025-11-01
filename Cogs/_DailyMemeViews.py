"""
🎭 DailyMeme Views Module
Contains all Discord UI components (Views, Buttons, Modals) for the DailyMeme Cog.
Separated from main cog for better organization and maintainability.
"""

import discord
import random
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from Config import (
    PINK,
    MEME_CHANNEL_ID,
    DEFAULT_MEME_SUBREDDITS,
    DEFAULT_MEME_LEMMY,
    MEME_SOURCES,
    ADMIN_ROLE_ID,
    MODERATOR_ROLE_ID,
)
from Utils.EmbedUtils import set_pink_footer

if TYPE_CHECKING:
    from .DailyMeme import DailyMeme

# Use DailyMeme logger name so COG_PREFIXES applies correctly
logger = logging.getLogger("Cogs.DailyMeme")


def is_mod_or_admin(member: discord.Member) -> bool:
    """Check if member is a moderator or administrator"""
    return any(role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in member.roles)


# ===== MAIN HUB VIEW =====


class MemeHubView(discord.ui.View):
    """Interactive Meme Hub with buttons for users and mods"""

    def __init__(self, cog: "DailyMeme", is_admin_or_mod: bool, post_to_channel_id: int = None):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.user_cooldowns = {}  # user_id -> last_use_timestamp
        self.cooldown_seconds = 10  # 10 second cooldown for regular users
        self.post_to_channel_id = post_to_channel_id  # If set, post memes to this channel instead of ephemeral

        # Add "Choose Source" button for all users
        self.add_item(ChooseSourceButton(post_to_channel_id=post_to_channel_id))

        # Add management buttons only for mods/admins
        if is_admin_or_mod:
            self.add_item(SubredditManagementButton())
            self.add_item(LemmyManagementButton())
            self.add_item(SourceManagementButton())
            self.add_item(DailyConfigButton())
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
            # If post_to_channel_id is set, post to channel instead of ephemeral
            if self.post_to_channel_id:
                channel = interaction.guild.get_channel(self.post_to_channel_id)
                if channel:
                    await channel.send(embed=embed)
                    await interaction.followup.send(f"✅ Meme posted to {channel.mention}!", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Target channel not found.", ephemeral=True)
                    return
            else:
                # Normal ephemeral response
                await interaction.followup.send(embed=embed)

            source_name = meme.get("subreddit", "unknown")
            if source_name not in ["9gag"]:
                source_name = f"r/{source_name}"
            logger.info(f"🎭 [DailyMeme] Meme Hub: Meme requested by {interaction.user} from {source_name}")

            # Increment meme request count
            user_id = str(interaction.user.id)
            self.cog.meme_requests[user_id] = self.cog.meme_requests.get(user_id, 0) + 1
            self.cog.save_meme_requests()
        else:
            await interaction.followup.send("❌ Couldn't fetch a meme right now. Try again later!", ephemeral=True)


# ===== SOURCE SELECTION =====


class ChooseSourceButton(discord.ui.Button):
    """Button to choose specific source (subreddit or Lemmy community)"""

    def __init__(self, post_to_channel_id: int = None):
        super().__init__(label="🎯 Choose Source", style=discord.ButtonStyle.secondary, row=0)
        self.post_to_channel_id = post_to_channel_id

    async def callback(self, interaction: discord.Interaction):
        from .DailyMeme import DailyMeme

        cog: DailyMeme = interaction.client.get_cog("DailyMeme")

        embed = discord.Embed(
            title="🎯 Choose Meme Source",
            description="Select a specific subreddit or Lemmy community to fetch memes from.",
            color=PINK,
        )

        set_pink_footer(embed, bot=interaction.client.user)
        view = SourceSelectionView(cog, post_to_channel_id=self.post_to_channel_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class SourceSelectionView(discord.ui.View):
    """View with select menus for choosing subreddit or Lemmy community"""

    def __init__(self, cog: "DailyMeme", post_to_channel_id: int = None):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_cooldowns = {}
        self.cooldown_seconds = 10
        self.post_to_channel_id = post_to_channel_id

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

            # If post_to_channel_id is set, post to channel instead of ephemeral
            if self.post_to_channel_id:
                channel = interaction.guild.get_channel(self.post_to_channel_id)
                if channel:
                    await channel.send(embed=embed)
                    await interaction.followup.send(f"✅ Meme posted to {channel.mention}!", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Target channel not found.", ephemeral=True)
                    return
            else:
                # Normal ephemeral response
                await interaction.followup.send(embed=embed)

            logger.info(f"🎭 [DailyMeme] Specific meme fetched by {interaction.user} from {source_name}")

            # Increment meme request count
            user_id = str(interaction.user.id)
            self.cog.meme_requests[user_id] = self.cog.meme_requests.get(user_id, 0) + 1
            self.cog.save_meme_requests()

        return callback


# ===== SUBREDDIT MANAGEMENT =====


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
        logger.info(f"🎭 [DailyMeme] Subreddits reset by {interaction.user}")


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
        logger.info(f"🎭 [DailyMeme] Subreddit r/{subreddit} added by {interaction.user}")


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
        logger.info(f"🎭 [DailyMeme] Subreddit r/{subreddit} removed by {interaction.user}")


# ===== LEMMY MANAGEMENT =====


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
        logger.info(f"🎭 [DailyMeme] Lemmy communities reset by {interaction.user}")


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
        logger.info(f"🎭 [DailyMeme] Lemmy community {community} added by {interaction.user}")


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
        logger.info(f"🎭 [DailyMeme] Lemmy community {community} removed by {interaction.user}")


# ===== SOURCE MANAGEMENT =====


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
                logger.info(f"🎭 [DailyMeme] Source {source_id} disabled by {interaction.user}")
            else:
                # Enable source
                self.cog.meme_sources.append(source_id)
                self.cog.save_sources()
                await interaction.response.send_message(f"✅ Enabled {source_name}", ephemeral=True)
                logger.info(f"🎭 [DailyMeme] Source {source_id} enabled by {interaction.user}")

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
        logger.info(f"🎭 [DailyMeme] Sources reset by {interaction.user}")

        # Update buttons
        self._update_buttons()
        await interaction.message.edit(view=self)


# ===== MANAGEMENT BUTTONS =====


class SubredditManagementButton(discord.ui.Button):
    """Button to manage subreddits (Mod/Admin only)"""

    def __init__(self):
        super().__init__(label="📋 Manage Subreddits", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        from .DailyMeme import DailyMeme

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
        from .DailyMeme import DailyMeme

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
        from .DailyMeme import DailyMeme

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

        from .DailyMeme import DailyMeme

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
            logger.info(f"🎭 [DailyMeme] Test meme posted by {interaction.user}")
        else:
            await interaction.followup.send("❌ Failed to fetch test meme", ephemeral=True)


class DailyConfigButton(discord.ui.Button):
    """Button to open daily meme configuration (Mod/Admin only)"""

    def __init__(self):
        super().__init__(label="⚙️ Daily Config", style=discord.ButtonStyle.success, row=1)

    async def callback(self, interaction: discord.Interaction):
        from .DailyMeme import DailyMeme

        cog: DailyMeme = interaction.client.get_cog("DailyMeme")

        embed = cog.get_daily_config_embed()
        view = DailyConfigView(cog)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"Daily config opened by {interaction.user}")


# ===== DAILY CONFIG MANAGEMENT =====


class DailyConfigView(discord.ui.View):
    """View for managing daily meme configuration"""

    def __init__(self, cog: "DailyMeme"):
        super().__init__(timeout=300)
        self.cog = cog

    @discord.ui.button(label="🔄 Toggle Enabled/Disabled", style=discord.ButtonStyle.primary, row=0)
    async def toggle_enabled(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle daily meme task on/off"""
        self.cog.daily_config["enabled"] = not self.cog.daily_config.get("enabled", True)
        self.cog.save_daily_config()
        self.cog.restart_daily_task()

        status = "enabled" if self.cog.daily_config["enabled"] else "disabled"
        embed = self.cog.get_daily_config_embed()
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"✅ Daily meme task {status}!", ephemeral=True)
        logger.info(f"Daily meme task {status} by {interaction.user}")

    @discord.ui.button(label="⏰ Set Time", style=discord.ButtonStyle.secondary, row=0)
    async def set_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set time"""
        modal = SetTimeModal(self.cog, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📺 Set Channel", style=discord.ButtonStyle.secondary, row=0)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set channel"""
        modal = SetChannelModal(self.cog, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🔞 Toggle NSFW", style=discord.ButtonStyle.secondary, row=1)
    async def toggle_nsfw(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle NSFW content"""
        self.cog.daily_config["allow_nsfw"] = not self.cog.daily_config.get("allow_nsfw", True)
        self.cog.save_daily_config()

        status = "allowed" if self.cog.daily_config["allow_nsfw"] else "disabled"
        embed = self.cog.get_daily_config_embed()
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"✅ NSFW content {status}!", ephemeral=True)
        logger.info(f"NSFW {status} by {interaction.user}")

    @discord.ui.button(label="🔔 Set Ping Role", style=discord.ButtonStyle.secondary, row=1)
    async def set_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set ping role"""
        modal = SetRoleModal(self.cog, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🎯 Selection Settings", style=discord.ButtonStyle.primary, row=1)
    async def selection_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open selection settings view"""
        embed = discord.Embed(
            title="🎯 Meme Selection Preferences",
            description="Configure how memes are selected for the daily post.",
            color=PINK,
        )

        config = self.cog.daily_config
        embed.add_field(
            name="Current Settings",
            value=(
                f"**Min Score:** {config.get('min_score', 100):,} upvotes\n"
                f"**Max Sources:** {config.get('max_sources', 5)} subreddits/communities\n"
                f"**Pool Size:** Top {config.get('pool_size', 50)} memes\n"
                f"**Reddit:** {len(config.get('use_subreddits', []))} configured (0 = all)\n"
                f"**Lemmy:** {len(config.get('use_lemmy', []))} configured (0 = all)"
            ),
            inline=False,
        )

        set_pink_footer(embed, bot=interaction.client.user)
        view = SelectionSettingsView(self.cog, self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.success, row=2)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the config display"""
        embed = self.cog.get_daily_config_embed()
        await interaction.response.edit_message(embed=embed, view=self)


class SetTimeModal(discord.ui.Modal, title="⏰ Set Daily Meme Time"):
    """Modal for setting the daily meme post time"""

    hour_input = discord.ui.TextInput(
        label="Hour (0-23)",
        placeholder="12",
        required=True,
        max_length=2,
    )

    minute_input = discord.ui.TextInput(
        label="Minute (0-59)",
        placeholder="0",
        required=True,
        max_length=2,
    )

    def __init__(self, cog: "DailyMeme", view: DailyConfigView):
        super().__init__()
        self.cog = cog
        self.view = view

        # Pre-fill with current values
        self.hour_input.default = str(cog.daily_config.get("hour", 12))
        self.minute_input.default = str(cog.daily_config.get("minute", 0))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            hour = int(self.hour_input.value)
            minute = int(self.minute_input.value)

            if not (0 <= hour <= 23):
                await interaction.response.send_message("❌ Hour must be between 0 and 23!", ephemeral=True)
                return

            if not (0 <= minute <= 59):
                await interaction.response.send_message("❌ Minute must be between 0 and 59!", ephemeral=True)
                return

            self.cog.daily_config["hour"] = hour
            self.cog.daily_config["minute"] = minute
            self.cog.save_daily_config()
            self.cog.restart_daily_task()

            embed = self.cog.get_daily_config_embed()
            await interaction.response.edit_message(embed=embed, view=self.view)
            await interaction.followup.send(f"✅ Time set to {hour:02d}:{minute:02d}!", ephemeral=True)
            logger.info(f"Daily meme time set to {hour:02d}:{minute:02d} by {interaction.user}")

        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers!", ephemeral=True)


class SetChannelModal(discord.ui.Modal, title="📺 Set Daily Meme Channel"):
    """Modal for setting the daily meme channel"""

    channel_input = discord.ui.TextInput(
        label="Channel ID",
        placeholder="1433414228840284252",
        required=True,
        max_length=20,
    )

    def __init__(self, cog: "DailyMeme", view: DailyConfigView):
        super().__init__()
        self.cog = cog
        self.view = view

        # Pre-fill with current value
        self.channel_input.default = str(cog.daily_config.get("channel_id", MEME_CHANNEL_ID))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_input.value)
            channel = interaction.guild.get_channel(channel_id)

            if not channel:
                await interaction.response.send_message("❌ Channel not found! Check the ID.", ephemeral=True)
                return

            self.cog.daily_config["channel_id"] = channel_id
            self.cog.save_daily_config()

            embed = self.cog.get_daily_config_embed()
            await interaction.response.edit_message(embed=embed, view=self.view)
            await interaction.followup.send(f"✅ Channel set to {channel.mention}!", ephemeral=True)
            logger.info(f"Daily meme channel set to {channel.name} by {interaction.user}")

        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid channel ID!", ephemeral=True)


class SetRoleModal(discord.ui.Modal, title="🔔 Set Ping Role"):
    """Modal for setting the ping role"""

    role_input = discord.ui.TextInput(
        label="Role ID (leave empty for none)",
        placeholder="1234567890",
        required=False,
        max_length=20,
    )

    def __init__(self, cog: "DailyMeme", view: DailyConfigView):
        super().__init__()
        self.cog = cog
        self.view = view

        # Pre-fill with current value
        role_id = cog.daily_config.get("ping_role_id")
        if role_id:
            self.role_input.default = str(role_id)

    async def on_submit(self, interaction: discord.Interaction):
        role_input = self.role_input.value.strip()

        if not role_input:
            # Remove role
            self.cog.daily_config["ping_role_id"] = None
            self.cog.save_daily_config()

            embed = self.cog.get_daily_config_embed()
            await interaction.response.edit_message(embed=embed, view=self.view)
            await interaction.followup.send("✅ Ping role removed!", ephemeral=True)
            logger.info(f"Daily meme ping role removed by {interaction.user}")
            return

        try:
            role_id = int(role_input)
            role = interaction.guild.get_role(role_id)

            if not role:
                await interaction.response.send_message("❌ Role not found! Check the ID.", ephemeral=True)
                return

            self.cog.daily_config["ping_role_id"] = role_id
            self.cog.save_daily_config()

            embed = self.cog.get_daily_config_embed()
            await interaction.response.edit_message(embed=embed, view=self.view)
            await interaction.followup.send(f"✅ Ping role set to {role.mention}!", ephemeral=True)
            logger.info(f"Daily meme ping role set to {role.name} by {interaction.user}")

        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid role ID!", ephemeral=True)


# ===== SELECTION SETTINGS =====


class SelectionSettingsView(discord.ui.View):
    """View for managing meme selection preferences"""

    def __init__(self, cog: "DailyMeme", parent_view: "DailyConfigView"):
        super().__init__(timeout=300)
        self.cog = cog
        self.parent_view = parent_view

    @discord.ui.button(label="📊 Set Min Score", style=discord.ButtonStyle.secondary, row=0)
    async def set_min_score(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set minimum score"""
        modal = SetMinScoreModal(self.cog, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🔢 Set Max Sources", style=discord.ButtonStyle.secondary, row=0)
    async def set_max_sources(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set max sources"""
        modal = SetMaxSourcesModal(self.cog, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🎲 Set Pool Size", style=discord.ButtonStyle.secondary, row=0)
    async def set_pool_size(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to set pool size"""
        modal = SetPoolSizeModal(self.cog, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📍 Manage Subreddits", style=discord.ButtonStyle.primary, row=1)
    async def manage_subreddits(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open subreddit management"""
        view = ManageSubredditsView(self.cog, self)
        embed = discord.Embed(
            title="📍 Manage Reddit Sources",
            description=(
                "Configure which subreddits to use for daily memes.\nLeave empty to use all available subreddits."
            ),
            color=PINK,
        )

        config = self.cog.daily_config.get("use_subreddits", [])
        if config:
            embed.add_field(
                name=f"Currently Selected ({len(config)})",
                value=", ".join(f"`{s}`" for s in config),
                inline=False,
            )
        else:
            embed.add_field(
                name="Currently Selected",
                value="*All subreddits*",
                inline=False,
            )

        set_pink_footer(embed, bot=interaction.client.user)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="🌐 Manage Lemmy", style=discord.ButtonStyle.primary, row=1)
    async def manage_lemmy(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Lemmy management"""
        view = ManageLemmyView(self.cog, self)
        embed = discord.Embed(
            title="🌐 Manage Lemmy Sources",
            description=(
                "Configure which Lemmy communities to use for daily memes.\n"
                "Leave empty to use all available communities."
            ),
            color=PINK,
        )

        config = self.cog.daily_config.get("use_lemmy", [])
        if config:
            embed.add_field(
                name=f"Currently Selected ({len(config)})",
                value=", ".join(f"`{c}`" for c in config),
                inline=False,
            )
        else:
            embed.add_field(
                name="Currently Selected",
                value="*All Lemmy communities*",
                inline=False,
            )

        set_pink_footer(embed, bot=interaction.client.user)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="◀ Back", style=discord.ButtonStyle.danger, row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to main config"""
        embed = self.cog.get_daily_config_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class SetMinScoreModal(discord.ui.Modal, title="Set Minimum Score"):
    """Modal for setting minimum score threshold"""

    min_score = discord.ui.TextInput(
        label="Minimum Upvotes",
        placeholder="Enter minimum score (e.g., 100)",
        required=True,
        max_length=10,
    )

    def __init__(self, cog: "DailyMeme", parent_view: "SelectionSettingsView"):
        super().__init__()
        self.cog = cog
        self.parent_view = parent_view
        self.min_score.default = str(self.cog.daily_config.get("min_score", 100))

    async def on_submit(self, interaction: discord.Interaction):
        """Handle min score submission"""
        try:
            score = int(self.min_score.value.strip())
            if score < 0:
                await interaction.response.send_message("❌ Score must be 0 or higher!", ephemeral=True)
                return

            self.cog.daily_config["min_score"] = score
            self.cog.save_daily_config()

            embed = discord.Embed(
                title="🎯 Meme Selection Preferences",
                description="Configure how memes are selected for the daily post.",
                color=PINK,
            )

            config = self.cog.daily_config
            embed.add_field(
                name="Current Settings",
                value=(
                    f"**Min Score:** {config.get('min_score', 100):,} upvotes\n"
                    f"**Max Sources:** {config.get('max_sources', 5)} subreddits/communities\n"
                    f"**Pool Size:** Top {config.get('pool_size', 50)} memes\n"
                    f"**Reddit:** {len(config.get('use_subreddits', []))} configured (0 = all)\n"
                    f"**Lemmy:** {len(config.get('use_lemmy', []))} configured (0 = all)"
                ),
                inline=False,
            )

            set_pink_footer(embed, bot=interaction.client.user)
            await interaction.response.edit_message(embed=embed, view=self.parent_view)
            await interaction.followup.send(f"✅ Minimum score set to {score:,}!", ephemeral=True)
            logger.info(f"Daily min score set to {score} by {interaction.user}")

        except ValueError:
            await interaction.response.send_message("❌ Invalid number!", ephemeral=True)


class SetMaxSourcesModal(discord.ui.Modal, title="Set Max Sources"):
    """Modal for setting maximum sources to fetch from"""

    max_sources = discord.ui.TextInput(
        label="Max Sources",
        placeholder="Enter max sources (1-10)",
        required=True,
        max_length=2,
    )

    def __init__(self, cog: "DailyMeme", parent_view: "SelectionSettingsView"):
        super().__init__()
        self.cog = cog
        self.parent_view = parent_view
        self.max_sources.default = str(self.cog.daily_config.get("max_sources", 5))

    async def on_submit(self, interaction: discord.Interaction):
        """Handle max sources submission"""
        try:
            sources = int(self.max_sources.value.strip())
            if sources < 1 or sources > 10:
                await interaction.response.send_message("❌ Max sources must be between 1 and 10!", ephemeral=True)
                return

            self.cog.daily_config["max_sources"] = sources
            self.cog.save_daily_config()

            embed = discord.Embed(
                title="🎯 Meme Selection Preferences",
                description="Configure how memes are selected for the daily post.",
                color=PINK,
            )

            config = self.cog.daily_config
            embed.add_field(
                name="Current Settings",
                value=(
                    f"**Min Score:** {config.get('min_score', 100):,} upvotes\n"
                    f"**Max Sources:** {config.get('max_sources', 5)} subreddits/communities\n"
                    f"**Pool Size:** Top {config.get('pool_size', 50)} memes\n"
                    f"**Reddit:** {len(config.get('use_subreddits', []))} configured (0 = all)\n"
                    f"**Lemmy:** {len(config.get('use_lemmy', []))} configured (0 = all)"
                ),
                inline=False,
            )

            set_pink_footer(embed, bot=interaction.client.user)
            await interaction.response.edit_message(embed=embed, view=self.parent_view)
            await interaction.followup.send(f"✅ Max sources set to {sources}!", ephemeral=True)
            logger.info(f"Daily max sources set to {sources} by {interaction.user}")

        except ValueError:
            await interaction.response.send_message("❌ Invalid number!", ephemeral=True)


class SetPoolSizeModal(discord.ui.Modal, title="Set Pool Size"):
    """Modal for setting meme pool size"""

    pool_size = discord.ui.TextInput(
        label="Pool Size",
        placeholder="Enter pool size (10-100)",
        required=True,
        max_length=3,
    )

    def __init__(self, cog: "DailyMeme", parent_view: "SelectionSettingsView"):
        super().__init__()
        self.cog = cog
        self.parent_view = parent_view
        self.pool_size.default = str(self.cog.daily_config.get("pool_size", 50))

    async def on_submit(self, interaction: discord.Interaction):
        """Handle pool size submission"""
        try:
            size = int(self.pool_size.value.strip())
            if size < 10 or size > 100:
                await interaction.response.send_message("❌ Pool size must be between 10 and 100!", ephemeral=True)
                return

            self.cog.daily_config["pool_size"] = size
            self.cog.save_daily_config()

            embed = discord.Embed(
                title="🎯 Meme Selection Preferences",
                description="Configure how memes are selected for the daily post.",
                color=PINK,
            )

            config = self.cog.daily_config
            embed.add_field(
                name="Current Settings",
                value=(
                    f"**Min Score:** {config.get('min_score', 100):,} upvotes\n"
                    f"**Max Sources:** {config.get('max_sources', 5)} subreddits/communities\n"
                    f"**Pool Size:** Top {config.get('pool_size', 50)} memes\n"
                    f"**Reddit:** {len(config.get('use_subreddits', []))} configured (0 = all)\n"
                    f"**Lemmy:** {len(config.get('use_lemmy', []))} configured (0 = all)"
                ),
                inline=False,
            )

            set_pink_footer(embed, bot=interaction.client.user)
            await interaction.response.edit_message(embed=embed, view=self.parent_view)
            await interaction.followup.send(f"✅ Pool size set to {size}!", ephemeral=True)
            logger.info(f"Daily pool size set to {size} by {interaction.user}")

        except ValueError:
            await interaction.response.send_message("❌ Invalid number!", ephemeral=True)


class ManageSubredditsView(discord.ui.View):
    """View for managing subreddit selection"""

    def __init__(self, cog: "DailyMeme", parent_view: "SelectionSettingsView"):
        super().__init__(timeout=300)
        self.cog = cog
        self.parent_view = parent_view

    @discord.ui.button(label="➕ Add Subreddit", style=discord.ButtonStyle.success, row=0)
    async def add_subreddit(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a subreddit"""
        modal = AddSubredditModal(self.cog, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="➖ Remove Subreddit", style=discord.ButtonStyle.danger, row=0)
    async def remove_subreddit(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Remove a subreddit"""
        config = self.cog.daily_config.get("use_subreddits", [])
        if not config:
            await interaction.response.send_message("❌ No subreddits configured!", ephemeral=True)
            return

        modal = RemoveSubredditModal(self.cog, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🗑️ Clear All", style=discord.ButtonStyle.danger, row=0)
    async def clear_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Clear all subreddits"""
        self.cog.daily_config["use_subreddits"] = []
        self.cog.save_daily_config()

        embed = discord.Embed(
            title="📍 Manage Reddit Sources",
            description=(
                "Configure which subreddits to use for daily memes.\nLeave empty to use all available subreddits."
            ),
            color=PINK,
        )

        embed.add_field(
            name="Currently Selected",
            value="*All subreddits*",
            inline=False,
        )

        set_pink_footer(embed, bot=interaction.client.user)
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send("✅ All subreddits cleared! Using all sources.", ephemeral=True)
        logger.info(f"Subreddit config cleared by {interaction.user}")

    @discord.ui.button(label="◀ Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to selection settings"""
        embed = discord.Embed(
            title="🎯 Meme Selection Preferences",
            description="Configure how memes are selected for the daily post.",
            color=PINK,
        )

        config = self.cog.daily_config
        embed.add_field(
            name="Current Settings",
            value=(
                f"**Min Score:** {config.get('min_score', 100):,} upvotes\n"
                f"**Max Sources:** {config.get('max_sources', 5)} subreddits/communities\n"
                f"**Pool Size:** Top {config.get('pool_size', 50)} memes\n"
                f"**Reddit:** {len(config.get('use_subreddits', []))} configured (0 = all)\n"
                f"**Lemmy:** {len(config.get('use_lemmy', []))} configured (0 = all)"
            ),
            inline=False,
        )

        set_pink_footer(embed, bot=interaction.client.user)
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class ManageLemmyView(discord.ui.View):
    """View for managing Lemmy community selection"""

    def __init__(self, cog: "DailyMeme", parent_view: "SelectionSettingsView"):
        super().__init__(timeout=300)
        self.cog = cog
        self.parent_view = parent_view

    @discord.ui.button(label="➕ Add Community", style=discord.ButtonStyle.success, row=0)
    async def add_community(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a Lemmy community"""
        modal = AddLemmyModal(self.cog, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="➖ Remove Community", style=discord.ButtonStyle.danger, row=0)
    async def remove_community(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Remove a Lemmy community"""
        config = self.cog.daily_config.get("use_lemmy", [])
        if not config:
            await interaction.response.send_message("❌ No communities configured!", ephemeral=True)
            return

        modal = RemoveLemmyModal(self.cog, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🗑️ Clear All", style=discord.ButtonStyle.danger, row=0)
    async def clear_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Clear all Lemmy communities"""
        self.cog.daily_config["use_lemmy"] = []
        self.cog.save_daily_config()

        embed = discord.Embed(
            title="🌐 Manage Lemmy Sources",
            description=(
                "Configure which Lemmy communities to use for daily memes.\n"
                "Leave empty to use all available communities."
            ),
            color=PINK,
        )

        embed.add_field(
            name="Currently Selected",
            value="*All Lemmy communities*",
            inline=False,
        )

        set_pink_footer(embed, bot=interaction.client.user)
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send("✅ All communities cleared! Using all sources.", ephemeral=True)
        logger.info(f"Lemmy config cleared by {interaction.user}")

    @discord.ui.button(label="◀ Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to selection settings"""
        embed = discord.Embed(
            title="🎯 Meme Selection Preferences",
            description="Configure how memes are selected for the daily post.",
            color=PINK,
        )

        config = self.cog.daily_config
        embed.add_field(
            name="Current Settings",
            value=(
                f"**Min Score:** {config.get('min_score', 100):,} upvotes\n"
                f"**Max Sources:** {config.get('max_sources', 5)} subreddits/communities\n"
                f"**Pool Size:** Top {config.get('pool_size', 50)} memes\n"
                f"**Reddit:** {len(config.get('use_subreddits', []))} configured (0 = all)\n"
                f"**Lemmy:** {len(config.get('use_lemmy', []))} configured (0 = all)"
            ),
            inline=False,
        )

        set_pink_footer(embed, bot=interaction.client.user)
        await interaction.response.edit_message(embed=embed, view=self.parent_view)
