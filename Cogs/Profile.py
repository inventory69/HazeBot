import discord
from discord.ext import commands
from discord import app_commands
import os
from typing import Optional, Any
from Config import (
    PINK,
    ADMIN_ROLE_ID,
    MODERATOR_ROLE_ID,
    NORMAL_ROLE_ID,
    INTEREST_ROLE_IDS,
)
from Utils.EmbedUtils import set_pink_footer
from Cogs.RocketLeague import get_highest_rl_rank, RANK_EMOJIS
from Cogs.Preferences import CHANGELOG_ROLE_ID
from Cogs.ModPerks import load_mod_data
from Cogs.TicketSystem import load_tickets
from Cogs.Leaderboard import get_user_activity


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
            ticket.get("claimed_by") == user_id or ticket.get("assigned_to") == user_id
        ):
            resolved_count += 1
    return resolved_count


class Profile(commands.Cog):
    """
    👤 Profile Cog: Shows user profile with avatar, join date, roles, and custom stats.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def create_profile_embed(self, member: discord.Member) -> discord.Embed:
        embed = discord.Embed(title=f"👤 Profile: {member.display_name}", color=PINK)
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
        warning_count = await get_warning_count(member.id)

        custom_stats = f"{rl_text}\n🔔 Changelog Opt-in: {changelog_opt_in}\n⚠️ Warnings: {warning_count}"
        if any(role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in member.roles):
            resolved_tickets = await get_resolved_ticket_count(member.id)
            custom_stats += f"\n🎫 Resolved Tickets: {resolved_tickets}"

        embed.add_field(name="Custom Stats", value=custom_stats, inline=False)

        # Activity stats
        activity = await get_user_activity(member.id)
        embed.add_field(
            name="Activity",
            value=f"💬 Messages: {activity['messages']}\n🖼️ Images: {activity['images']}",
            inline=True,
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
        await self.handle_profile(ctx, user)

    # /profile (Slash)
    @app_commands.command(name="profile", description="👤 Shows your profile or another user's profile.")
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    @app_commands.describe(user="Select a user (optional, defaults to yourself)")
    async def profile_slash(self, interaction: discord.Interaction, user: Optional[discord.Member] = None) -> None:
        await self.handle_profile(interaction, user)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Profile(bot))
