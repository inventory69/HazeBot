from discord.ext import commands
from discord import app_commands
import discord
import os
from typing import Dict, List, Optional
from Config import PINK, MOD_COMMANDS, ADMIN_COMMANDS, SLASH_COMMANDS
from Utils.EmbedUtils import set_pink_footer

ADMIN_ROLE_ID = 1424466881862959294
MODERATOR_ROLE_ID = 1427219729960931449
NORMAL_ROLE_ID = 1424161475718807562

ROLE_DESCRIPTIONS: Dict[int, str] = {
    ADMIN_ROLE_ID: (
        "🛡️ **Admin**\n"
        "Admins manage the server, configure settings, assign roles, and resolve escalated issues. "
        "They have full access to all moderation and configuration features."
        f"\n**Role ID:** `{ADMIN_ROLE_ID}`"
        "\n**Admin Commands:**\n"
        + "\n".join(f"• !{cmd}" + (" /" + cmd if cmd in SLASH_COMMANDS else "") for cmd in ADMIN_COMMANDS)
        + "\n*Note: Slash commands (/) are only visible to you.*"
    ),
    MODERATOR_ROLE_ID: (
        "📦 **Slot Keeper (Moderator)**\n"
        "Moderators help keep the server safe and organized. They can manage messages, warn, mute, kick, ban users, "
        "manage roles (including assigning roles), and handle tickets (claim, close, support). "
        "Slot Keepers are the first contact for ticket support and community questions."
        f"\n**Role ID:** `{MODERATOR_ROLE_ID}`"
        "\n**Mod Commands:**\n"
        + "\n".join(f"• !{cmd}" + (" /" + cmd if cmd in SLASH_COMMANDS else "") for cmd in MOD_COMMANDS)
        + "\n*Note: Slash commands (/) are only visible to you.*"
    ),
    NORMAL_ROLE_ID: (
        "🎒 **Lootling**\n"
        "Members can chat, use bot features, and participate in events. If you need help, open a ticket or ask a moderator."
        f"\n**Role ID:** `{NORMAL_ROLE_ID}`"
    ),
}


class RoleInfo(commands.Cog):
    """
    📢 RoleInfo Cog: Shows info, permissions, and usage tips for any role.
    Shared helpers for prefix and slash commands!
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def create_roleinfo_embed(self, role: discord.Role) -> discord.Embed:
        perms = [perm.replace("_", " ").title() for perm, value in role.permissions if value]
        perms_text = "\n".join(f"• {p}" for p in perms) if perms else "No special permissions"
        description = ROLE_DESCRIPTIONS.get(
            role.id,
            f"**{role.name}**\nNo specific description available.\n**Role ID:** `{role.id}`",
        )
        embed = discord.Embed(
            title=f"📢 Role Info: {role.name}",
            color=role.color if role.color.value else PINK,
            description=description,
        )
        embed.add_field(name="Permissions", value=perms_text, inline=False)
        embed.add_field(
            name="Usage Tips",
            value="Ask staff if you are unsure about your permissions. Use roles to access features and channels.",
            inline=False,
        )
        set_pink_footer(embed, bot=self.bot.user)
        return embed

    def get_default_role(self, member: discord.Member) -> discord.Role:
        guild = member.guild
        if any(role.id == ADMIN_ROLE_ID for role in member.roles):
            return guild.get_role(ADMIN_ROLE_ID)
        elif any(role.id == MODERATOR_ROLE_ID for role in member.roles):
            return guild.get_role(MODERATOR_ROLE_ID)
        else:
            return guild.get_role(NORMAL_ROLE_ID)

    # !roleinfo (Prefix)
    @commands.command(name="roleinfo")
    async def roleinfo_prefix(self, ctx: commands.Context, *, role_name: Optional[str] = None) -> None:
        """
        📢 Shows info, permissions, and usage tips for a given role.
        Usage: !roleinfo [role name]
        If no role is given, shows your main group (Admin/Mod/Lootling).
        """
        role = None
        if role_name:
            role = discord.utils.find(lambda r: r.name.lower() == role_name.lower(), ctx.guild.roles)
        if not role:
            role = self.get_default_role(ctx.author)
        if not role:
            await ctx.send("❌ Role not found.")
            return
        embed = self.create_roleinfo_embed(role)
        await ctx.send(embed=embed)

    # /roleinfo (Slash) - Only show the 3 main roles
    @app_commands.command(
        name="roleinfo",
        description="📢 Shows info, permissions, and usage tips for a given role.",
    )
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    @app_commands.describe(role_id="Select a main server role")
    async def roleinfo_slash(self, interaction: discord.Interaction, role_id: Optional[str] = None) -> None:
        """
        Slash command for role info. If no role is selected, shows your main group.
        Only the 3 main roles are selectable.
        """
        guild = interaction.guild
        member = (
            interaction.user if isinstance(interaction.user, discord.Member) else guild.get_member(interaction.user.id)
        )
        allowed_role_ids = [ADMIN_ROLE_ID, MODERATOR_ROLE_ID, NORMAL_ROLE_ID]
        if role_id:
            role = guild.get_role(int(role_id))
            if not role or role.id not in allowed_role_ids:
                await interaction.response.send_message("❌ Only main roles can be selected.", ephemeral=True)
                return
        else:
            role = self.get_default_role(member)
        if not role:
            await interaction.response.send_message("❌ Role not found.", ephemeral=True)
            return
        embed = self.create_roleinfo_embed(role)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @roleinfo_slash.autocomplete("role_id")
    async def role_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice]:
        guild = interaction.guild
        roles = [
            guild.get_role(ADMIN_ROLE_ID),
            guild.get_role(MODERATOR_ROLE_ID),
            guild.get_role(NORMAL_ROLE_ID),
        ]
        return [
            app_commands.Choice(name=role.name, value=str(role.id))
            for role in roles
            if role and current.lower() in role.name.lower()
        ]


async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the RoleInfo cog.
    """
    await bot.add_cog(RoleInfo(bot))
