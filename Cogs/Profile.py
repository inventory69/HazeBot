import logging
import sqlite3
from pathlib import Path
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands

import Config
from Cogs.Leaderboard import get_user_activity
from Cogs.ModPerks import load_mod_data
from Cogs.RocketLeague import RANK_EMOJIS, get_highest_rl_rank
from Cogs.TicketSystem import load_tickets
from Config import (
    ADMIN_ROLE_ID,
    CHANGELOG_ROLE_ID,
    INTEREST_ROLE_IDS,
    MEME_ROLE_ID,
    MODERATOR_ROLE_ID,
    NORMAL_ROLE_ID,
    get_guild_id,
)
from Utils.EmbedUtils import set_pink_footer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Helper to get warning count for a user
async def get_warning_count(user_id: int) -> int:
    mod_data = await load_mod_data()
    warnings_data = mod_data.get("warnings", {})
    user_warnings = warnings_data.get(str(user_id), {})
    return user_warnings.get("count", 0)


# Helper to get resolved ticket count for a user
async def get_resolved_ticket_count(user_id: int) -> int:
    tickets = await load_tickets()
    resolved_count = 0
    for ticket in tickets:
        if ticket["status"] == "Closed" and (
            ticket.get("claimed_by") == user_id
            or ticket.get("assigned_to") == user_id
            or ticket.get("closed_by") == user_id
        ):
            resolved_count += 1
    return resolved_count


# Helper to get XP/Level data for a user
def get_user_xp_data(user_id: int) -> Optional[dict]:
    """Get XP and level data for a user from the database."""
    try:
        db_path = Path(Config.DATA_DIR) / "user_levels.db"
        if not db_path.exists():
            return None

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT total_xp, current_level FROM user_xp WHERE user_id = ?", (str(user_id),))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        total_xp = row["total_xp"]
        level = row["current_level"]

        # Calculate XP needed for next level using Config function
        xp_for_next_level = Config.calculate_xp_for_next_level(level)

        # Get tier info using Config function (includes emoji)
        tier_info = Config.get_level_tier(level)

        return {
            "total_xp": total_xp,
            "level": level,
            "xp_for_next_level": xp_for_next_level,
            "tier_name": tier_info["name"],
            "tier_color": tier_info["color"],
            "tier_emoji": tier_info["emoji"],
        }
    except Exception as e:
        logger.error(f"Error fetching XP data for user {user_id}: {e}")
        return None


# Helper to load meme requests
def load_meme_requests() -> dict:
    """Load meme requests from file"""
    import json
    import os

    from Config import get_data_dir

    file_path = os.path.join(get_data_dir(), "meme_requests.json")
    try:
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading meme requests: {e}")
    return {}


# Helper to load memes generated
def load_memes_generated() -> dict:
    """Load memes generated from file"""
    import json
    import os

    from Config import get_data_dir

    file_path = os.path.join(get_data_dir(), "memes_generated.json")
    try:
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading memes generated: {e}")
    return {}


class Profile(commands.Cog):
    """
    👤 Profile Cog: Shows user profile with avatar, join date, roles, and custom stats.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def create_profile_embed(self, member: discord.Member) -> discord.Embed:
        embed = discord.Embed(title=f"👤 Profile: {member.display_name}", color=Config.PINK)
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.add_field(name="Joined At", value=member.joined_at.strftime("%B %d, %Y"), inline=True)
        embed.add_field(
            name="Account Created",
            value=member.created_at.strftime("%B %d, %Y"),
            inline=True,
        )

        # Main roles with colored mentions
        main_roles = []
        guild = member.guild
        if any(role.id == ADMIN_ROLE_ID for role in member.roles):
            admin_role = guild.get_role(ADMIN_ROLE_ID)
            main_roles.append(admin_role.mention)
        if any(role.id == MODERATOR_ROLE_ID for role in member.roles):
            mod_role = guild.get_role(MODERATOR_ROLE_ID)
            main_roles.append(mod_role.mention)
        if any(role.id == NORMAL_ROLE_ID for role in member.roles):
            normal_role = guild.get_role(NORMAL_ROLE_ID)
            main_roles.append(normal_role.mention)
        main_roles_text = ", ".join(main_roles) if main_roles else "No main roles"
        embed.add_field(name="Main Roles", value=main_roles_text, inline=False)

        # Interest roles with colored mentions
        interest_roles = [role.mention for role in member.roles if role.id in INTEREST_ROLE_IDS]
        interest_roles_text = ", ".join(interest_roles) if interest_roles else "No interest roles"
        embed.add_field(name="Interest Roles", value=interest_roles_text, inline=False)

        # Custom stats
        rl_rank = get_highest_rl_rank(member.id)
        if rl_rank:
            emoji = RANK_EMOJIS.get(rl_rank, "<:unranked:1425389712276721725>")
            rl_text = f"🏆 Highest RL Rank: {emoji} {rl_rank}"
        else:
            rl_text = "🏆 No RL account linked"

        changelog_opt_in = "✅ Yes" if any(role.id == CHANGELOG_ROLE_ID for role in member.roles) else "❌ No"
        meme_opt_in = "✅ Yes" if any(role.id == MEME_ROLE_ID for role in member.roles) else "❌ No"
        warning_count = await get_warning_count(member.id)

        custom_stats = f"{rl_text}\n⚠️ Warnings: {warning_count}"
        if any(role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in member.roles):
            resolved_tickets = await get_resolved_ticket_count(member.id)
            custom_stats += f"\n🎫 Resolved Tickets: {resolved_tickets}"

        embed.add_field(name="Custom Stats", value=custom_stats, inline=False)

        # Notifications
        notifications = f"🔔 Changelog Opt-in: {changelog_opt_in}\n🎭 Meme Opt-in: {meme_opt_in}"
        embed.add_field(name="Notifications", value=notifications, inline=True)

        # Activity stats
        activity = await get_user_activity(member.id)
        meme_requests = load_meme_requests()
        memes_generated = load_memes_generated()
        meme_request_count = meme_requests.get(str(member.id), 0)
        meme_generated_count = memes_generated.get(str(member.id), 0)
        embed.add_field(
            name="Activity",
            value=(
                f"💬 Messages: {activity['messages']}\n"
                f"🖼️ Images: {activity['images']}\n"
                f"🎭 Memes Requested: {meme_request_count}\n"
                f"🎨 Memes Generated: {meme_generated_count}"
            ),
            inline=True,
        )

        # XP & Level stats
        xp_data = get_user_xp_data(member.id)
        if xp_data:
            # Tier info already contains emoji from Config.get_level_tier
            tier_name = xp_data["tier_name"]
            tier_emoji = xp_data.get("tier_emoji", "🔰")

            embed.add_field(
                name="⭐ Level & Experience",
                value=(
                    f"**Level:** {xp_data['level']} {tier_emoji}\n"
                    f"**Tier:** {tier_name.title()}\n"
                    f"**Total XP:** {xp_data['total_xp']:,}\n"
                    f"**Next Level:** {xp_data['xp_for_next_level']:,} XP"
                ),
                inline=False,
            )

        set_pink_footer(embed, bot=self.bot.user)
        return embed

    # 🧩 Shared handler for profile logic
    async def handle_profile(self, ctx_or_interaction: Any, user: Optional[discord.Member] = None) -> None:
        if user:
            member = user
        else:
            member = ctx_or_interaction.author if hasattr(ctx_or_interaction, "author") else ctx_or_interaction.user
        embed = await self.create_profile_embed(member)
        if hasattr(ctx_or_interaction, "send"):  # Prefix command
            await ctx_or_interaction.send(embed=embed)
        else:  # Slash command
            await ctx_or_interaction.response.send_message(embed=embed, ephemeral=False)

    # !profile (Prefix)
    @commands.command(name="profile")
    async def profile_command(self, ctx: commands.Context, user: Optional[discord.Member] = None) -> None:
        """
        👤 Shows your profile or another user's profile.
        """
        logger.info(f"Profile requested for user {user.display_name if user else 'self'} by {ctx.author}")
        await self.handle_profile(ctx, user)

    # /profile (Slash)
    @app_commands.command(name="profile", description="👤 Shows your profile or another user's profile.")
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    @app_commands.describe(user="Select a user (optional, defaults to yourself)")
    async def profile_slash(self, interaction: discord.Interaction, user: Optional[discord.Member] = None) -> None:
        logger.info(f"Profile slash requested for user {user.display_name if user else 'self'} by {interaction.user}")
        await self.handle_profile(interaction, user)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Profile(bot))
