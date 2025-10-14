from discord.ext import commands
import discord
from Config import BotName, PINK, SLASH_COMMANDS, ADMIN_COMMANDS, MOD_COMMANDS
from Utils.EmbedUtils import set_pink_footer
from Utils.Logger import log_clear, Logger
from discord import app_commands
import os

ADMIN_ROLE_ID = 1424466881862959294  # Admin role ID
MODERATOR_ROLE_ID = 1427219729960931449  # Slot Keeper role ID

class Utility(commands.Cog):
    """
    🛠️ Utility Cog: Provides standard commands like help and status.
    Modular and easy to extend!
    """

    def __init__(self, bot):
        self.bot = bot

    # Gemeinsame Helper-Funktionen für Logik
    def create_help_embed(self, ctx_or_interaction, is_admin=False, is_mod=False):
        embed = discord.Embed(
            title=f"{BotName} Help",
            description="Here are all available commands:\n",
            color=PINK
        )
        # List of commands that have slash versions
        slash_commands = SLASH_COMMANDS  # Removed "say"
        normal_commands = []
        admin_commands = []
        mod_commands = []
        for cog_name, cog in self.bot.cogs.items():
            for cmd in cog.get_commands():
                is_admin_only = cmd.name in ADMIN_COMMANDS  # Use from Config
                is_mod_only = cmd.name in MOD_COMMANDS
                if not cmd.hidden:
                    entry = f"**!{cmd.name}**\n{cmd.help or 'No description'}"
                    if cmd.name in slash_commands:
                        entry += " (Slash available)"
                    entry += "\n"  # Removed long separator to save space
                    if is_admin_only and is_admin:
                        admin_commands.append(entry)
                    elif is_mod_only and (is_admin or is_mod):
                        mod_commands.append(entry)
                    elif not is_admin_only and not is_mod_only:
                        normal_commands.append(entry)
        
        # Function to add fields in chunks to avoid 1024 char limit
        def add_chunked_fields(name_prefix, commands_list):
            if not commands_list:
                return
            chunk_size = 8  # Adjust as needed to stay under 1024 chars
            chunks = [commands_list[i:i + chunk_size] for i in range(0, len(commands_list), chunk_size)]
            for idx, chunk in enumerate(chunks):
                field_name = f"{name_prefix}" if len(chunks) == 1 else f"{name_prefix} ({idx+1}/{len(chunks)})"
                embed.add_field(name=field_name, value="\n".join(chunk), inline=False)
        
        add_chunked_fields("✨ User Commands", normal_commands)
        add_chunked_fields("📦 Mod Commands", mod_commands)
        add_chunked_fields("🛡️ Admin Commands", admin_commands)
        
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
        Admins and mods receive the help message without anyone being able to see it.
        """
        is_admin = any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles)
        is_mod = any(role.id == MODERATOR_ROLE_ID for role in ctx.author.roles)
        embed = self.create_help_embed(ctx, is_admin, is_mod)
        if is_admin or is_mod:
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
        is_mod = any(role.id == MODERATOR_ROLE_ID for role in interaction.user.roles)
        embed = self.create_help_embed(interaction, is_admin, is_mod)
        if is_admin or is_mod:
            try:
                await interaction.user.send(embed=embed)
                await interaction.response.send_message("📬 Help sent to your DMs!", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("❌ I couldn't send you a DM. Please check your privacy settings.", ephemeral=True)
        else:
            # Check if embed is too large (over 2000 chars total)
            embed_length = len(embed.title or "") + len(embed.description or "") + sum(len(field.name) + len(field.value) for field in embed.fields)
            if embed_length > 1900:  # Buffer for safety
                # Split into multiple embeds if needed (simple split by fields)
                embeds = []
                current_embed = discord.Embed(title=embed.title, description=embed.description, color=embed.color)
                for field in embed.fields:
                    if len(current_embed.fields) >= 5 or (len(current_embed.title or "") + len(current_embed.description or "") + sum(len(f.name) + len(f.value) for f in current_embed.fields) + len(field.name) + len(field.value)) > 1900:
                        embeds.append(current_embed)
                        current_embed = discord.Embed(title=embed.title, description="", color=embed.color)
                    current_embed.add_field(name=field.name, value=field.value, inline=field.inline)
                if current_embed.fields:
                    embeds.append(current_embed)
                for e in embeds:
                    set_pink_footer(e, bot=interaction.client.user)
                # Send first embed with response, then followups for the rest
                await interaction.response.send_message(embed=embeds[0], ephemeral=False)
                for additional_embed in embeds[1:]:
                    await interaction.followup.send(embed=additional_embed, ephemeral=False)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=False)

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
        Only allowed for users with the Admin or Slot Keeper (Mod) role.
        """
        if not any(role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in ctx.author.roles):
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