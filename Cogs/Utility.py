from discord.ext import commands
import discord
from Config import BotName, PINK, SLASH_COMMANDS
from Utils.EmbedUtils import set_pink_footer
from Utils.Logger import log_clear, Logger
from discord import app_commands
import os

ADMIN_ROLE_ID = 1424466881862959294  # Admin role ID

class Utility(commands.Cog):
    """
    🛠️ Utility Cog: Provides standard commands like help and status.
    Modular and easy to extend!
    """

    def __init__(self, bot):
        self.bot = bot

    # Gemeinsame Helper-Funktionen für Logik
    def create_help_embed(self, ctx_or_interaction, is_admin=False):
        embed = discord.Embed(
            title=f"{BotName} Help",
            description="Here are all available commands:\n",
            color=PINK
        )
        # List of commands that have slash versions
        slash_commands = SLASH_COMMANDS  # Removed "say"
        normal_commands = []
        admin_commands = []
        for cog_name, cog in self.bot.cogs.items():
            for cmd in cog.get_commands():
                is_admin_only = cmd.name in ["clear", "say"]  # Add more admin-only commands here
                if not cmd.hidden:
                    entry = f"**!{cmd.name}**\n{cmd.help or 'No description'}"
                    if cmd.name in slash_commands:
                        entry += " (Slash available)"
                    entry += f"\n{'─'*24}"
                    if is_admin_only and is_admin:
                        admin_commands.append(entry)
                    elif not is_admin_only:
                        normal_commands.append(entry)
        if normal_commands:
            embed.add_field(name="✨ User Commands", value="\n".join(normal_commands), inline=False)
        if admin_commands:
            embed.add_field(name="🛡️ Admin Commands", value="\n".join(admin_commands), inline=False)
        embed.set_footer(text="Powered by Haze World 💖", icon_url=getattr(self.bot.user.avatar, 'url', None))
        return embed

    def create_status_embed(self, bot_user, latency, guild_count):
        embed = discord.Embed(
            title=f"{BotName} Status",
            description="The bot is online and fabulous! 💖",
            color=PINK
        )
        embed.add_field(name="Latency", value=f"{round(latency * 1000)} ms")
        embed.add_field(name="Guilds", value=f"{guild_count}")
        set_pink_footer(embed, bot=bot_user)
        return embed

    def create_clear_embed(self, deleted_count, bot_user):
        embed = discord.Embed(
            description=f"🧹 {deleted_count} messages have been deleted.",
            color=PINK
        )
        set_pink_footer(embed, bot=bot_user)
        return embed

    def create_say_embed(self, message, bot_user):
        embed = discord.Embed(description=message, color=PINK)
        set_pink_footer(embed, bot=bot_user)
        return embed

    # !help (Prefix)
    @commands.command(name="help")
    async def help_command(self, ctx):
        """
        📖 Shows all available commands with their descriptions.
        Admins receive the help message as a DM, normal users see it in the channel.
        Only admin-only commands are shown to users with the Admin role.
        Admin commands are listed separately at the bottom for admins.
        """
        is_admin = any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles)
        embed = self.create_help_embed(ctx, is_admin)
        if is_admin:
            try:
                await ctx.author.send(embed=embed)
                await ctx.message.add_reaction("📬")
            except discord.Forbidden:
                await ctx.send("❌ I couldn't send you a DM. Please check your privacy settings.", delete_after=10)
        else:
            await ctx.send(embed=embed)

    # /help (Slash) - Öffentlich, aber zeigt mehr für Admins
    @app_commands.command(name="help", description="📖 Shows all available commands with their descriptions.")
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    async def help_slash(self, interaction: discord.Interaction):
        is_admin = any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)
        embed = self.create_help_embed(interaction, is_admin)
        await interaction.response.send_message(embed=embed, ephemeral=True if is_admin else False)

    # !status (Prefix)
    @commands.command(name="status")
    async def status(self, ctx):
        """
        💖 Shows bot status and basic info in pink.
        """
        embed = self.create_status_embed(self.bot.user, self.bot.latency, len(self.bot.guilds))
        await ctx.send(embed=embed)

    # /status (Slash)
    @app_commands.command(name="status", description="💖 Shows bot status and basic info in pink.")
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    async def status_slash(self, interaction: discord.Interaction):
        embed = self.create_status_embed(interaction.client.user, interaction.client.latency, len(interaction.client.guilds))
        await interaction.response.send_message(embed=embed, ephemeral=False)
        Logger.info(f"Slash command /status used by {interaction.user} in {interaction.guild}")

    # !clear (Prefix) - Only prefix, no slash
    @commands.command(name="clear")
    async def clear(self, ctx, amount: str = "10"):
        """
        🧹 Deletes the last X messages in the channel (default: 10). Use 'all' to delete all messages.
        Only allowed for users with the Admin role.
        """
        if not any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles):
            embed = discord.Embed(
                description="🚫 You do not have permission to use this command.",
                color=discord.Color.red()
            )
            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed, delete_after=5)
            return
        if amount.lower() == "all":
            limit = None
            deleted_count = len(await ctx.channel.purge())
        else:
            try:
                limit = int(amount) + 1
                deleted = await ctx.channel.purge(limit=limit)
                deleted_count = len(deleted) - 1
            except ValueError:
                await ctx.send("❌ Invalid amount. Use a number or 'all'.")
                return
        embed = self.create_clear_embed(deleted_count, self.bot.user)
        msg = await ctx.send(embed=embed)
        await msg.delete(delay=30)
        log_clear(ctx.channel, ctx.author, deleted_count)

    # !say (Prefix) - Only prefix, no slash
    @commands.command(name="say")
    async def say(self, ctx, *, message: str):
        """
        🗣️ Allows an admin to send a message as the bot in the current channel.
        Usage: !say --embed your message here
        If --embed is included directly after !say, the message will be sent as an embed.
        """
        if not any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles):
            embed = discord.Embed(
                description="🚫 You do not have permission to use this command.",
                color=discord.Color.red()
            )
            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed, delete_after=5)
            return
        await ctx.message.delete()
        if message.startswith("--embed "):
            message = message[8:].strip()
            embed = self.create_say_embed(message, self.bot.user)
            await ctx.send(embed=embed)
        else:
            await ctx.send(message)
        Logger.info(f"Prefix command !say used by {ctx.author} in {ctx.guild}")

async def setup(bot):
    """
    Setup function to add the Utility cog.
    """
    await bot.add_cog(Utility(bot))