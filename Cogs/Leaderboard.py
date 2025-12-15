import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, List

import discord
from discord import app_commands
from discord.ext import commands

import Config
from Cogs.RocketLeague import RANK_EMOJIS, load_rl_accounts
from Cogs.TicketSystem import load_tickets
from Config import ACTIVITY_FILE, RL_TIER_ORDER, get_data_dir, get_guild_id
from Utils.CacheUtils import cache
from Utils.EmbedUtils import set_pink_footer

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Helper to load activity data
@cache(ttl_seconds=30)  # Cache for 30 seconds since activity data changes frequently
async def load_activity() -> Dict[str, Any]:
    if not os.path.exists(ACTIVITY_FILE):
        return {}
    with open(ACTIVITY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# Helper to load meme requests data
@cache(ttl_seconds=30)  # Cache for 30 seconds
async def load_meme_requests() -> Dict[str, int]:
    file_path = os.path.join(get_data_dir(), "meme_requests.json")
    if not os.path.exists(file_path):
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Helper to load memes generated data
@cache(ttl_seconds=30)  # Cache for 30 seconds
async def load_memes_generated() -> Dict[str, int]:
    file_path = os.path.join(get_data_dir(), "memes_generated.json")
    if not os.path.exists(file_path):
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Helper to load XP/Level leaderboard
@cache(ttl_seconds=300)  # Cache for 5 minutes
async def load_xp_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Load XP/Level leaderboard from database."""
    try:
        db_path = Path(Config.get_data_dir()) / "user_levels.db"
        if not db_path.exists():
            return []
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT user_id, username, total_xp, current_level
            FROM user_xp
            ORDER BY total_xp DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        leaderboard = []
        for row in rows:
            user_id = row["user_id"]
            username = row["username"]
            total_xp = row["total_xp"]
            level = row["current_level"]
            
            # Get tier info using Config function (includes emoji)
            tier_info = Config.get_level_tier(level)
            
            leaderboard.append({
                "user_id": user_id,
                "username": username,
                "total_xp": total_xp,
                "level": level,
                "tier_name": tier_info["name"],
                "tier_emoji": tier_info["emoji"],
            })
        
        return leaderboard
    except Exception as e:
        logger.error(f"Error loading XP leaderboard: {e}")
        return []


def save_activity(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(ACTIVITY_FILE), exist_ok=True)
    with open(ACTIVITY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


# Helper to get activity for a user
async def get_user_activity(user_id: str) -> Dict[str, int]:
    activity = await load_activity()
    return activity.get(str(user_id), {"messages": 0, "images": 0})


class Leaderboard(commands.Cog):
    """
    🏆 Leaderboard Cog: Shows various leaderboards like RL ranks, resolved tickets, and activity.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # Listener to track activity
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        activity = await load_activity()
        user_id = str(message.author.id)
        if user_id not in activity:
            activity[user_id] = {"messages": 0, "images": 0}
        activity[user_id]["messages"] += 1
        if message.attachments:
            activity[user_id]["images"] += len(message.attachments)
        save_activity(activity)

    # Shared helper to create leaderboard embed
    def create_leaderboard_embed(
        self, title: str, data_list: List[tuple], value_formatter: Callable[[Any], str] = lambda x: x
    ) -> discord.Embed:
        embed = discord.Embed(title=f"🏆 {title}", color=Config.PINK)
        if not data_list:
            embed.add_field(name="No Data", value="No entries found.", inline=False)
        else:
            text = "\n".join(
                [f"{i + 1}. <@{uid}>: {value_formatter(val)}" for i, (uid, val) in enumerate(data_list[:10])]
            )
            embed.add_field(name="Top 10", value=text, inline=False)
        set_pink_footer(embed, bot=self.bot.user)
        return embed

    async def create_xp_leaderboard_embed(self, leaderboard: List[Dict[str, Any]]) -> discord.Embed:
        """Create an embed for XP/Level leaderboard with consistent formatting."""
        embed = discord.Embed(title="⭐ XP & Levels Leaderboard", color=Config.PINK)
        
        if not leaderboard:
            embed.add_field(name="No Data", value="No XP data found yet.", inline=False)
        else:
            # Medal emojis for top 3
            medals = ["🥇", "🥈", "🥉"]
            
            entries = []
            for i, entry in enumerate(leaderboard[:10]):
                rank_display = medals[i] if i < 3 else f"{i + 1}."
                tier_emoji = entry["tier_emoji"]
                username = entry["username"]
                level = entry["level"]
                total_xp = entry["total_xp"]
                tier_name = entry["tier_name"]
                
                # Format: 🥇 Username - Level 25 👑 (Legendary) • 15,000 XP
                entry_text = (
                    f"{rank_display} **{username}** - Level {level} {tier_emoji} "
                    f"({tier_name.title()}) • {total_xp:,} XP"
                )
                entries.append(entry_text)
            
            embed.description = "\n".join(entries)
        
        set_pink_footer(embed, bot=self.bot.user)
        return embed

    # Helper to get top entries for a category (used for overview)
    async def get_top_entries(self, category: str, limit: int = 3) -> List[tuple]:
        if category == "rl_overall":
            accounts = load_rl_accounts()
            data = {}
            for uid, acc in accounts.items():
                ranks = acc.get("ranks", {})
                highest_tier = "Unranked"
                for tier in ranks.values():
                    if tier in RL_TIER_ORDER and RL_TIER_ORDER.index(tier) > RL_TIER_ORDER.index(highest_tier):
                        highest_tier = tier
                if highest_tier != "Unranked":
                    data[uid] = RL_TIER_ORDER.index(highest_tier)
            sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
            return [(uid, RL_TIER_ORDER[idx]) for uid, idx in sorted_data[:limit]]
        elif category.startswith("rl_"):
            playlist = category.split("_")[1]
            accounts = load_rl_accounts()
            data = {}
            for uid, acc in accounts.items():
                ranks = acc.get("ranks", {})
                tier = ranks.get(playlist, "Unranked")
                if tier != "Unranked":
                    data[uid] = RL_TIER_ORDER.index(tier)
            sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
            return [(uid, RL_TIER_ORDER[idx]) for uid, idx in sorted_data[:limit]]
        elif category == "tickets":
            tickets = await load_tickets()
            data = {}
            for ticket in tickets:
                if ticket["status"] == "Closed":
                    for key in ["claimed_by", "assigned_to"]:
                        uid = ticket.get(key)
                        if uid:
                            data[uid] = data.get(uid, 0) + 1
            sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
            return sorted_data[:limit]
        elif category == "messages":
            activity = await load_activity()
            data = {uid: stats["messages"] for uid, stats in activity.items()}
            sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
            return sorted_data[:limit]
        elif category == "images":
            activity = await load_activity()
            data = {uid: stats["images"] for uid, stats in activity.items()}
            sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
            return sorted_data[:limit]
        elif category == "meme_requests":
            meme_requests = await load_meme_requests()
            sorted_data = sorted(meme_requests.items(), key=lambda x: x[1], reverse=True)
            return sorted_data[:limit]
        elif category == "memes_generated":
            memes_generated = await load_memes_generated()
            sorted_data = sorted(memes_generated.items(), key=lambda x: x[1], reverse=True)
            return sorted_data[:limit]
        return []

    # Create overview embed with all leaderboards
    async def create_overview_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🏆 Leaderboard Overview", description="Top performers in various categories", color=Config.PINK
        )

        # XP & Levels
        xp_leaderboard = await load_xp_leaderboard(limit=3)
        if xp_leaderboard:
            xp_text = ""
            for i, entry in enumerate(xp_leaderboard):
                xp_text += f"{i + 1}. <@{entry['user_id']}> (Level {entry['level']} {entry['tier_emoji']} - {entry['total_xp']:,} XP)\n"
            embed.add_field(name="⭐ XP & Levels", value=xp_text.strip(), inline=False)

        # Rocket League Rankings
        rl_text = ""
        rl_categories = [("rl_overall", "Overall"), ("rl_1v1", "1v1"), ("rl_2v2", "2v2"), ("rl_3v3", "3v3")]
        for cat_key, cat_name in rl_categories:
            top_entries = await self.get_top_entries(cat_key, limit=3)
            if top_entries:
                entries_str = ", ".join([f"{i + 1}. <@{uid}> ({val})" for i, (uid, val) in enumerate(top_entries)])
                rl_text += f"**{cat_name}**: {entries_str}\n"
        if rl_text:
            embed.add_field(name="🚀 Rocket League Rankings", value=rl_text.strip(), inline=False)

        # Activity
        activity_text = ""
        activity_categories = [
            ("messages", "Messages"),
            ("images", "Images"),
            ("meme_requests", "Meme Requests"),
            ("memes_generated", "Memes Generated"),
        ]
        for cat_key, cat_name in activity_categories:
            top_entries = await self.get_top_entries(cat_key, limit=3)
            if top_entries:
                entries_str = ", ".join([f"{i + 1}. <@{uid}> ({val})" for i, (uid, val) in enumerate(top_entries)])
                activity_text += f"**{cat_name}**: {entries_str}\n"
        if activity_text:
            embed.add_field(name="📊 Activity", value=activity_text.strip(), inline=False)

        # Contributions
        contrib_text = ""
        contrib_categories = [("tickets", "Resolved Tickets")]
        for cat_key, cat_name in contrib_categories:
            top_entries = await self.get_top_entries(cat_key, limit=3)
            if top_entries:
                entries_str = ", ".join([f"{i + 1}. <@{uid}> ({val})" for i, (uid, val) in enumerate(top_entries)])
                contrib_text += f"**{cat_name}**: {entries_str}\n"
        if contrib_text:
            embed.add_field(name="🛠️ Contributions", value=contrib_text.strip(), inline=False)

        embed.set_footer(text="Use /leaderboard <category> for full rankings")
        return embed

    # 🧩 Shared handler for leaderboard logic
    async def handle_leaderboard(self, ctx_or_interaction: Any, category: str) -> None:
        if category == "xp":
            leaderboard = await load_xp_leaderboard(limit=10)
            embed = await self.create_xp_leaderboard_embed(leaderboard)
        elif category == "rl_overall":
            accounts = load_rl_accounts()
            data = {}
            for uid, acc in accounts.items():
                ranks = acc.get("ranks", {})
                highest_tier = "Unranked"
                for tier in ranks.values():
                    if tier in RL_TIER_ORDER and RL_TIER_ORDER.index(tier) > RL_TIER_ORDER.index(highest_tier):
                        highest_tier = tier
                if highest_tier != "Unranked":
                    data[uid] = RL_TIER_ORDER.index(highest_tier)
            sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
            embed = self.create_leaderboard_embed(
                "Highest RL Ranks Overall",
                sorted_data,
                lambda idx: f"{RANK_EMOJIS.get(RL_TIER_ORDER[idx], '<:unranked:1425389712276721725>')} {RL_TIER_ORDER[idx]}",
            )
        elif category.startswith("rl_"):
            playlist = category.split("_")[1]
            accounts = load_rl_accounts()
            data = {}
            for uid, acc in accounts.items():
                ranks = acc.get("ranks", {})
                tier = ranks.get(playlist, "Unranked")
                if tier != "Unranked":
                    data[uid] = RL_TIER_ORDER.index(tier)
            sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
            embed = self.create_leaderboard_embed(
                f"Highest RL Ranks {playlist.upper()}",
                sorted_data,
                lambda idx: f"{RANK_EMOJIS.get(RL_TIER_ORDER[idx], '<:unranked:1425389712276721725>')} {RL_TIER_ORDER[idx]}",
            )
        elif category == "tickets":
            tickets = await load_tickets()  # Added await since load_tickets is now async
            data = {}
            for ticket in tickets:
                if ticket["status"] == "Closed":
                    for key in ["claimed_by", "assigned_to"]:
                        uid = ticket.get(key)
                        if uid:
                            data[uid] = data.get(uid, 0) + 1
            sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
            embed = self.create_leaderboard_embed("Resolved Tickets", sorted_data)
        elif category == "messages":
            activity = await load_activity()
            data = {uid: stats["messages"] for uid, stats in activity.items()}
            sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
            embed = self.create_leaderboard_embed("Most Messages", sorted_data)
        elif category == "images":
            activity = await load_activity()
            data = {uid: stats["images"] for uid, stats in activity.items()}
            sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
            embed = self.create_leaderboard_embed("Most Images Posted", sorted_data)
        elif category == "meme_requests":
            meme_requests = await load_meme_requests()
            sorted_data = sorted(meme_requests.items(), key=lambda x: x[1], reverse=True)
            embed = self.create_leaderboard_embed("Most Meme Requests", sorted_data)
        elif category == "memes_generated":
            memes_generated = await load_memes_generated()
            sorted_data = sorted(memes_generated.items(), key=lambda x: x[1], reverse=True)
            embed = self.create_leaderboard_embed("Most Memes Generated", sorted_data)
        else:
            embed = discord.Embed(
                title="❌ Invalid Category",
                description="Use: rl_overall, rl_1v1, rl_2v2, rl_3v3, rl_4v4, tickets, messages, images, meme_requests, memes_generated",
                color=Config.PINK,
            )
            set_pink_footer(embed, bot=self.bot.user)

        if hasattr(ctx_or_interaction, "send"):
            await ctx_or_interaction.send(embed=embed)
        else:
            await ctx_or_interaction.response.send_message(embed=embed, ephemeral=False)

    # !leaderboard (Prefix)
    @commands.command(name="leaderboard")
    async def leaderboard_command(self, ctx: commands.Context, category: str = None) -> None:
        """
        🏆 Shows leaderboard overview or specific category.
        Categories: rl_overall, rl_1v1, rl_2v2, rl_3v3, rl_4v4, tickets, messages, images, meme_requests, memes_generated
        """
        if category:
            logger.info(f"Leaderboard requested for category '{category}' by {ctx.author}")
            await self.handle_leaderboard(ctx, category.lower())
        else:
            logger.info(f"Leaderboard overview requested by {ctx.author}")
            embed = await self.create_overview_embed()
            await ctx.send(embed=embed)

        # /leaderboard (Slash)

    @app_commands.command(name="leaderboard", description="🏆 Shows leaderboard overview or specific category.")
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    @app_commands.describe(category="Choose the leaderboard category (optional for overview)")
    @app_commands.choices(
        category=[
            app_commands.Choice(name="⭐ XP & Levels", value="xp"),
            app_commands.Choice(name="RL Overall Highest", value="rl_overall"),
            app_commands.Choice(name="RL 1v1 Ranks", value="rl_1v1"),
            app_commands.Choice(name="RL 2v2 Ranks", value="rl_2v2"),
            app_commands.Choice(name="RL 3v3 Ranks", value="rl_3v3"),
            app_commands.Choice(name="RL 4v4 Ranks", value="rl_4v4"),
            app_commands.Choice(name="Resolved Tickets", value="tickets"),
            app_commands.Choice(name="Most Messages", value="messages"),
            app_commands.Choice(name="Most Images", value="images"),
            app_commands.Choice(name="Most Meme Requests", value="meme_requests"),
            app_commands.Choice(name="Most Memes Generated", value="memes_generated"),
        ]
    )
    async def leaderboard_slash(self, interaction: discord.Interaction, category: str = None) -> None:
        if category:
            logger.info(f"Leaderboard slash requested for category '{category}' by {interaction.user}")
            await self.handle_leaderboard(interaction, category)
        else:
            logger.info(f"Leaderboard overview slash requested by {interaction.user}")
            embed = await self.create_overview_embed()
            await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))
