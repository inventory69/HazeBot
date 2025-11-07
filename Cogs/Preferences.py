import discord
from discord.ext import commands
from discord import app_commands
from typing import Any
import Config
from Config import CHANGELOG_ROLE_ID, MEME_ROLE_ID, get_guild_id
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
        logger.info(f"Prefix command !preferences used by {ctx.author} in {ctx.guild}")
        embed = self.get_preferences_help_embed(ctx, ctx.author)
        view = PreferencesView(ctx.author.id, ctx.guild)
        await ctx.send(embed=embed, view=view)

    # /preferences (Slash) - Only synced in guild
    @app_commands.command(name="preferences", description="🛠️ Open your preferences menu.")
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    async def preferences_slash(self, interaction: discord.Interaction) -> None:
        logger.info(f"Slash command /preferences used by {interaction.user} in {interaction.guild}")
        embed = self.get_preferences_help_embed(interaction, interaction.user)
        view = PreferencesView(interaction.user.id, interaction.guild)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # 🧩 Shared Helper for preferences embed (used in prefix and slash)
    def get_preferences_help_embed(self, ctx_or_interaction: Any, user: discord.User) -> discord.Embed:
        # Check Changelog role status
        has_changelog_role = any(role.id == CHANGELOG_ROLE_ID for role in user.roles)
        changelog_status = "✅ Enabled" if has_changelog_role else "❌ Disabled"

        # Check Meme role status
        has_meme_role = any(role.id == MEME_ROLE_ID for role in user.roles)
        meme_status = "✅ Enabled" if has_meme_role else "❌ Disabled"

        embed = discord.Embed(
            title="🛠️ Preferences Menu",
            description="Customize your notification preferences.",
            color=Config.PINK,
        )

        embed.add_field(
            name="🔔 Changelog Notifications",
            value=f"Status: **{changelog_status}**\nGet notified about bot updates and new features.",
            inline=False,
        )

        embed.add_field(
            name="🎭 Daily Meme Notifications",
            value=f"Status: **{meme_status}**\nGet pinged when the daily meme is posted at 12:00 PM.",
            inline=False,
        )

        set_pink_footer(embed, bot=self.bot.user if hasattr(self.bot, "user") else None)
        return embed


# === View for preferences menu ===
class PreferencesView(discord.ui.View):
    def __init__(self, user_id: int, guild: discord.Guild) -> None:
        super().__init__(timeout=300)
        member = guild.get_member(user_id)

        # Changelog button
        has_changelog = member and any(role.id == CHANGELOG_ROLE_ID for role in member.roles)
        changelog_label = "🔕 Disable Changelogs" if has_changelog else "🔔 Enable Changelogs"
        self.add_item(ToggleChangelogButton(changelog_label, user_id, guild))

        # Meme button
        has_meme = member and any(role.id == MEME_ROLE_ID for role in member.roles)
        meme_label = "🔕 Disable Daily Memes" if has_meme else "🎭 Enable Daily Memes"
        self.add_item(ToggleMemeButton(meme_label, user_id, guild))


class ToggleChangelogButton(discord.ui.Button):
    def __init__(self, label: str, user_id: int, guild: discord.Guild) -> None:
        super().__init__(label=label, style=discord.ButtonStyle.primary, row=0)
        self.user_id = user_id
        self.guild = guild

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This menu is not for you.", ephemeral=True)
            return

        member = self.guild.get_member(self.user_id)
        if not member:
            await interaction.response.send_message("❌ Member not found.", ephemeral=True)
            return

        role = self.guild.get_role(CHANGELOG_ROLE_ID)
        if not role:
            await interaction.response.send_message("❌ Changelog role not found.", ephemeral=True)
            return

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message("🔕 Changelog notifications **disabled**.", ephemeral=True)
            logger.info(f"User {interaction.user} disabled changelog notifications")
        else:
            await member.add_roles(role)
            await interaction.response.send_message("🔔 Changelog notifications **enabled**!", ephemeral=True)
            logger.info(f"User {interaction.user} enabled changelog notifications")


class ToggleMemeButton(discord.ui.Button):
    def __init__(self, label: str, user_id: int, guild: discord.Guild) -> None:
        super().__init__(label=label, style=discord.ButtonStyle.primary, row=1)
        self.user_id = user_id
        self.guild = guild

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This menu is not for you.", ephemeral=True)
            return

        member = self.guild.get_member(self.user_id)
        if not member:
            await interaction.response.send_message("❌ Member not found.", ephemeral=True)
            return

        role = self.guild.get_role(MEME_ROLE_ID)
        if not role:
            await interaction.response.send_message("❌ Daily Meme role not found.", ephemeral=True)
            return

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message("🔕 Daily Meme notifications **disabled**.", ephemeral=True)
            logger.info(f"User {interaction.user} disabled daily meme notifications")
        else:
            await member.add_roles(role)
            await interaction.response.send_message("🎭 Daily Meme notifications **enabled**!", ephemeral=True)
            logger.info(f"User {interaction.user} enabled daily meme notifications")


# === Setup function ===
async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the PreferencesSystem cog.
    """
    await bot.add_cog(PreferencesSystem(bot))
