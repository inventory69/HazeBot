from discord.ext import commands
import discord
from typing import Any, List, Dict
from Config import BotName, PINK, SLASH_COMMANDS, ADMIN_COMMANDS, MOD_COMMANDS
from Utils.EmbedUtils import set_pink_footer
from Utils.Logger import log_clear, Logger
from discord import app_commands
import os
import json

ADMIN_ROLE_ID = 1424466881862959294  # Admin role ID
MODERATOR_ROLE_ID = 1427219729960931449  # Slot Keeper role ID


class DynamicButtonView(discord.ui.View):
    """
    A dynamic view that creates buttons from JSON configuration.
    Supports both link buttons and interactive buttons.
    """

    def __init__(self, buttons_config: List[Dict[str, Any]]) -> None:
        super().__init__(timeout=None)  # Persistent view
        for button_data in buttons_config:
            self._add_button(button_data)

    def _add_button(self, button_data: Dict[str, Any]) -> None:
        """
        Add a button to the view based on configuration.

        Supported fields:
        - label: Button text (required)
        - style: Button style (optional, default: "blurple")
        - url: URL for link buttons (optional)
        - emoji: Emoji for the button (optional)
        - custom_id: Custom identifier for interactive buttons (optional)
        - disabled: Whether button is disabled (optional, default: False)
        """
        label = button_data.get("label", "Button")
        url = button_data.get("url")
        emoji = button_data.get("emoji")
        disabled = button_data.get("disabled", False)

        # Parse style
        style_str = button_data.get("style", "blurple").lower()
        style_map = {
            "primary": discord.ButtonStyle.primary,
            "blurple": discord.ButtonStyle.primary,
            "secondary": discord.ButtonStyle.secondary,
            "grey": discord.ButtonStyle.secondary,
            "gray": discord.ButtonStyle.secondary,
            "success": discord.ButtonStyle.success,
            "green": discord.ButtonStyle.success,
            "danger": discord.ButtonStyle.danger,
            "red": discord.ButtonStyle.danger,
            "link": discord.ButtonStyle.link,
        }
        style = style_map.get(style_str, discord.ButtonStyle.primary)

        # If URL is provided, it's a link button
        if url:
            button = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.link,
                url=url,
                emoji=emoji,
                disabled=disabled,
            )
            self.add_item(button)
        else:
            # Interactive button
            custom_id = button_data.get("custom_id", f"button_{len(self.children)}")

            button = discord.ui.Button(
                label=label,
                style=style,
                custom_id=custom_id,
                emoji=emoji,
                disabled=disabled,
            )

            # Create callback for the button
            async def button_callback(interaction: discord.Interaction, btn=button) -> None:
                """Handle button click with a simple acknowledgment."""
                await interaction.response.send_message(
                    f"✅ You clicked the **{btn.label}** button!",
                    ephemeral=True,
                )

            button.callback = button_callback
            self.add_item(button)


class Utility(commands.Cog):
    """
    🛠️ Utility Cog: Provides standard commands like help and status.
    Modular and easy to extend!
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Shared helper functions for logic
    def create_help_embed(self, ctx_or_interaction: Any, is_admin: bool = False, is_mod: bool = False) -> discord.Embed:
        embed = discord.Embed(
            title=f"{BotName} Help",
            description="Here are all available commands:\n",
            color=PINK,
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
            chunks = []
            current_chunk = []
            current_length = 0
            max_length = 800  # Safe under 1024
            for entry in commands_list:
                if current_length + len(entry) > max_length:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = [entry]
                    current_length = len(entry)
                else:
                    current_chunk.append(entry)
                    current_length += len(entry)
            if current_chunk:
                chunks.append(current_chunk)
            for idx, chunk in enumerate(chunks):
                field_name = f"{name_prefix}" if len(chunks) == 1 else f"{name_prefix} ({idx + 1}/{len(chunks)})"
                embed.add_field(name=field_name, value="\n".join(chunk), inline=False)

        add_chunked_fields("✨ User Commands", normal_commands)
        add_chunked_fields("📦 Mod Commands", mod_commands)
        add_chunked_fields("🛡️ Admin Commands", admin_commands)

        embed.set_footer(
            text="Powered by Haze World 💖",
            icon_url=getattr(self.bot.user.avatar, "url", None),
        )
        return embed

    def create_status_embed(self, bot_user: discord.User, latency: float, guild_count: int) -> discord.Embed:
        embed = discord.Embed(
            title=f"{BotName} Status",
            description="The bot is online and fabulous! 💖",
            color=PINK,
        )
        embed.add_field(name="Latency", value=f"{round(latency * 1000)} ms")
        embed.add_field(name="Guilds", value=f"{guild_count}")
        set_pink_footer(embed, bot=bot_user)
        return embed

    def create_clear_embed(self, deleted_count: int, bot_user: discord.User) -> discord.Embed:
        embed = discord.Embed(description=f"🧹 {deleted_count} messages have been deleted.", color=PINK)
        set_pink_footer(embed, bot=bot_user)
        return embed

    def create_say_embed(self, message: str, bot_user: discord.User) -> discord.Embed:
        embed = discord.Embed(description=message, color=PINK)
        set_pink_footer(embed, bot=bot_user)
        return embed

    # !help (Prefix)
    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context) -> None:
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
                await ctx.send(
                    "❌ I couldn't send you a DM. Please check your privacy settings.",
                    delete_after=10,
                )
        else:
            await ctx.send(embed=embed)

    # /help (Slash) - Public, but shows more for admins
    @app_commands.command(
        name="help",
        description="📖 Shows all available commands with their descriptions.",
    )
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    async def help_slash(self, interaction: discord.Interaction) -> None:
        is_admin = any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)
        is_mod = any(role.id == MODERATOR_ROLE_ID for role in interaction.user.roles)
        embed = self.create_help_embed(interaction, is_admin, is_mod)
        if is_admin or is_mod:
            # Check if embed is too large (over 2000 chars total)
            embed_length = (
                len(embed.title or "")
                + len(embed.description or "")
                + sum(len(field.name) + len(field.value) for field in embed.fields)
            )
            if embed_length > 1900:  # Buffer for safety
                # Split into multiple embeds if needed (simple split by fields)
                embeds = []
                current_embed = discord.Embed(title=embed.title, description=embed.description, color=embed.color)
                for field in embed.fields:
                    if (
                        len(current_embed.fields) >= 5
                        or (
                            len(current_embed.title or "")
                            + len(current_embed.description or "")
                            + sum(len(f.name) + len(f.value) for f in current_embed.fields)
                            + len(field.name)
                            + len(field.value)
                        )
                        > 1900
                    ):
                        embeds.append(current_embed)
                        current_embed = discord.Embed(title=embed.title, description="", color=embed.color)
                    current_embed.add_field(name=field.name, value=field.value, inline=field.inline)
                if current_embed.fields:
                    embeds.append(current_embed)
                for e in embeds:
                    set_pink_footer(e, bot=interaction.client.user)
                # Send embeds via DM
                try:
                    for additional_embed in embeds:
                        await interaction.user.send(embed=additional_embed)
                    await interaction.response.send_message("📬 Help sent to your DMs!", ephemeral=True)
                except discord.Forbidden:
                    await interaction.response.send_message(
                        "❌ I couldn't send you a DM. Please check your privacy settings.",
                        ephemeral=True,
                    )
            else:
                try:
                    await interaction.user.send(embed=embed)
                    await interaction.response.send_message("📬 Help sent to your DMs!", ephemeral=True)
                except discord.Forbidden:
                    await interaction.response.send_message(
                        "❌ I couldn't send you a DM. Please check your privacy settings.",
                        ephemeral=True,
                    )
        else:
            # Check if embed is too large (over 2000 chars total)
            embed_length = (
                len(embed.title or "")
                + len(embed.description or "")
                + sum(len(field.name) + len(field.value) for field in embed.fields)
            )
            if embed_length > 1900:  # Buffer for safety
                # Split into multiple embeds if needed (simple split by fields)
                embeds = []
                current_embed = discord.Embed(title=embed.title, description=embed.description, color=embed.color)
                for field in embed.fields:
                    if (
                        len(current_embed.fields) >= 5
                        or (
                            len(current_embed.title or "")
                            + len(current_embed.description or "")
                            + sum(len(f.name) + len(f.value) for f in current_embed.fields)
                            + len(field.name)
                            + len(field.value)
                        )
                        > 1900
                    ):
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
    async def status(self, ctx: commands.Context) -> None:
        """
        💖 Shows bot status and basic info in pink.
        """
        embed = self.create_status_embed(self.bot.user, self.bot.latency, len(self.bot.guilds))
        await ctx.send(embed=embed)

    # /status (Slash)
    @app_commands.command(name="status", description="💖 Shows bot status and basic info in pink.")
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    async def status_slash(self, interaction: discord.Interaction) -> None:
        embed = self.create_status_embed(
            interaction.client.user,
            interaction.client.latency,
            len(interaction.client.guilds),
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)
        Logger.info(f"Slash command /status used by {interaction.user} in {interaction.guild}")

    # !clear (Prefix) - Only prefix, no slash
    @commands.command(name="clear")
    async def clear(self, ctx: commands.Context, amount: str = "10") -> None:
        """
        🧹 Deletes the last X messages in the channel (default: 10). Use 'all' to delete all messages.
        Only allowed for users with the Admin or Slot Keeper (Mod) role.
        """
        if not any(role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in ctx.author.roles):
            embed = discord.Embed(
                description="🚫 You do not have permission to use this command.",
                color=discord.Color.red(),
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
    async def say(self, ctx: commands.Context, *, message: str) -> None:
        """
        🗣️ Allows an admin to send a message as the bot in the current channel.
        Usage:
        - !say your message here (plain text)
        - !say --embed your message here (simple text embed)
        - !say --json {"title": "...", "description": "...", "image": {"url": "..."}} (full JSON embed)
        - !say --json {"embed": {...}, "buttons": [{"label": "...", "url": "..."}]} (embed with buttons)
        """
        if not any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles):
            embed = discord.Embed(
                description="🚫 You do not have permission to use this command.",
                color=discord.Color.red(),
            )
            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed, delete_after=5)
            return
        await ctx.message.delete()

        # JSON Embed Support (Full Control with Images and Buttons)
        if message.startswith("--json "):
            try:
                json_str = message[7:].strip()
                json_data = json.loads(json_str)

                # Check if there's a separate "embed" and "buttons" structure
                # or if the entire JSON is the embed data
                if "embed" in json_data or "buttons" in json_data:
                    # New structure: {"embed": {...}, "buttons": [...]}
                    embed_data = json_data.get("embed", {})
                    buttons_data = json_data.get("buttons", [])

                    # Create embed if provided
                    if embed_data:
                        embed = discord.Embed.from_dict(embed_data)
                    else:
                        embed = None

                    # Create view with buttons if provided
                    view = None
                    if buttons_data and isinstance(buttons_data, list):
                        view = DynamicButtonView(buttons_data)

                    # Send message with embed and/or buttons
                    if embed and view:
                        await ctx.send(embed=embed, view=view)
                    elif embed:
                        await ctx.send(embed=embed)
                    elif view:
                        await ctx.send(view=view)
                    else:
                        error_embed = discord.Embed(
                            description="❌ JSON must contain 'embed' or 'buttons'.",
                            color=discord.Color.red(),
                        )
                        await ctx.send(embed=error_embed, delete_after=10)
                        return
                else:
                    # Legacy structure: entire JSON is embed data
                    embed = discord.Embed.from_dict(json_data)
                    await ctx.send(embed=embed)

                Logger.info(f"JSON embed sent by {ctx.author} in {ctx.guild}")
            except json.JSONDecodeError as e:
                error_embed = discord.Embed(
                    description=f"❌ Invalid JSON format: {e}",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=error_embed, delete_after=10)
                Logger.error(f"JSON decode error in !say by {ctx.author}: {e}")
            except Exception as e:
                error_embed = discord.Embed(
                    description=f"❌ Error creating embed: {e}",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=error_embed, delete_after=10)
                Logger.error(f"Error creating embed in !say by {ctx.author}: {e}")
        # Simple Text Embed Support
        elif message.startswith("--embed "):
            message = message[8:].strip()
            embed = self.create_say_embed(message, self.bot.user)
            await ctx.send(embed=embed)
            Logger.info(f"Simple embed sent by {ctx.author} in {ctx.guild}")
        # Plain Text
        else:
            await ctx.send(message)
            Logger.info(f"Plain message sent by {ctx.author} in {ctx.guild}")

        Logger.info(f"Prefix command !say used by {ctx.author} in {ctx.guild}")


async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the Utility cog.
    """
    await bot.add_cog(Utility(bot))
