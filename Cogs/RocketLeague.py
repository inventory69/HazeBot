import aiohttp
import requests
import os
import json
import random
import asyncio
from concurrent.futures import ThreadPoolExecutor
from discord.ext import commands, tasks
import discord
from discord import app_commands
from bs4 import BeautifulSoup
from typing import Dict, Optional, Tuple, Any
from Config import (
    PINK,
    RL_TIER_ORDER,
    RL_ACCOUNTS_FILE,
    RANK_EMOJIS,
    get_guild_id,
    RL_CHANNEL_ID,
    RL_CONGRATS_VIEWS_FILE,
    RL_RANK_PROMOTION_CONFIG,
    RL_CONGRATS_REPLIES,
    RL_RANK_CHECK_INTERVAL_HOURS,
    RL_RANK_CACHE_TTL_SECONDS,
)

from Utils.EmbedUtils import set_pink_footer
from Utils.CacheUtils import file_cache
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)


# === Rocket League Hub View ===
class RocketLeagueHubView(discord.ui.View):
    """View with buttons for Rocket League commands"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Link Account", style=discord.ButtonStyle.primary, emoji="🔗", custom_id="rl_link_button")
    async def link_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to link RL account"""
        # Check if account is already linked
        accounts = load_rl_accounts()
        if str(interaction.user.id) in accounts:
            await interaction.response.send_message(
                "❌ You already have a Rocket League account linked. Use **Unlink Account** first if you want to change it.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(LinkAccountModal())

    @discord.ui.button(label="View Stats", style=discord.ButtonStyle.primary, emoji="📊", custom_id="rl_stats_button")
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show RL stats for the user"""
        rl_cog = interaction.client.get_cog("RocketLeague")
        if not rl_cog:
            await interaction.response.send_message("❌ Rocket League system not available.", ephemeral=True)
            return

        # Check if account is linked
        accounts = load_rl_accounts()
        user_data = accounts.get(str(interaction.user.id))
        if not user_data:
            await interaction.response.send_message(
                "❌ No Rocket League account linked. Use the **Link Account** button first!", ephemeral=True
            )
            return

        # Determine if response should be ephemeral (only in server-guide channel)
        is_ephemeral = interaction.channel and (
            "server-guide" in interaction.channel.name.lower() or "guide" in interaction.channel.name.lower()
        )

        # Defer immediately to show loading state
        await interaction.response.defer(ephemeral=is_ephemeral)

        # Show loading message
        loading_msg = await interaction.followup.send("🔍 Fetching stats...", ephemeral=is_ephemeral)

        try:
            # Get stats (uses cache like the command)
            platform = user_data["platform"]
            username = user_data["username"]
            stats = await rl_cog.get_player_stats(platform, username)

            if not stats:
                await loading_msg.delete()
                await interaction.followup.send(
                    "❌ Unable to fetch stats right now. Please try again in a moment.", ephemeral=is_ephemeral
                )
                return

            embed = await rl_cog._create_rl_embed(stats, platform)
            await loading_msg.delete()
            await interaction.followup.send(embed=embed, ephemeral=is_ephemeral)
            logger.info(f"RL stats viewed by {interaction.user} (button)")

        except Exception as e:
            logger.error(f"Error in stats_button for {interaction.user}: {e}")
            await loading_msg.delete()
            await interaction.followup.send(
                "❌ An error occurred while fetching stats. Please try again later.", ephemeral=is_ephemeral
            )

    @discord.ui.button(
        label="Unlink Account", style=discord.ButtonStyle.secondary, emoji="🔓", custom_id="rl_unlink_button"
    )
    async def unlink_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Unlink RL account"""
        rl_cog = interaction.client.get_cog("RocketLeague")
        if not rl_cog:
            await interaction.response.send_message("❌ Rocket League system not available.", ephemeral=True)
            return

        # Call the unlink_account method
        await rl_cog.unlink_account(interaction)


class LinkAccountModal(discord.ui.Modal, title="Link Rocket League Account"):
    platform_input = discord.ui.TextInput(
        label="Platform",
        placeholder="steam, epic, psn, xbl, or switch",
        required=True,
        style=discord.TextStyle.short,
        max_length=10,
    )

    username_input = discord.ui.TextInput(
        label="Username/Steam ID",
        placeholder="Your username or Steam ID (17 digits for Steam)",
        required=True,
        style=discord.TextStyle.short,
        max_length=100,
    )

    async def on_submit(self, interaction: discord.Interaction):
        platform = self.platform_input.value.lower().strip()
        username = self.username_input.value.strip()

        if platform not in ["steam", "epic", "psn", "xbl", "switch"]:
            await interaction.response.send_message(
                "❌ Invalid platform. Use: steam, epic, psn, xbl, or switch.", ephemeral=True
            )
            return

        # Fetch stats to verify account
        rl_cog = interaction.client.get_cog("RocketLeague")
        if not rl_cog:
            await interaction.response.send_message("❌ Rocket League system not available.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        stats = await rl_cog.get_player_stats(platform, username)

        if not stats:
            if platform == "steam":
                await interaction.followup.send(
                    "❌ Player not found. For Steam, try using your 17-digit Steam ID instead of the display name.\n"
                    "Find it at https://steamid.io/ or in your Steam profile URL.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "❌ Player not found or error fetching stats. Please check the username and platform.",
                    ephemeral=True,
                )
            return

        # Show confirmation
        embed = discord.Embed(
            title="🔗 Confirm Rocket League Account Linking",
            description=f"Player found: **{stats['username']}**\nPlatform: **{platform.upper()}**\n\nDo you want to link this account?",
            color=PINK,
        )
        if stats.get("highest_icon_url"):
            embed.set_thumbnail(url=stats["highest_icon_url"])
        embed.add_field(
            name="Current Ranks",
            value="\n".join(
                [f"• {k}: {v}" for k, v in (stats.get("rank_display") or stats.get("tier_names") or {}).items()]
            ),
            inline=False,
        )
        set_pink_footer(embed, bot=interaction.client.user)
        msg = await interaction.followup.send(embed=embed, ephemeral=True)  # Send without view first
        view = ConfirmLinkView(interaction, platform, username, stats, rl_cog, msg)
        await msg.edit(embed=embed, view=view)


def load_rl_accounts() -> Dict[str, Any]:
    os.makedirs(os.path.dirname(RL_ACCOUNTS_FILE), exist_ok=True)
    if os.path.exists(RL_ACCOUNTS_FILE):
        with open(RL_ACCOUNTS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_rl_accounts(accounts: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(RL_ACCOUNTS_FILE), exist_ok=True)
    with open(RL_ACCOUNTS_FILE, "w") as f:
        json.dump(accounts, f, indent=4)


def get_highest_rl_rank(user_id: str) -> Optional[str]:
    """
    Helper to get the highest RL rank for a user from local file.
    """
    accounts = load_rl_accounts()
    user_data = accounts.get(str(user_id))
    if not user_data:
        return None
    ranks = user_data.get("ranks", {})
    highest_tier = "Unranked"
    for playlist, tier in ranks.items():
        if tier in RL_TIER_ORDER and RL_TIER_ORDER.index(tier) > RL_TIER_ORDER.index(highest_tier):
            highest_tier = tier
    return highest_tier


class CongratsButton(discord.ui.Button):
    """
    Button for others to congratulate the ranked up user.
    """

    def __init__(self, parent_view: Any) -> None:
        super().__init__(label="Congrats!", style=discord.ButtonStyle.primary, emoji="🎉")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        user = interaction.user
        if user == self.parent_view.ranked_user:
            await interaction.followup.send("You can't congratulate yourself! 😄", ephemeral=True)
            return
        # Get random congrats reply from config
        reply_template = random.choice(RL_CONGRATS_REPLIES)
        reply = reply_template.format(user=user.mention, ranked_user=self.parent_view.ranked_user.mention)
        await interaction.followup.send(reply)
        logger.info(f"{user} congratulated {self.parent_view.ranked_user} on rank up")


class CongratsView(discord.ui.View):
    """
    View containing the congrats button for rank promotions.
    Times out after 3.5 days (half a week).
    """

    def __init__(
        self, ranked_user: discord.User, start_time: Optional[datetime] = None, cog: Optional[Any] = None
    ) -> None:
        if start_time:
            # Ensure both datetimes are timezone-aware
            now = datetime.now(timezone.utc)
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            elapsed = (now - start_time).total_seconds()
            remaining = 302400 - elapsed  # 3.5 days in seconds
            timeout = max(remaining, 0)
        else:
            timeout = 302400  # 3.5 days
        super().__init__(timeout=timeout)
        self.ranked_user = ranked_user
        self.start_time = start_time or datetime.now(timezone.utc)
        self.cog = cog
        self.add_item(CongratsButton(self))

    async def on_timeout(self) -> None:
        """
        Called when the view times out (3.5 days).
        Disables the button and removes from persistent data.
        """
        for item in self.children:
            item.disabled = True
        # Try to edit the message to show disabled button
        if hasattr(self, "message") and self.message:
            try:
                await self.message.edit(view=self)
                logger.info(f"Congrats button disabled after timeout for {self.ranked_user}")
            except Exception as e:
                logger.error(f"Failed to disable congrats button: {e}")

            # Remove from persistent data
            if self.cog:
                self.cog.congrats_views_data = [
                    d for d in self.cog.congrats_views_data if d["message_id"] != self.message.id
                ]
                with open(self.cog.congrats_views_file, "w") as f:
                    json.dump(self.cog.congrats_views_data, f)


class ConfirmLinkView(discord.ui.View):
    """
    View for confirming RL account linking.
    """

    def __init__(
        self,
        interaction: discord.Interaction,
        platform: str,
        username: str,
        stats: Dict[str, Any],
        cog: "RocketLeague",
        message: discord.Message,
    ) -> None:
        super().__init__(timeout=60)  # 1 minute timeout
        self.interaction = interaction
        self.platform = platform
        self.username = username
        self.stats = stats
        self.cog = cog
        self.message = message

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Save the account
        accounts = load_rl_accounts()
        accounts[str(interaction.user.id)] = {
            "platform": self.platform.lower(),
            "username": self.username,
            "ranks": self.stats["tier_names"],  # Keep for compatibility
            "rank_display": self.stats["rank_display"],  # Add full display with emojis
        }
        save_rl_accounts(accounts)
        await self.message.edit(
            content=f"✅ Successfully linked your Rocket League account to {self.stats['username']} on {self.platform.upper()}.",
            embed=None,
            view=None,
        )
        logger.info(f"Rocket League account linked by {interaction.user}")
        self.stop()
        await asyncio.sleep(5)
        await self.message.delete()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.message.edit(content="❌ Account linking cancelled.", embed=None, view=None)
        self.stop()
        await asyncio.sleep(5)
        await self.message.delete()


class RocketLeague(commands.Cog):
    """
    🚀 Rocket League Cog: Fetches player stats using FlareSolverr.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.api_base = os.getenv("ROCKET_API_BASE")
        self.flaresolverr_url = os.getenv("FLARESOLVERR_URL")

        # Ensure HTTPS is used for FlareSolverr
        if self.flaresolverr_url and self.flaresolverr_url.startswith("http://"):
            self.flaresolverr_url = self.flaresolverr_url.replace("http://", "https://", 1)
            logger.warning(f"⚠️ FlareSolverr URL converted from HTTP to HTTPS: {self.flaresolverr_url}")

        self.executor = ThreadPoolExecutor(max_workers=5)

        # Load congrats views data
        self.congrats_views_file = RL_CONGRATS_VIEWS_FILE
        if os.path.exists(self.congrats_views_file):
            with open(self.congrats_views_file, "r") as f:
                self.congrats_views_data = json.load(f)
        else:
            os.makedirs(os.path.dirname(self.congrats_views_file), exist_ok=True)
            self.congrats_views_data = []

    async def _setup_cog(self) -> None:
        """Setup the cog - called on ready and after reload"""
        # Only start once
        if not self.check_ranks.is_running():
            self.check_ranks.start()
            logger.info(f"Rank check task started. Using FlareSolverr URL: {self.flaresolverr_url}")

        self.bot.add_view(RocketLeagueHubView())
        logger.info("RocketLeague hub view restored.")

        # Restore congrats views
        restored_count = 0
        cleaned_congrats_views_data = []
        for data in self.congrats_views_data:
            channel = self.bot.get_channel(data["channel_id"])
            if channel:
                try:
                    message = await channel.fetch_message(data["message_id"])
                    start_time = datetime.fromisoformat(data["start_time"])
                    user = self.bot.get_user(data["user_id"])
                    if user:
                        view = CongratsView(user, start_time=start_time, cog=self)
                        view.message = message
                        await message.edit(view=view)
                        restored_count += 1
                        cleaned_congrats_views_data.append(data)
                    await asyncio.sleep(1)  # Avoid rate limits
                except discord.NotFound:
                    logger.warning(f"Congrats message {data['message_id']} not found, removing from data.")
                except Exception as e:
                    logger.error(f"Failed to restore congrats view for message {data['message_id']}: {e}")
                    cleaned_congrats_views_data.append(data)  # Keep on other errors
            else:
                cleaned_congrats_views_data.append(data)  # Keep if channel not found

        # Save cleaned data
        self.congrats_views_data = cleaned_congrats_views_data
        with open(self.congrats_views_file, "w") as f:
            json.dump(self.congrats_views_data, f)
        logger.info(f"Restored {restored_count} congrats views.")

        # Validate that HTTPS is being used
        if self.flaresolverr_url and not self.flaresolverr_url.startswith("https://"):
            logger.error(f"❌ FlareSolverr URL is not using HTTPS: {self.flaresolverr_url}")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """
        Start the rank check task when the bot is ready and restore persistent views.
        """
        await self._setup_cog()

    async def cog_load(self) -> None:
        """Called when the cog is loaded (including reloads)"""
        if self.bot.is_ready():
            await self._setup_cog()

    async def cog_unload(self):
        """
        Cleanup when cog is unloaded.
        """
        # Stop the rank check task
        if hasattr(self, "check_ranks") and self.check_ranks.is_running():
            self.check_ranks.cancel()
            logger.info("Rank check task cancelled.")

        # Shutdown the thread pool executor
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=True)
            logger.info("Thread pool executor shutdown.")

        # Close the aiohttp session
        if hasattr(self, "session") and not self.session.closed:
            await self.session.close()
            logger.info("HTTP session closed.")

    def fetch_stats_sync(self, platform: str, username: str) -> Optional[Dict[str, Any]]:
        """
        Synchronous fetch using external service.
        """
        url = f"{self.api_base}/standard/profile/{platform}/{username}"

        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 90000,  # Increased from 60s to 90s
        }

        try:
            response = requests.post(self.flaresolverr_url, json=payload, timeout=30)  # Kürzerer Timeout
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"FlareSolverr request failed: {e}")
            return None

        try:
            data = response.json()
            if data.get("status") != "ok":
                logger.warning(f"❌ External service failed: {data.get('message')}")
                return None
            # Get the actual response
            api_response = data["solution"]["response"]
            # Parse HTML to get JSON
            soup = BeautifulSoup(api_response, "html.parser")
            pre_tag = soup.find("pre")
            if not pre_tag:
                logger.warning("Invalid response format")
                return None
            json_text = pre_tag.text
            api_data = json.loads(json_text)

            # Now process api_data as before
            if "errors" in api_data and api_data["errors"][0]["code"] == "CollectorResultStatus::NotFound":
                logger.warning(f"🚫 Player {username} not found")
                return None

            profile = api_data["data"]
            segments = profile["segments"]
            overview = next((s for s in segments if s["type"] == "overview"), None)
            if not overview:
                logger.warning("No overview segment found")
                return None

            stats = overview["stats"]
            rank = stats.get("tier", {}).get("metadata", {}).get("name", "Unranked")
            season_reward_name = stats.get("seasonRewardLevel", {}).get("metadata", {}).get("name", "N/A")

            # Extract username
            username_display = profile["platformInfo"]["platformUserHandle"]

            # Extract ranks
            ranks = {}
            tier_names = {}
            icon_urls = {}
            highest_tier_val = 0
            highest_icon_url = None
            for segment in segments:
                if segment["type"] == "playlist" and segment["attributes"].get("season") == 34:
                    pid = segment["attributes"]["playlistId"]
                    name = segment["metadata"]["name"]
                    if pid == 10 or name == "Ranked Duel 1v1":  # 1v1
                        tier_name = segment["stats"]["tier"]["metadata"]["name"]
                        div_name = segment["stats"]["division"]["metadata"]["name"]
                        emoji = RANK_EMOJIS.get(tier_name, "<:unranked:1425389712276721725>")
                        ranks["1v1"] = f"{emoji} {div_name}"
                        tier_names["1v1"] = tier_name
                        icon_urls["1v1"] = segment["stats"]["tier"]["metadata"]["iconUrl"]
                        tier_val = segment["stats"]["tier"]["value"]
                        if tier_val > highest_tier_val:
                            highest_tier_val = tier_val
                            highest_icon_url = segment["stats"]["tier"]["metadata"]["iconUrl"]
                    elif pid == 11 or name == "Ranked Doubles 2v2":  # 2v2
                        tier_name = segment["stats"]["tier"]["metadata"]["name"]
                        div_name = segment["stats"]["division"]["metadata"]["name"]
                        emoji = RANK_EMOJIS.get(tier_name, "<:unranked:1425389712276721725>")
                        ranks["2v2"] = f"{emoji} {div_name}"
                        tier_names["2v2"] = tier_name
                        icon_urls["2v2"] = segment["stats"]["tier"]["metadata"]["iconUrl"]
                        tier_val = segment["stats"]["tier"]["value"]
                        if tier_val > highest_tier_val:
                            highest_tier_val = tier_val
                            highest_icon_url = segment["stats"]["tier"]["metadata"]["iconUrl"]
                    elif pid == 13 or name == "Ranked Standard 3v3":  # 3v3
                        tier_name = segment["stats"]["tier"]["metadata"]["name"]
                        div_name = segment["stats"]["division"]["metadata"]["name"]
                        emoji = RANK_EMOJIS.get(tier_name, "<:unranked:1425389712276721725>")
                        ranks["3v3"] = f"{emoji} {div_name}"
                        tier_names["3v3"] = tier_name
                        icon_urls["3v3"] = segment["stats"]["tier"]["metadata"]["iconUrl"]
                        tier_val = segment["stats"]["tier"]["value"]
                        if tier_val > highest_tier_val:
                            highest_tier_val = tier_val
                            highest_icon_url = segment["stats"]["tier"]["metadata"]["iconUrl"]
                    elif name == "Ranked 4v4 Quads":  # 4v4
                        tier_name = segment["stats"]["tier"]["metadata"]["name"]
                        div_name = segment["stats"]["division"]["metadata"]["name"]
                        emoji = RANK_EMOJIS.get(tier_name, "<:unranked:1425389712276721725>")
                        ranks["4v4"] = f"{emoji} {div_name}"
                        tier_names["4v4"] = tier_name
                        icon_urls["4v4"] = segment["stats"]["tier"]["metadata"]["iconUrl"]
                        tier_val = segment["stats"]["tier"]["value"]
                        if tier_val > highest_tier_val:
                            highest_tier_val = tier_val
                            highest_icon_url = segment["stats"]["tier"]["metadata"]["iconUrl"]

            # Set unavailable ranks to Unranked
            for key in ["1v1", "2v2", "3v3", "4v4"]:
                if key not in ranks:
                    ranks[key] = "<:unranked:1425389712276721725> Unranked"
                    tier_names[key] = "Unranked"

            season_emoji = RANK_EMOJIS.get(season_reward_name, "<:unranked:1425389712276721725>")

            return {
                "username": username_display,
                "rank": rank,
                "season_reward": f"{season_emoji} {season_reward_name}",
                "rank_1v1": ranks["1v1"],
                "rank_2v2": ranks["2v2"],
                "rank_3v3": ranks["3v3"],
                "rank_4v4": ranks["4v4"],
                "highest_icon_url": highest_icon_url,
                "tier_names": tier_names,
                "rank_display": ranks,  # Full display with emojis
                "icon_urls": icon_urls,
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Connection error: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching stats for {username}: {e}")
            return None

    async def get_player_stats(
        self, platform: str, username: str, force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Async wrapper for sync fetch with caching.
        """
        cache_key = f"rl_stats:{platform}:{username}"

        if force_refresh:
            # Bypass cache and fetch directly
            loop = self.bot.loop
            result = await loop.run_in_executor(self.executor, self.fetch_stats_sync, platform, username)
            # Rate limit only for actual API calls
            if result is not None:
                await asyncio.sleep(30)
            return result

        async def fetch_and_cache():
            loop = self.bot.loop
            result = await loop.run_in_executor(self.executor, self.fetch_stats_sync, platform, username)
            # Rate limit only for actual API calls (when cache miss)
            if result is not None:
                await asyncio.sleep(30)
            return result

        # Cache using configured TTL
        return await file_cache.get_or_set(cache_key, fetch_and_cache, ttl=RL_RANK_CACHE_TTL_SECONDS)

    async def _get_rl_account(self, user_id: int, platform: Optional[str], username: Optional[str]) -> Tuple[str, str]:
        """
        Shared helper to get RL account details.
        Returns (platform, username) or raises ValueError with message.
        """
        accounts = load_rl_accounts()
        user_account = accounts.get(str(user_id))
        if not platform and not username:
            if not user_account:
                raise ValueError("❌ No account set. Use /setrlaccount or !setrlaccount")
            platform = user_account["platform"]
            username = user_account["username"]
        elif not username:
            raise ValueError("❌ Provide username or set account.")
        if platform.lower() not in ["steam", "epic", "psn", "xbl", "switch"]:
            raise ValueError("❌ Invalid platform.")
        return platform.lower(), username

    async def _create_rl_embed(self, stats: Dict[str, Any], platform: str) -> discord.Embed:
        """
        Shared helper to create the RL stats embed.
        """
        embed = discord.Embed(
            title=f"Rocket League Stats for {stats['username']} ({platform.upper()})",
            color=PINK,
        )
        if stats.get("highest_icon_url"):
            embed.set_thumbnail(url=stats["highest_icon_url"])
        embed.add_field(name="Rank 1v1", value=stats["rank_1v1"], inline=True)
        embed.add_field(name="Rank 2v2", value=stats["rank_2v2"], inline=True)
        embed.add_field(name="Rank 3v3", value=stats["rank_3v3"], inline=True)
        embed.add_field(name="Rank 4v4", value=stats["rank_4v4"], inline=True)
        embed.add_field(name="Season Reward", value=stats["season_reward"], inline=True)
        set_pink_footer(embed, bot=self.bot.user)
        return embed

    async def _check_and_update_ranks(self, force: bool = False) -> None:
        """
        Check and update ranks for all linked accounts.
        If force=True, ignore time checks and fetch all.
        """
        accounts = load_rl_accounts()
        now = datetime.now()
        guild = self.bot.get_guild(get_guild_id())
        if not guild:
            return
        channel = guild.get_channel(RL_CHANNEL_ID)
        if not channel:
            return
        if not accounts:
            logger.info("No linked accounts, skipping rank check.")
            return
        tier_order = [
            "Unranked",
            "Bronze I",
            "Bronze II",
            "Bronze III",
            "Silver I",
            "Silver II",
            "Silver III",
            "Gold I",
            "Gold II",
            "Gold III",
            "Platinum I",
            "Platinum II",
            "Platinum III",
            "Diamond I",
            "Diamond II",
            "Diamond III",
            "Champion I",
            "Champion II",
            "Champion III",
            "Grand Champion I",
            "Grand Champion II",
            "Grand Champion III",
            "Supersonic Legend",
        ]
        logger.info(f"Starting rank check for {len(accounts)} linked accounts.")
        for user_id, data in accounts.items():
            if not force:
                last_fetched_str = data.get("last_fetched")
                if last_fetched_str:
                    last_fetched = datetime.fromisoformat(last_fetched_str)
                    time_since_last = now - last_fetched
                    if time_since_last < timedelta(hours=RL_RANK_CHECK_INTERVAL_HOURS):
                        logger.debug(
                            f"Skipping {data['username']} - last checked {time_since_last.total_seconds() / 60:.1f} minutes ago"
                        )
                        continue  # Skip if less than configured interval
                else:
                    logger.info(f"No last_fetched timestamp for {data['username']}, will check ranks")
            platform = data["platform"]
            username = data["username"]
            old_ranks = data.get("ranks", {})

            # Log old ranks before fetching new ones
            old_ranks_str = ", ".join([f"{k}: {v}" for k, v in old_ranks.items()]) if old_ranks else "No ranks stored"
            logger.info(f"Checking {username} (ID: {user_id}) - Stored ranks: [{old_ranks_str}]")

            stats = await self.get_player_stats(platform, username, force_refresh=force)
            if stats:
                new_ranks = stats["tier_names"]  # For comparison (tier names only)
                new_rank_display = stats.get("rank_display", {})  # For storage (with divisions and emojis)
                new_icon_urls = stats.get("icon_urls", {})

                # Log fetched ranks
                new_ranks_str = ", ".join([f"{k}: {v}" for k, v in new_ranks.items()])
                logger.info(f"Fetched ranks for {username}: [{new_ranks_str}]")

                user = self.bot.get_user(int(user_id))
                if user:
                    # Check if this is the first check (no old ranks stored)
                    is_first_check = not old_ranks or all(v == "Unranked" for v in old_ranks.values())

                    for playlist, new_tier in new_ranks.items():
                        old_tier = old_ranks.get(playlist, "Unranked")
                        if new_tier != old_tier:
                            logger.info(f"Rank change detected for {username} {playlist}: {old_tier} -> {new_tier}")
                        if new_tier != old_tier and tier_order.index(new_tier) > tier_order.index(old_tier):
                            # Skip notification if this is the first check (initial setup)
                            if is_first_check:
                                logger.info(
                                    f"Skipping promotion notification for {username} {playlist} (first check/initialization)"
                                )
                                continue

                            # DOUBLE VALIDATION: Fetch stats again without cache to verify the promotion
                            logger.info(f"Double-checking promotion for {username} {playlist} with fresh API call...")
                            await asyncio.sleep(2)  # Small delay before re-fetch
                            verification_stats = await self.get_player_stats(platform, username, force_refresh=True)

                            if not verification_stats:
                                logger.warning(
                                    f"Failed to verify promotion for {username} {playlist} - skipping notification"
                                )
                                continue

                            verified_tier = verification_stats["tier_names"].get(playlist, "Unranked")
                            logger.info(f"Verification result for {username} {playlist}: {verified_tier}")

                            if verified_tier != new_tier:
                                logger.warning(
                                    f"Promotion verification FAILED for {username} {playlist}: Initial={new_tier}, Verified={verified_tier} - skipping notification"
                                )
                                # Use the verified tier for storage
                                new_ranks[playlist] = verified_tier
                                continue

                            logger.info(f"Promotion verified for {username} {playlist}: {old_tier} -> {new_tier}")

                            emoji = RANK_EMOJIS.get(new_tier, "<:unranked:1425389712276721725>")
                            icon_url = new_icon_urls.get(playlist)

                            # Send notification using config
                            config = RL_RANK_PROMOTION_CONFIG
                            notification_msg = config["notification_prefix"].format(user=user.mention)
                            await channel.send(notification_msg)

                            # Create embed using config
                            embed_description = config["embed_description"].format(
                                user=user.mention, playlist=playlist, emoji=emoji, rank=new_tier
                            )
                            embed = discord.Embed(
                                title=config["embed_title"],
                                description=embed_description,
                                color=PINK,
                            )
                            if icon_url:
                                embed.set_thumbnail(url=icon_url)
                            set_pink_footer(embed, bot=self.bot.user)
                            view = CongratsView(user, cog=self)
                            embed_msg = await channel.send(embed=embed, view=view)
                            view.message = embed_msg

                            # Save congrats view data persistently
                            congrats_data = {
                                "user_id": user.id,
                                "channel_id": channel.id,
                                "message_id": embed_msg.id,
                                "start_time": view.start_time.isoformat(),
                            }
                            self.congrats_views_data.append(congrats_data)
                            with open(self.congrats_views_file, "w") as f:
                                json.dump(self.congrats_views_data, f)

                            logger.info(f"Rank promotion notified for {user}: {playlist} {old_tier} -> {new_tier}")
                else:
                    logger.warning(f"User {user_id} not found in bot cache, cannot send rank promotion")
                # Update ranks and last_fetched
                data["ranks"] = new_ranks  # Store tier names for comparison
                data["rank_display"] = new_rank_display  # Store full display with divisions and emojis
                data["icon_urls"] = new_icon_urls
                data["last_fetched"] = now.isoformat()
                save_rl_accounts(accounts)
                logger.info(f"Updated stored ranks for {username}: [{new_ranks_str}], last_fetched: {now.isoformat()}")
            else:
                logger.warning(f"Failed to fetch stats for {username} ({platform})")
        logger.info("Rank check completed.")

    @tasks.loop(hours=RL_RANK_CHECK_INTERVAL_HOURS)
    async def check_ranks(self) -> None:
        """
        Check for rank promotions at configured interval.
        """
        await self._check_and_update_ranks(force=False)

    @commands.command(name="setrlaccount")
    async def setrlaccount(self, ctx: commands.Context, platform: str, *, username: str) -> None:
        """
        🚀 Set your main Rocket League account.
        Usage: !setrlaccount <platform> <username>
        """
        # Check if account is already linked
        accounts = load_rl_accounts()
        if str(ctx.author.id) in accounts:
            await ctx.send(
                "❌ You already have a Rocket League account linked. Use **!unlinkrlaccount** first if you want to change it."
            )
            return

        if platform.lower() not in ["steam", "epic", "psn", "xbl", "switch"]:
            await ctx.send("❌ Invalid platform.")
            return
        stats = await self.get_player_stats(platform.lower(), username)
        if not stats:
            if platform.lower() == "steam":
                await ctx.send(
                    "❌ Player not found. For Steam, try using your 17-digit Steam ID instead of the display name.\n"
                    "Find it at https://steamid.io/ or in your Steam profile URL (e.g., https://steamcommunity.com/profiles/76561197993735144)."
                )
            else:
                await ctx.send("❌ Player not found or error fetching stats. Please check the username and platform.")
            return
        accounts = load_rl_accounts()
        accounts[str(ctx.author.id)] = {
            "platform": platform.lower(),
            "username": username,
            "ranks": stats["tier_names"],  # Keep for compatibility
            "rank_display": stats["rank_display"],  # Add full display with emojis
        }
        save_rl_accounts(accounts)
        await ctx.send(
            f"✅ Successfully linked your Rocket League account to {stats['username']} on {platform.upper()}."
        )
        logger.info(f"Rocket League account linked by {ctx.author}")

    @app_commands.command(name="setrlaccount", description="Set your main Rocket League account")
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    @app_commands.describe(platform="Platform", username="Username")
    async def setrlaccount_slash(self, interaction: discord.Interaction, platform: str, username: str) -> None:
        # Check if account is already linked
        accounts = load_rl_accounts()
        if str(interaction.user.id) in accounts:
            await interaction.response.send_message(
                "❌ You already have a Rocket League account linked. Use **Unlink Account** first if you want to change it.",
                ephemeral=True,
            )
            return

        if platform.lower() not in ["steam", "epic", "psn", "xbl", "switch"]:
            await interaction.response.send_message("❌ Invalid platform.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        stats = await self.get_player_stats(platform.lower(), username)
        if not stats:
            if platform.lower() == "steam":
                await interaction.followup.send(
                    "❌ Player not found. For Steam, try using your 17-digit Steam ID instead of the display name.\n"
                    "Find it at https://steamid.io/ or in your Steam profile URL.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "❌ Player not found or error fetching stats. Please check the username and platform.",
                    ephemeral=True,
                )
            return
        # Show confirmation
        embed = discord.Embed(
            title="🔗 Confirm Rocket League Account Linking",
            description=f"Player found: **{stats['username']}**\nPlatform: **{platform.upper()}**\n\nDo you want to link this account?",
            color=PINK,
        )
        if stats.get("highest_icon_url"):
            embed.set_thumbnail(url=stats["highest_icon_url"])
        embed.add_field(
            name="Current Ranks",
            value="\n".join(
                [f"• {k}: {v}" for k, v in (stats.get("rank_display") or stats.get("tier_names") or {}).items()]
            ),
            inline=False,
        )
        set_pink_footer(embed, bot=self.bot.user)
        msg = await interaction.followup.send(embed=embed, ephemeral=True)  # Send without view first
        view = ConfirmLinkView(interaction, platform, username, stats, self, msg)
        await msg.edit(embed=embed, view=view)  # Edit to add view

    @commands.command(name="rlstats")
    async def rlstats(
        self, ctx: commands.Context, platform: Optional[str] = None, *, username: Optional[str] = None
    ) -> None:
        """
        🚀 Get Rocket League stats for a player or your set account.
        Usage: !rlstats [platform] [username]
        If no args, uses your set account.
        """
        try:
            platform, username = await self._get_rl_account(ctx.author.id, platform, username)
        except ValueError as e:
            await ctx.send(str(e))
            return

        await ctx.send("🔍 Fetching stats...")
        stats = await self.get_player_stats(platform, username)
        if not stats:
            await ctx.send("❌ Player not found or error fetching stats.")
            return

        embed = await self._create_rl_embed(stats, platform)
        await ctx.send(embed=embed)
        logger.info(f"Rocket League stats requested for {username} by {ctx.author}")

    @app_commands.command(
        name="rlstats",
        description="🚀 Get Rocket League stats for a player or your set account",
    )
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    @app_commands.describe(platform="Platform (optional if set)", username="Username (optional if set)")
    async def rlstats_slash(
        self,
        interaction: discord.Interaction,
        platform: Optional[str] = None,
        username: Optional[str] = None,
    ) -> None:
        """
        🚀 Get Rocket League stats for a player.
        """
        await self.show_stats(interaction, platform, username)

    @commands.command(name="adminrlstats")
    @commands.has_permissions(administrator=True)
    async def adminrlstats(self, ctx: commands.Context) -> None:
        """
        🚀 Admin command to manually check all linked Rocket League accounts for rank promotions.
        Bypasses the hourly timer and fetches fresh data.
        Requires administrator permissions.
        """
        msg1 = await ctx.send("🔍 Checking all linked Rocket League accounts for rank promotions...")
        await self._check_and_update_ranks(force=True)
        await msg1.delete()
        msg2 = await ctx.send("✅ Rank check completed for all linked accounts.")
        await asyncio.sleep(5)
        await msg2.delete()
        logger.info(f"Admin manual rank check triggered by {ctx.author}")

    @commands.command(name="unlinkrlaccount")
    async def unlinkrlaccount(self, ctx: commands.Context) -> None:
        """
        🚀 Unlink your Rocket League account.
        Usage: !unlinkrlaccount
        """
        accounts = load_rl_accounts()
        user_id = str(ctx.author.id)
        if user_id not in accounts:
            await ctx.send("❌ No Rocket League account linked.")
            return
        del accounts[user_id]
        save_rl_accounts(accounts)
        await ctx.send("✅ Successfully unlinked your Rocket League account.")
        logger.info(f"Rocket League account unlinked by {ctx.author}")

    async def show_stats(
        self,
        interaction: discord.Interaction,
        platform: Optional[str] = None,
        username: Optional[str] = None,
        ephemeral: bool = False,
    ) -> None:
        """Show RL stats (used by command and button)"""
        try:
            platform, username = await self._get_rl_account(interaction.user.id, platform, username)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=ephemeral)
            return

        await interaction.response.defer(ephemeral=ephemeral)
        stats = await self.get_player_stats(platform, username)
        if not stats:
            await interaction.followup.send("❌ Player not found or error fetching stats.", ephemeral=ephemeral)
            return

        embed = await self._create_rl_embed(stats, platform)
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        logger.info(f"RL stats viewed by {interaction.user}")

    async def unlink_account(self, interaction: discord.Interaction) -> None:
        """Unlink RL account (used by command and button)"""
        accounts = load_rl_accounts()
        user_id = str(interaction.user.id)
        if user_id not in accounts:
            await interaction.response.send_message("❌ No Rocket League account linked.", ephemeral=True)
            return
        del accounts[user_id]
        save_rl_accounts(accounts)
        await interaction.response.send_message("✅ Successfully unlinked your Rocket League account.", ephemeral=True)
        logger.info(f"Rocket League account unlinked by {interaction.user}")

    @app_commands.command(name="unlinkrlaccount", description="Unlink your Rocket League account")
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    async def unlinkrlaccount_slash(self, interaction: discord.Interaction) -> None:
        await self.unlink_account(interaction)

    async def show_rocket_hub(self, interaction: discord.Interaction) -> None:
        """Show the Rocket League hub (used by command and button)"""
        embed = discord.Embed(
            title="🚀 Rocket League Hub",
            description=(
                "Welcome to the Rocket League stats tracking system!\n\n"
                "**Features:**\n"
                "• Link your Rocket League account\n"
                "• View detailed stats and ranks\n"
                "• Track rank promotions automatically\n"
                "• Compare with other players\n\n"
                "**Supported Platforms:**\n"
                "Steam, Epic, PSN, Xbox, Nintendo Switch"
            ),
            color=PINK,
        )

        # Check if user has account linked
        accounts = load_rl_accounts()
        user_data = accounts.get(str(interaction.user.id))
        if user_data:
            embed.add_field(
                name="📊 Your Linked Account",
                value=f"**Platform:** {user_data['platform'].upper()}\n**Username:** {user_data['username']}",
                inline=False,
            )
            if user_data.get("rank_display"):
                ranks_display = "\n".join([f"• {k}: {v}" for k, v in user_data["rank_display"].items()])
                embed.add_field(name="🏆 Current Ranks", value=ranks_display, inline=False)
            elif user_data.get("ranks"):
                # Fallback for old accounts that only have tier names
                ranks_display = "\n".join(
                    [
                        f"• {k}: {RANK_EMOJIS.get(v, '<:unranked:1425389712276721725>')} {v}"
                        for k, v in user_data["ranks"].items()
                    ]
                )
                embed.add_field(name="🏆 Current Ranks", value=ranks_display, inline=False)
        else:
            embed.add_field(
                name="❓ No Account Linked",
                value="Click **Link Account** below to get started!",
                inline=False,
            )

        embed.add_field(
            name="💡 Quick Start",
            value=(
                "1. Click **Link Account** and enter your details\n"
                "2. Use **View Stats** to see your current ranks\n"
                "3. Get notified when you rank up!"
            ),
            inline=False,
        )

        set_pink_footer(embed, bot=interaction.client.user)

        view = RocketLeagueHubView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"Rocket League hub opened by {interaction.user}")

    @commands.command(name="rocket")
    async def rocket_command(self, ctx: commands.Context) -> None:
        """
        🚀 Rocket League Hub - Manage your account and view stats
        """

        # Create a mock interaction object to use the same helper
        class MockInteraction:
            def __init__(self, ctx):
                self.user = ctx.author
                self.client = ctx.bot
                self.guild = ctx.guild
                self.channel = ctx.channel
                self._responded = False

            async def response_send_message(self, **kwargs):
                # Remove ephemeral for prefix commands (not supported)
                kwargs.pop("ephemeral", None)
                await self.channel.send(**kwargs)

        # Create mock interaction and call helper
        mock_interaction = MockInteraction(ctx)
        mock_interaction.response = type("Response", (), {"send_message": mock_interaction.response_send_message})()
        await self.show_rocket_hub(mock_interaction)

    @app_commands.command(name="rocket", description="🚀 Rocket League Hub - Manage your account and view stats")
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    async def rocket_hub(self, interaction: discord.Interaction) -> None:
        """Rocket League hub with all features"""
        await self.show_rocket_hub(interaction)

    @commands.command(name="restorecongratsview")
    @commands.is_owner()
    async def restore_congrats_view(self, ctx: commands.Context, message_id: int, user_id: int) -> None:
        """
        Restore a congrats view for an old rank promotion message.
        Usage: !restorecongratsview <message_id> <user_id>
        """
        try:
            # Fetch the message
            channel = self.bot.get_channel(RL_CHANNEL_ID)
            if not channel:
                await ctx.send("❌ Rocket League channel not found!")
                return

            message = await channel.fetch_message(message_id)
            if not message:
                await ctx.send("❌ Message not found!")
                return

            # Get the user
            user = self.bot.get_user(user_id)
            if not user:
                await ctx.send("❌ User not found!")
                return

            # Create view with the message's creation time as start_time
            view = CongratsView(user, start_time=message.created_at, cog=self)

            # Edit the message to add the view
            await message.edit(view=view)
            view.message = message

            # Save to persistent data
            congrats_data = {
                "user_id": user.id,
                "channel_id": channel.id,
                "message_id": message.id,
                "start_time": message.created_at.isoformat(),
            }
            # Remove old entry if exists
            self.congrats_views_data = [d for d in self.congrats_views_data if d["message_id"] != message_id]
            self.congrats_views_data.append(congrats_data)
            with open(self.congrats_views_file, "w") as f:
                json.dump(self.congrats_views_data, f)

            await ctx.send(f"✅ Congrats view restored for message {message_id}!")
            logger.info(f"Congrats view restored for message {message_id} by {ctx.author}")
        except Exception as e:
            await ctx.send(f"❌ Error restoring view: {e}")
            logger.error(f"Error restoring congrats view: {e}")


async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the RocketLeague cog.
    """
    await bot.add_cog(RocketLeague(bot))
