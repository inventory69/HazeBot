import discord
from discord.ext import commands
from discord import app_commands
import os
import json
from typing import Dict, List, Callable, Any
from Config import PINK, RL_TIER_ORDER, ACTIVITY_FILE, get_guild_id
from Utils.EmbedUtils import set_pink_footer
from Cogs.RocketLeague import load_rl_accounts, RANK_EMOJIS
from Utils.CacheUtils import cache
from Cogs.TicketSystem import load_tickets


# Helper to load activity data
@cache(ttl_seconds=30)  # Cache for 30 seconds since activity data changes frequently
async def load_activity() -> Dict[str, Any]:
    if not os.path.exists(ACTIVITY_FILE):
        return {}
    with open(ACTIVITY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


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
        embed = discord.Embed(title=f"🏆 {title}", color=PINK)
        if not data_list:
            embed.add_field(name="No Data", value="No entries found.", inline=False)
        else:
            text = "\n".join(
                [f"{i + 1}. <@{uid}>: {value_formatter(val)}" for i, (uid, val) in enumerate(data_list[:10])]
            )
            embed.add_field(name="Top 10", value=text, inline=False)
        set_pink_footer(embed, bot=self.bot.user)
        return embed

    # 🧩 Shared handler for leaderboard logic
    async def handle_leaderboard(self, ctx_or_interaction: Any, category: str) -> None:
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
        else:
            embed = discord.Embed(
                title="❌ Invalid Category",
                description="Use: rl_overall, rl_1v1, rl_2v2, rl_3v3, rl_4v4, tickets, messages, images",
                color=PINK,
            )
            set_pink_footer(embed, bot=self.bot.user)

        if hasattr(ctx_or_interaction, "send"):
            await ctx_or_interaction.send(embed=embed)
        else:
            await ctx_or_interaction.response.send_message(embed=embed, ephemeral=False)

    # !leaderboard (Prefix)
    @commands.command(name="leaderboard")
    async def leaderboard_command(self, ctx: commands.Context, category: str) -> None:
        """
        🏆 Shows a leaderboard for the given category.
        Categories: rl_overall, rl_1v1, rl_2v2, rl_3v3, rl_4v4, tickets, messages, images
        """
        await self.handle_leaderboard(ctx, category.lower())

    # /leaderboard (Slash)
    @app_commands.command(name="leaderboard", description="🏆 Shows a leaderboard for various categories.")
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    @app_commands.describe(category="Choose the leaderboard category")
    @app_commands.choices(
        category=[
            app_commands.Choice(name="RL Overall Highest", value="rl_overall"),
            app_commands.Choice(name="RL 1v1 Ranks", value="rl_1v1"),
            app_commands.Choice(name="RL 2v2 Ranks", value="rl_2v2"),
            app_commands.Choice(name="RL 3v3 Ranks", value="rl_3v3"),
            app_commands.Choice(name="RL 4v4 Ranks", value="rl_4v4"),
            app_commands.Choice(name="Resolved Tickets", value="tickets"),
            app_commands.Choice(name="Most Messages", value="messages"),
            app_commands.Choice(name="Most Images", value="images"),
        ]
    )
    async def leaderboard_slash(self, interaction: discord.Interaction, category: str) -> None:
        await self.handle_leaderboard(interaction, category)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))
