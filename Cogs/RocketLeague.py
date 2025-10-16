import aiohttp
import requests
import os
import json
from concurrent.futures import ThreadPoolExecutor
from discord.ext import commands, tasks
import discord
from discord import app_commands
from bs4 import BeautifulSoup
from typing import Dict, Optional, Tuple, Any
from Config import PINK, RL_TIER_ORDER, RL_ACCOUNTS_FILE, RANK_EMOJIS

from Utils.EmbedUtils import set_pink_footer
from Utils.Logger import Logger
from Utils.CacheUtils import file_cache
from datetime import datetime, timedelta


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
        if tier in RL_TIER_ORDER and RL_TIER_ORDER.index(tier) > RL_TIER_ORDER.index(
            highest_tier
        ):
            highest_tier = tier
    return highest_tier


class RocketLeague(commands.Cog):
    """
    🚀 Rocket League Cog: Fetches player stats using FlareSolverr.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.api_base = os.getenv("ROCKET_API_BASE")
        self.flaresolverr_url = os.getenv("FLARESOLVERR_URL")
        self.executor = ThreadPoolExecutor(max_workers=5)
        # Do not start task here

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """
        Start the rank check task when the bot is ready.
        """
        self.check_ranks.start()
        Logger.info("Rank check task started.")

    def fetch_stats_sync(self, platform: str, username: str) -> Optional[Dict[str, Any]]:
        """
        Synchronous fetch using external service.
        """
        url = f"{self.api_base}/standard/profile/{platform}/{username}"

        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 60000,
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/json",
            },
        }

        Logger.info(f"🔍 Fetching RL stats for {username} on {platform}: {url}")
        try:
            response = requests.post(self.flaresolverr_url, json=payload, timeout=60)
            if response.status_code != 200:
                Logger.warning(f"❌ External service error: {response.status_code}")
                return None
            data = response.json()
            if data.get("status") != "ok":
                Logger.warning(f"❌ External service failed: {data.get('message')}")
                return None
            # Get the actual response
            api_response = data["solution"]["response"]
            # Parse HTML to get JSON
            soup = BeautifulSoup(api_response, "html.parser")
            pre_tag = soup.find("pre")
            if not pre_tag:
                Logger.warning("Invalid response format")
                return None
            json_text = pre_tag.text
            api_data = json.loads(json_text)

            # Now process api_data as before
            if (
                "errors" in api_data
                and api_data["errors"][0]["code"] == "CollectorResultStatus::NotFound"
            ):
                Logger.warning(f"🚫 Player {username} not found")
                return None

            profile = api_data["data"]
            segments = profile["segments"]
            overview = next((s for s in segments if s["type"] == "overview"), None)
            if not overview:
                Logger.warning("No overview segment found")
                return None

            stats = overview["stats"]
            rank = stats.get("tier", {}).get("metadata", {}).get("name", "Unranked")
            season_reward_name = (
                stats.get("seasonRewardLevel", {})
                .get("metadata", {})
                .get("name", "N/A")
            )

            # Extract username
            username_display = profile["platformInfo"]["platformUserHandle"]

            # Extract ranks
            ranks = {}
            tier_names = {}
            icon_urls = {}
            highest_tier_val = 0
            highest_icon_url = None
            for segment in segments:
                if (
                    segment["type"] == "playlist"
                    and segment["attributes"].get("season") == 34
                ):
                    pid = segment["attributes"]["playlistId"]
                    name = segment["metadata"]["name"]
                    if pid == 10 or name == "Ranked Duel 1v1":  # 1v1
                        tier_name = segment["stats"]["tier"]["metadata"]["name"]
                        div_name = segment["stats"]["division"]["metadata"]["name"]
                        emoji = RANK_EMOJIS.get(
                            tier_name, "<:unranked:1425389712276721725>"
                        )
                        ranks["1v1"] = f"{emoji} {div_name}"
                        tier_names["1v1"] = tier_name
                        icon_urls["1v1"] = segment["stats"]["tier"]["metadata"][
                            "iconUrl"
                        ]
                        tier_val = segment["stats"]["tier"]["value"]
                        if tier_val > highest_tier_val:
                            highest_tier_val = tier_val
                            highest_icon_url = segment["stats"]["tier"]["metadata"][
                                "iconUrl"
                            ]
                    elif pid == 11 or name == "Ranked Doubles 2v2":  # 2v2
                        tier_name = segment["stats"]["tier"]["metadata"]["name"]
                        div_name = segment["stats"]["division"]["metadata"]["name"]
                        emoji = RANK_EMOJIS.get(
                            tier_name, "<:unranked:1425389712276721725>"
                        )
                        ranks["2v2"] = f"{emoji} {div_name}"
                        tier_names["2v2"] = tier_name
                        icon_urls["2v2"] = segment["stats"]["tier"]["metadata"][
                            "iconUrl"
                        ]
                        tier_val = segment["stats"]["tier"]["value"]
                        if tier_val > highest_tier_val:
                            highest_tier_val = tier_val
                            highest_icon_url = segment["stats"]["tier"]["metadata"][
                                "iconUrl"
                            ]
                    elif pid == 13 or name == "Ranked Standard 3v3":  # 3v3
                        tier_name = segment["stats"]["tier"]["metadata"]["name"]
                        div_name = segment["stats"]["division"]["metadata"]["name"]
                        emoji = RANK_EMOJIS.get(
                            tier_name, "<:unranked:1425389712276721725>"
                        )
                        ranks["3v3"] = f"{emoji} {div_name}"
                        tier_names["3v3"] = tier_name
                        icon_urls["3v3"] = segment["stats"]["tier"]["metadata"][
                            "iconUrl"
                        ]
                        tier_val = segment["stats"]["tier"]["value"]
                        if tier_val > highest_tier_val:
                            highest_tier_val = tier_val
                            highest_icon_url = segment["stats"]["tier"]["metadata"][
                                "iconUrl"
                            ]
                    elif name == "Ranked 4v4 Quads":  # 4v4
                        tier_name = segment["stats"]["tier"]["metadata"]["name"]
                        div_name = segment["stats"]["division"]["metadata"]["name"]
                        emoji = RANK_EMOJIS.get(
                            tier_name, "<:unranked:1425389712276721725>"
                        )
                        ranks["4v4"] = f"{emoji} {div_name}"
                        tier_names["4v4"] = tier_name
                        icon_urls["4v4"] = segment["stats"]["tier"]["metadata"][
                            "iconUrl"
                        ]
                        tier_val = segment["stats"]["tier"]["value"]
                        if tier_val > highest_tier_val:
                            highest_tier_val = tier_val
                            highest_icon_url = segment["stats"]["tier"]["metadata"][
                                "iconUrl"
                            ]

            # Set unavailable ranks to Unranked
            for key in ["1v1", "2v2", "3v3", "4v4"]:
                if key not in ranks:
                    ranks[key] = "<:unranked:1425389712276721725> Unranked"
                    tier_names[key] = "Unranked"

            season_emoji = RANK_EMOJIS.get(
                season_reward_name, "<:unranked:1425389712276721725>"
            )

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
                "icon_urls": icon_urls,
            }
        except requests.exceptions.RequestException as e:
            Logger.error(f"💥 Connection error: {e}")
            return None
        except json.JSONDecodeError as e:
            Logger.error(f"💥 JSON parse error: {e}")
            return None
        except Exception as e:
            Logger.error(f"💥 Error fetching stats for {username}: {e}")
            return None
        finally:
            import time

            time.sleep(8)  # Rate limit to avoid overwhelming the API

    async def get_player_stats(self, platform: str, username: str) -> Optional[Dict[str, Any]]:
        """
        Async wrapper for sync fetch with caching.
        """
        cache_key = f"rl_stats:{platform}:{username}"

        async def fetch_and_cache():
            loop = self.bot.loop
            return await loop.run_in_executor(
                self.executor, self.fetch_stats_sync, platform, username
            )

        # Cache for 1 hour (3600 seconds) since RL ranks don't change that frequently
        return await file_cache.get_or_set(cache_key, fetch_and_cache, ttl=3600)

    async def _get_rl_account(self, user_id: int, platform: Optional[str], username: Optional[str]) -> Tuple[str, str]:
        """
        Shared helper to get RL account details.
        Returns (platform, username) or raises ValueError with message.
        """
        accounts = load_rl_accounts()
        user_account = accounts.get(str(user_id))
        if not platform and not username:
            if not user_account:
                raise ValueError(
                    "❌ No account set. Use /setrlaccount or !setrlaccount"
                )
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

    @tasks.loop(hours=1)
    async def check_ranks(self) -> None:
        """
        Check for rank promotions every hour.
        """
        accounts = load_rl_accounts()
        now = datetime.now()
        guild = self.bot.get_guild(int(os.getenv("DISCORD_GUILD_ID")))
        if not guild:
            return
        channel = guild.get_channel(1425472657293443236)
        if not channel:
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
        for user_id, data in accounts.items():
            last_fetched_str = data.get("last_fetched")
            if last_fetched_str:
                last_fetched = datetime.fromisoformat(last_fetched_str)
                if now - last_fetched < timedelta(hours=1):
                    continue  # Skip if less than 1 hour
            platform = data["platform"]
            username = data["username"]
            old_ranks = data.get("ranks", {})
            stats = await self.get_player_stats(platform, username)
            if stats:
                new_ranks = stats["tier_names"]
                new_icon_urls = stats.get("icon_urls", {})
                user = self.bot.get_user(int(user_id))
                if user:
                    for playlist, new_tier in new_ranks.items():
                        old_tier = old_ranks.get(playlist, "Unranked")
                        if new_tier != old_tier and tier_order.index(
                            new_tier
                        ) > tier_order.index(old_tier):
                            emoji = RANK_EMOJIS.get(
                                new_tier, "<:unranked:1425389712276721725>"
                            )
                            icon_url = new_icon_urls.get(playlist)
                            # Sende die Notification als separate Nachricht vor dem Embed
                            await channel.send(
                                f"{user.mention} 🚀 Rank Promotion Notification!"
                            )
                            embed = discord.Embed(
                                title="🎉 Rank Promotion! 🎉",
                                description=f"Congratulations {user.mention}! Your {playlist} rank has improved to {emoji} {new_tier}!",
                                color=PINK,
                            )
                            if icon_url:
                                embed.set_thumbnail(url=icon_url)
                            set_pink_footer(embed, bot=self.bot.user)
                            await channel.send(embed=embed)
                            Logger.info(
                                f"Rank promotion notified for {user}: {playlist} {old_tier} -> {new_tier}"
                            )
                # Update ranks and last_fetched
                data["ranks"] = new_ranks
                data["icon_urls"] = new_icon_urls
                data["last_fetched"] = now.isoformat()
                save_rl_accounts(accounts)

    @commands.command(name="setrlaccount")
    async def setrlaccount(self, ctx: commands.Context, platform: str, *, username: str) -> None:
        """
        🚀 Set your main Rocket League account.
        Usage: !setrlaccount <platform> <username>
        """
        if platform.lower() not in ["steam", "epic", "psn", "xbl", "switch"]:
            await ctx.send("❌ Invalid platform.")
            return
        stats = await self.get_player_stats(platform.lower(), username)
        initial_ranks = {
            "1v1": "Unranked",
            "2v2": "Unranked",
            "3v3": "Unranked",
            "4v4": "Unranked",
        }
        if stats:
            initial_ranks = stats["tier_names"]
        accounts = load_rl_accounts()
        accounts[str(ctx.author.id)] = {
            "platform": platform.lower(),
            "username": username,
            "ranks": initial_ranks,
        }
        save_rl_accounts(accounts)
        await ctx.send(f"✅ Set your RL account to {username} on {platform}.")

    @app_commands.command(
        name="setrlaccount", description="Set your main Rocket League account"
    )
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    @app_commands.describe(platform="Platform", username="Username")
    async def setrlaccount_slash(
        self, interaction: discord.Interaction, platform: str, username: str
    ) -> None:
        if platform.lower() not in ["steam", "epic", "psn", "xbl", "switch"]:
            await interaction.response.send_message(
                "❌ Invalid platform.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)  # <--- Defer first!
        stats = await self.get_player_stats(platform.lower(), username)
        initial_ranks = {
            "1v1": "Unranked",
            "2v2": "Unranked",
            "3v3": "Unranked",
            "4v4": "Unranked",
        }
        if stats:
            initial_ranks = stats["tier_names"]
        accounts = load_rl_accounts()
        accounts[str(interaction.user.id)] = {
            "platform": platform.lower(),
            "username": username,
            "ranks": initial_ranks,
        }
        save_rl_accounts(accounts)
        await interaction.followup.send(
            f"✅ Set your RL account to {username} on {platform}.", ephemeral=True
        )

    @commands.command(name="rlstats")
    async def rlstats(self, ctx: commands.Context, platform: Optional[str] = None, *, username: Optional[str] = None) -> None:
        """
        🚀 Get Rocket League stats for a player or your set account.
        Usage: !rlstats [platform] [username]
        If no args, uses your set account.
        """
        try:
            platform, username = await self._get_rl_account(
                ctx.author.id, platform, username
            )
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
        Logger.info(f"Rocket League stats requested for {username} by {ctx.author}")

    @app_commands.command(
        name="rlstats",
        description="🚀 Get Rocket League stats for a player or your set account",
    )
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    @app_commands.describe(
        platform="Platform (optional if set)", username="Username (optional if set)"
    )
    async def rlstats_slash(
        self,
        interaction: discord.Interaction,
        platform: Optional[str] = None,
        username: Optional[str] = None,
    ) -> None:
        """
        🚀 Get Rocket League stats for a player.
        """
        try:
            platform, username = await self._get_rl_account(
                interaction.user.id, platform, username
            )
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        await interaction.response.defer()
        stats = await self.get_player_stats(platform, username)
        if not stats:
            await interaction.followup.send(
                "❌ Player not found or error fetching stats."
            )
            return

        embed = await self._create_rl_embed(stats, platform)
        await interaction.followup.send(embed=embed)

    async def cog_unload(self) -> None:
        await self.session.close()
        self.executor.shutdown()


async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the RocketLeague cog.
    """
    await bot.add_cog(RocketLeague(bot))
