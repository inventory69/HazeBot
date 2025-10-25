from discord.ext import commands
import discord
from typing import Any
from Config import (
    BotName,
    PINK,
    SLASH_COMMANDS,
    ADMIN_COMMANDS,
    MOD_COMMANDS,
    get_guild_id,
    ADMIN_ROLE_ID,
    MODERATOR_ROLE_ID,
)
from Utils.EmbedUtils import set_pink_footer
from Utils.Logger import log_clear, Logger
from discord import app_commands
import json


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
    @app_commands.guilds(discord.Object(id=get_guild_id()))
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
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    async def status_slash(self, interaction: discord.Interaction) -> None:
        embed = self.create_status_embed(
            interaction.client.user,
            interaction.client.latency,
            len(interaction.client.guilds),
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)
        Logger.info(f"🔧 [Utility] Slash command /status used by {interaction.user} in {interaction.guild}")

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

    # Modal for interactive embed creation
    class EmbedBuilderModal(discord.ui.Modal, title="Embed Builder"):
        banner_url = discord.ui.TextInput(
            label="Banner Image URL",
            placeholder="https://example.com/banner.png",
            required=False,
            style=discord.TextStyle.short,
        )

        embed_title = discord.ui.TextInput(
            label="Embed Title", placeholder="📦 Welcome to...", required=True, style=discord.TextStyle.short
        )

        sections = discord.ui.TextInput(
            label="Sections (JSON format)",
            placeholder='[{"emoji": "🧊", "title": "About Us", "description": "Text here"}]',
            required=True,
            style=discord.TextStyle.long,
        )

        buttons = discord.ui.TextInput(
            label="Buttons (Label|URL per line)",
            placeholder="Website|https://example.com\nDocumentation|https://docs.example.com",
            required=False,
            style=discord.TextStyle.long,
        )

        embed_color = discord.ui.TextInput(
            label="Embed Color (hex without #)",
            placeholder="4605516 or 464bac",
            required=False,
            style=discord.TextStyle.short,
        )

        async def on_submit(self, interaction: discord.Interaction):
            try:
                # Parse color
                color_value = self.embed_color.value.strip() if self.embed_color.value else "464bac"

                if not color_value:
                    color_value = "464bac"

                try:
                    color_value = color_value.lstrip("#")
                    color = int(color_value, 16)
                except (ValueError, TypeError):
                    try:
                        color = int(color_value)
                    except (ValueError, TypeError):
                        color = 0x464BAC

                # Create main embed
                embed = discord.Embed(title=self.embed_title.value, color=color)

                # Add banner image
                if self.banner_url.value and self.banner_url.value.strip():
                    embed.set_image(url=self.banner_url.value.strip())

                # Parse sections
                try:
                    sections = json.loads(self.sections.value)

                    # Add each section as a separate field
                    for section in sections:
                        emoji = section.get("emoji", "")
                        section_title = section.get("title", "")
                        desc = section.get("description", "")

                        # Add section as field with emoji in title
                        embed.add_field(name=f"{emoji} {section_title}", value=desc, inline=False)

                except json.JSONDecodeError:
                    embed.description = self.sections.value

                # Add footer
                footer_icon = interaction.client.user.avatar.url if interaction.client.user.avatar else None
                embed.set_footer(
                    text=f"Powered by {interaction.guild.name} 💖",
                    icon_url=footer_icon,
                )

                # Parse buttons into multiple rows
                view = None
                if self.buttons.value and self.buttons.value.strip():
                    view = discord.ui.View(timeout=None)
                    lines = self.buttons.value.strip().split("\n")

                    # Group buttons (max 5 per row)
                    for line in lines:
                        if "|" in line:
                            parts = line.split("|", 1)
                            label = parts[0].strip()
                            url = parts[1].strip()

                            # Auto-detect emoji
                            emoji = None
                            if "website" in label.lower() or "web" in label.lower():
                                emoji = "🌐"
                            elif "doc" in label.lower():
                                emoji = "📖"
                            elif "support" in label.lower():
                                emoji = "🛠️"
                            elif "patreon" in label.lower():
                                emoji = "💖"

                            view.add_item(
                                discord.ui.Button(
                                    label=label,
                                    url=url,
                                    style=discord.ButtonStyle.secondary,
                                    emoji=emoji,
                                )
                            )

                # Send embed with view
                await interaction.response.send_message(embed=embed, view=view)
                Logger.info(f"🔧 [Utility] Interactive embed created by {interaction.user}")

            except Exception as e:
                import traceback

                error_trace = traceback.format_exc()
                error_msg = f"❌ Error creating embed: {e}\n\n```\n{error_trace[:1500]}\n```"
                await interaction.response.send_message(error_msg, ephemeral=True)
                Logger.error(f"Error in embed builder: {e}\n{error_trace}")

    # !say (Prefix) - Only prefix, no slash
    @commands.command(name="say")
    async def say(self, ctx: commands.Context, *, message: str) -> None:
        """
        🗣️ Allows an admin to send a message as the bot in the current channel.
        Usage:
        - !say your message here (plain text)
        - !say --embed your message here (simple text embed)
        - !say --json {"embeds": [...], "components": [...]} (full JSON with embeds and buttons)
        - !say --builder (interactive embed builder modal)
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

        # Interactive Builder
        if message.strip() == "--builder":
            # Create a temporary interaction-like button to trigger modal
            view = discord.ui.View(timeout=60)
            button = discord.ui.Button(label="Open Embed Builder", style=discord.ButtonStyle.primary)

            async def button_callback(interaction: discord.Interaction):
                await interaction.response.send_modal(self.EmbedBuilderModal())

            button.callback = button_callback
            view.add_item(button)

            await ctx.send("Click the button to open the embed builder:", view=view, delete_after=60)
            return

        # JSON Embed Support (Full Control with Embeds + Components)
        if message.startswith("--json "):
            try:
                json_str = message[7:].strip()
                data = json.loads(json_str)

                # Parse embeds
                embeds = []
                if "embeds" in data:
                    for embed_data in data["embeds"]:
                        embeds.append(discord.Embed.from_dict(embed_data))
                elif "embed" in data:
                    embeds.append(discord.Embed.from_dict(data["embed"]))
                elif any(key in data for key in ["title", "description", "color", "fields"]):
                    embeds.append(discord.Embed.from_dict(data))

                # Parse components (buttons)
                view = None
                if "components" in data:
                    view = discord.ui.View(timeout=None)

                    for action_row in data["components"]:
                        if action_row.get("type") != 1:
                            continue

                        for component in action_row.get("components", []):
                            if component.get("type") != 2:
                                continue

                            # Link Button
                            if component.get("style") == 5:
                                view.add_item(
                                    discord.ui.Button(
                                        label=component.get("label", "Button"),
                                        url=component["url"],
                                        style=discord.ButtonStyle.link,
                                        emoji=component.get("emoji"),
                                    )
                                )
                            # Interactive Button
                            else:
                                custom_id = component.get("custom_id", "button")
                                label = component.get("label", "Button")
                                style_map = {
                                    1: discord.ButtonStyle.primary,
                                    2: discord.ButtonStyle.secondary,
                                    3: discord.ButtonStyle.success,
                                    4: discord.ButtonStyle.danger,
                                }
                                style = style_map.get(component.get("style", 2), discord.ButtonStyle.secondary)

                                button = discord.ui.Button(
                                    label=label, style=style, custom_id=custom_id, emoji=component.get("emoji")
                                )

                                async def button_callback(interaction: discord.Interaction, cid=custom_id):
                                    await interaction.response.send_message(f"Button '{cid}' clicked!", ephemeral=True)

                                button.callback = button_callback
                                view.add_item(button)

                # Send message
                if embeds:
                    await ctx.send(embeds=embeds, view=view)
                else:
                    await ctx.send(content=data.get("content", ""), view=view)

                Logger.info(f"🔧 [Utility] JSON message sent by {ctx.author}")

            except json.JSONDecodeError as e:
                error_embed = discord.Embed(
                    description=f"❌ Invalid JSON format: {e}",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=error_embed, delete_after=10)
                Logger.error(f"JSON decode error: {e}")
            except Exception as e:
                error_embed = discord.Embed(
                    description=f"❌ Error creating message: {e}",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=error_embed, delete_after=10)
                Logger.error(f"Error in !say: {e}")
        # Simple Text Embed
        elif message.startswith("--embed "):
            message = message[8:].strip()
            embed = self.create_say_embed(message, self.bot.user)
            await ctx.send(embed=embed)
            Logger.info(f"🔧 [Utility] Simple embed sent by {ctx.author}")
        # Plain Text
        else:
            await ctx.send(message)
            Logger.info(f"🔧 [Utility] Plain message sent by {ctx.author}")

        Logger.info(f"🔧 [Utility] Prefix command !say used by {ctx.author}")


async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the Utility cog.
    """
    await bot.add_cog(Utility(bot))
