import discord
from discord.ext import commands
from discord import app_commands
from typing import Any
from Config import PINK, CHANGELOG_ROLE_ID, get_guild_id
from Utils.EmbedUtils import set_pink_footer
import logging

logger = logging.getLogger(__name__)


# === Cog definition ===
class PreferencesSystem(commands.Cog):
    """
    🛠️ Preferences System Cog: Allows members to set personal preferences like changelog notifications.
    Modular and persistent with JSON.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # !preferences (Prefix)
    @commands.command(name="preferences")
    async def preferences_command(self, ctx: commands.Context) -> None:
        """
        🛠️ Open your preferences menu.
        """
        embed = self.get_preferences_help_embed(ctx, ctx.author)
        view = PreferencesView(ctx.author.id, ctx.guild)
        await ctx.send(embed=embed, view=view)

    # /preferences (Slash) - Only synced in guild
    @app_commands.command(name="preferences", description="🛠️ Open your preferences menu.")
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    async def preferences_slash(self, interaction: discord.Interaction) -> None:
        embed = self.get_preferences_help_embed(interaction, interaction.user)
        view = PreferencesView(interaction.user.id, interaction.guild)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # 🧩 Shared Helper for preferences embed (used in prefix and slash)
    def get_preferences_help_embed(self, ctx_or_interaction: Any, user: discord.User) -> discord.Embed:
        has_role = any(role.id == CHANGELOG_ROLE_ID for role in user.roles)
        status = "✅ Enabled" if has_role else "❌ Disabled"
        embed = discord.Embed(
            title="🛠️ Preferences Menu",
            description=f"Customize your experience. Changelog notifications are currently **{status}**.",
            color=PINK,
        )
        embed.add_field(
            name="Options",
            value="🔔 Toggle Changelog Notifications – Opt-in to receive role <@&1426314743278473307> for update notifications.",
            inline=False,
        )
        set_pink_footer(embed, bot=self.bot.user if hasattr(self.bot, "user") else None)
        return embed


# === View for preferences menu ===
class PreferencesView(discord.ui.View):
    def __init__(self, user_id: int, guild: discord.Guild) -> None:
        super().__init__(timeout=300)  # 5 minutes
        self.user_id = user_id
        self.guild = guild
        # Check current status
        member = guild.get_member(user_id)
        has_role = member and any(role.id == CHANGELOG_ROLE_ID for role in member.roles)
        label = "Disable Changelog Notifications" if has_role else "Enable Changelog Notifications"
        emoji = "🔕" if has_role else "🔔"
        # Add the button with dynamic label
        self.add_item(ToggleChangelogButton(label, emoji, user_id, guild))


class ToggleChangelogButton(discord.ui.Button):
    def __init__(self, label: str, emoji: str, user_id: int, guild: discord.Guild) -> None:
        super().__init__(label=label, style=discord.ButtonStyle.primary, emoji=emoji)
        self.user_id = user_id
        self.guild = guild

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu is not for you.", ephemeral=True)
            return
        member = self.guild.get_member(self.user_id)
        if not member:
            await interaction.response.send_message("Member not found.", ephemeral=True)
            return
        role = self.guild.get_role(CHANGELOG_ROLE_ID)
        if not role:
            await interaction.response.send_message("Changelog role not found.", ephemeral=True)
            return
        if role in member.roles:
            await member.remove_roles(role)
            status = "disabled"
        else:
            await member.add_roles(role)
            status = "enabled"
        await interaction.response.send_message(f"Changelog notifications {status}.", ephemeral=True)
        logger.info(f"User {interaction.user} toggled changelog role to {status}.")

        # Note: Since the message is ephemeral, we can't edit it. The status is shown in the button label and embed initially.


# === Setup function ===
async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the PreferencesSystem cog.
    """
    await bot.add_cog(PreferencesSystem(bot))
