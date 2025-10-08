import aiohttp
import cloudscraper
import os
import json
from concurrent.futures import ThreadPoolExecutor
from discord.ext import commands, tasks
import discord
from discord import app_commands
from Config import PINK
from Utils.EmbedUtils import set_pink_footer
from Utils.Logger import Logger

RANK_EMOJIS = {
    'Supersonic Legend': '<:ssl:1425389967030489139>',
    'Grand Champion III': '<:gc3:1425389956796518420>',
    'Grand Champion II': '<:gc2:1425389941810266162>',
    'Grand Champion I': '<:gc1:1425389930225471499>',
    'Champion III': '<:c3:1425389912651464824>',
    'Champion II': '<:c2:1425389901670776842>',
    'Champion I': '<:c1:1425389889796706374>',
    'Diamond III': '<:d3:1425389878673149962>',
    'Diamond II': '<:d2:1425389867197665361>',
    'Diamond I': '<:d1:1425389856229691462>',
    'Platinum III': '<:p3:1425389845328433213>',
    'Platinum II': '<:p2:1425389833706278923>',
    'Platinum I': '<:p1:1425389821706113055>',
    'Gold III': '<:g3:1425389810968690749>',
    'Gold II': '<:g2:1425389799463981217>',
    'Gold I': '<:g1:1425389788885811380>',
    'Silver III': '<:s3:1425389776852221982>',
    'Silver II': '<:s2:1425389768425996341>',
    'Silver I': '<:s1:1425389757940367411>',
    'Bronze III': '<:b3:1425389747282382919>',
    'Bronze II': '<:b2:1425389735819350056>',
    'Bronze I': '<:b1:1425389725652615209>',
    'Unranked': '<:unranked:1425389712276721725>',
}

RL_ACCOUNTS_FILE = 'rl_accounts.json'

def load_rl_accounts():
    if os.path.exists(RL_ACCOUNTS_FILE):
        with open(RL_ACCOUNTS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_rl_accounts(accounts):
    with open(RL_ACCOUNTS_FILE, 'w') as f:
        json.dump(accounts, f, indent=4)

class RocketLeague(commands.Cog):
    """
    🚀 Rocket League Cog: Fetches player stats using requests in thread.
    """

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.api_base = os.getenv("ROCKET_API_BASE")
        self.executor = ThreadPoolExecutor(max_workers=5)
        # Do not start task here

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Start the rank check task when the bot is ready.
        """
        self.check_ranks.start()
        Logger.info("Rank check task started.")

    def fetch_stats_sync(self, platform, username):
        """
        Synchronous fetch using cloudscraper to bypass Cloudflare.
        """
        url = f"{self.api_base}/standard/profile/{platform}/{username}"
        headers = {
            'User-Agent': 'Chrome/79',
            'Accept': 'application/json'
        }

        Logger.info(f"🔍 Fetching RL stats for {username} on {platform}: {url}")
        scraper = cloudscraper.create_scraper()
        try:
            response = scraper.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                Logger.warning(f"❌ Bad response for {username}: {response.status_code}")
                return None
            data = response.json()
            
            if 'errors' in data and data['errors'][0]['code'] == 'CollectorResultStatus::NotFound':
                Logger.warning(f"🚫 Player {username} not found")
                return None
            
            profile = data['data']
            segments = profile['segments']
            overview = next((s for s in segments if s['type'] == 'overview'), None)
            if not overview:
                Logger.warning("No overview segment found")
                return None
            
            stats = overview['stats']
            rank = stats.get('tier', {}).get('metadata', {}).get('name', 'Unranked')
            season_reward_level = stats.get('seasonRewardLevel', {}).get('value', 'N/A')
            season_reward_name = stats.get('seasonRewardLevel', {}).get('metadata', {}).get('rankName', 'None')
            
            # Extract username
            username_display = profile['platformInfo']['platformUserHandle']
            
            # Extract ranks
            ranks = {}
            tier_names = {}
            highest_tier_val = 0
            highest_tier_name = 'Unranked'
            highest_icon_url = None
            for segment in segments:
                if segment['type'] == 'playlist' and segment['attributes'].get('season') == 34:
                    pid = segment['attributes']['playlistId']
                    name = segment['metadata']['name']
                    if pid == 10 or name == 'Ranked Duel 1v1':  # 1v1
                        tier_name = segment['stats']['tier']['metadata']['name']
                        div_name = segment['stats']['division']['metadata']['name']
                        emoji = RANK_EMOJIS.get(tier_name, '<:unranked:1425389712276721725>')
                        ranks['1v1'] = f"{emoji} {div_name}"
                        tier_names['1v1'] = tier_name
                        tier_val = segment['stats']['tier']['value']
                        icon_url = segment['stats']['tier']['metadata']['iconUrl']
                        if tier_val > highest_tier_val:
                            highest_tier_val = tier_val
                            highest_tier_name = tier_name
                            highest_icon_url = icon_url
                    elif pid == 11 or name == 'Ranked Doubles 2v2':  # 2v2
                        tier_name = segment['stats']['tier']['metadata']['name']
                        div_name = segment['stats']['division']['metadata']['name']
                        emoji = RANK_EMOJIS.get(tier_name, '<:unranked:1425389712276721725>')
                        ranks['2v2'] = f"{emoji} {div_name}"
                        tier_names['2v2'] = tier_name
                        tier_val = segment['stats']['tier']['value']
                        icon_url = segment['stats']['tier']['metadata']['iconUrl']
                        if tier_val > highest_tier_val:
                            highest_tier_val = tier_val
                            highest_tier_name = tier_name
                            highest_icon_url = icon_url
                    elif pid == 13 or name == 'Ranked Standard 3v3':  # 3v3
                        tier_name = segment['stats']['tier']['metadata']['name']
                        div_name = segment['stats']['division']['metadata']['name']
                        emoji = RANK_EMOJIS.get(tier_name, '<:unranked:1425389712276721725>')
                        ranks['3v3'] = f"{emoji} {div_name}"
                        tier_names['3v3'] = tier_name
                        tier_val = segment['stats']['tier']['value']
                        icon_url = segment['stats']['tier']['metadata']['iconUrl']
                        if tier_val > highest_tier_val:
                            highest_tier_val = tier_val
                            highest_tier_name = tier_name
                            highest_icon_url = icon_url
                    elif name == 'Ranked 4v4 Quads':  # 4v4
                        tier_name = segment['stats']['tier']['metadata']['name']
                        div_name = segment['stats']['division']['metadata']['name']
                        emoji = RANK_EMOJIS.get(tier_name, '<:unranked:1425389712276721725>')
                        ranks['4v4'] = f"{emoji} {div_name}"
                        tier_names['4v4'] = tier_name
                        tier_val = segment['stats']['tier']['value']
                        icon_url = segment['stats']['tier']['metadata']['iconUrl']
                        if tier_val > highest_tier_val:
                            highest_tier_val = tier_val
                            highest_tier_name = tier_name
                            highest_icon_url = icon_url
            
            # Set unavailable ranks to Unranked
            for key in ['1v1', '2v2', '3v3', '4v4']:
                if key not in ranks:
                    ranks[key] = '<:unranked:1425389712276721725> Unranked'
                    tier_names[key] = 'Unranked'
            
            season_emoji = RANK_EMOJIS.get(season_reward_name, '<:unranked:1425389712276721725>')
            
            return {
                'username': username_display,
                'rank': rank,
                'season_reward': f"{season_emoji} {season_reward_name}",
                'rank_1v1': ranks['1v1'],
                'rank_2v2': ranks['2v2'],
                'rank_3v3': ranks['3v3'],
                'rank_4v4': ranks['4v4'],
                'highest_icon_url': highest_icon_url,
                'tier_names': tier_names,
            }
        except Exception as e:
            Logger.error(f"💥 Error fetching stats for {username}: {e}")
            return None
        finally:
            import time
            time.sleep(2)  # Rate limit to avoid overwhelming the API

    async def get_player_stats(self, platform, username):
        """
        Async wrapper for sync fetch.
        """
        loop = self.bot.loop
        return await loop.run_in_executor(self.executor, self.fetch_stats_sync, platform, username)

    async def _get_rl_account(self, user_id, platform, username):
        """
        Shared helper to get RL account details.
        Returns (platform, username) or raises ValueError with message.
        """
        accounts = load_rl_accounts()
        user_account = accounts.get(str(user_id))
        if not platform and not username:
            if not user_account:
                raise ValueError("❌ No account set. Use /setrlaccount or !setrlaccount")
            platform = user_account['platform']
            username = user_account['username']
        elif not username:
            raise ValueError("❌ Provide username or set account.")
        if platform.lower() not in ['steam', 'epic', 'psn', 'xbl', 'switch']:
            raise ValueError("❌ Invalid platform.")
        return platform.lower(), username

    async def _create_rl_embed(self, stats, platform):
        """
        Shared helper to create the RL stats embed.
        """
        embed = discord.Embed(
            title=f"Rocket League Stats for {stats['username']} ({platform.upper()})",
            color=PINK
        )
        if stats.get('highest_icon_url'):
            embed.set_thumbnail(url=stats['highest_icon_url'])
        embed.add_field(name="Rank 1v1", value=stats['rank_1v1'], inline=True)
        embed.add_field(name="Rank 2v2", value=stats['rank_2v2'], inline=True)
        embed.add_field(name="Rank 3v3", value=stats['rank_3v3'], inline=True)
        embed.add_field(name="Rank 4v4", value=stats['rank_4v4'], inline=True)
        embed.add_field(name="Season Reward", value=stats['season_reward'], inline=True)
        set_pink_footer(embed, bot=self.bot.user)
        return embed

    @tasks.loop(hours=1)
    async def check_ranks(self):
        """
        Check for rank promotions every hour.
        """
        accounts = load_rl_accounts()
        guild = self.bot.get_guild(int(os.getenv("DISCORD_GUILD_ID")))
        if not guild:
            return
        channel = guild.get_channel(1425472657293443236)
        if not channel:
            return
        tier_order = ['Unranked', 'Bronze I', 'Bronze II', 'Bronze III', 'Silver I', 'Silver II', 'Silver III', 'Gold I', 'Gold II', 'Gold III', 'Platinum I', 'Platinum II', 'Platinum III', 'Diamond I', 'Diamond II', 'Diamond III', 'Champion I', 'Champion II', 'Champion III', 'Grand Champion I', 'Grand Champion II', 'Grand Champion III', 'Supersonic Legend']
        for user_id, data in accounts.items():
            platform = data['platform']
            username = data['username']
            old_ranks = data.get('ranks', {})
            stats = await self.get_player_stats(platform, username)
            if stats:
                new_ranks = stats['tier_names']
                user = self.bot.get_user(int(user_id))
                if user:
                    for playlist, new_tier in new_ranks.items():
                        old_tier = old_ranks.get(playlist, 'Unranked')
                        if new_tier != old_tier and tier_order.index(new_tier) > tier_order.index(old_tier):
                            await channel.send(f"Congratulations! {user.mention} Your {playlist} rank has improved to {new_tier}!")
                            Logger.info(f"Rank promotion notified for {user}: {playlist} {old_tier} -> {new_tier}")
                # Update ranks
                data['ranks'] = new_ranks
                save_rl_accounts(accounts)

    @commands.command(name="setrlaccount")
    async def setrlaccount(self, ctx, platform: str, *, username: str):
        """
        🚀 Set your main Rocket League account.
        Usage: !setrlaccount <platform> <username>
        """
        if platform.lower() not in ['steam', 'epic', 'psn', 'xbl', 'switch']:
            await ctx.send("❌ Invalid platform.")
            return
        stats = await self.get_player_stats(platform.lower(), username)
        initial_ranks = {'1v1': 'Unranked', '2v2': 'Unranked', '3v3': 'Unranked', '4v4': 'Unranked'}
        if stats:
            initial_ranks = stats['tier_names']
        accounts = load_rl_accounts()
        accounts[str(ctx.author.id)] = {'platform': platform.lower(), 'username': username, 'ranks': initial_ranks}
        save_rl_accounts(accounts)
        await ctx.send(f"✅ Set your RL account to {username} on {platform}.")

    @app_commands.command(name="setrlaccount", description="Set your main Rocket League account")
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    @app_commands.describe(platform="Platform", username="Username")
    async def setrlaccount_slash(self, interaction: discord.Interaction, platform: str, username: str):
        if platform.lower() not in ['steam', 'epic', 'psn', 'xbl', 'switch']:
            await interaction.response.send_message("❌ Invalid platform.", ephemeral=True)
            return
        stats = await self.get_player_stats(platform.lower(), username)
        initial_ranks = {'1v1': 'Unranked', '2v2': 'Unranked', '3v3': 'Unranked', '4v4': 'Unranked'}
        if stats:
            initial_ranks = stats['tier_names']
        accounts = load_rl_accounts()
        accounts[str(interaction.user.id)] = {'platform': platform.lower(), 'username': username, 'ranks': initial_ranks}
        save_rl_accounts(accounts)
        await interaction.response.send_message(f"✅ Set your RL account to {username} on {platform}.", ephemeral=True)

    @commands.command(name="rlstats")
    async def rlstats(self, ctx, platform: str = None, *, username: str = None):
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
        Logger.info(f"Rocket League stats requested for {username} by {ctx.author}")

    @app_commands.command(name="rlstats", description="🚀 Get Rocket League stats for a player or your set account")
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    @app_commands.describe(platform="Platform (optional if set)", username="Username (optional if set)")
    async def rlstats_slash(self, interaction: discord.Interaction, platform: str = None, username: str = None):
        """
        🚀 Get Rocket League stats for a player.
        """
        try:
            platform, username = await self._get_rl_account(interaction.user.id, platform, username)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return
        
        await interaction.response.defer()
        stats = await self.get_player_stats(platform, username)
        if not stats:
            await interaction.followup.send("❌ Player not found or error fetching stats.")
            return
        
        embed = await self._create_rl_embed(stats, platform)
        await interaction.followup.send(embed=embed)

    async def cog_unload(self):
        await self.session.close()
        self.executor.shutdown()

async def setup(bot):
    """
    Setup function to add the RocketLeague cog.
    """
    await bot.add_cog(RocketLeague(bot))