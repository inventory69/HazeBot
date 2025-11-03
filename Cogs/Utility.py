from discord.ext import commands
import discord
from typing import Any
from Config import (
    BotName,
    PINK,
    SLASH_COMMANDS,
    ADMIN_COMMANDS,
    MOD_COMMANDS,
    ROLE_NAMES,
    get_guild_id,
    ADMIN_ROLE_ID,
    MODERATOR_ROLE_ID,
)
from Utils.EmbedUtils import set_pink_footer
from Utils.Logger import log_clear
from discord import app_commands
import json
import logging

logger = logging.getLogger(__name__)


class Utility(commands.Cog):
    """
    🛠️ Utility Cog: Provides standard commands like help and status.
    Modular and easy to extend!
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Shared helper functions for logic
    def create_help_embed(self, ctx_or_interaction: Any, is_admin: bool = False, is_mod: bool = False) -> discord.Embed:
        # Determine user's role display name
        if is_admin:
            role_display = ROLE_NAMES["admin"]
        elif is_mod:
            role_display = ROLE_NAMES["mod"]
        else:
            role_display = ROLE_NAMES["user"]

        embed = discord.Embed(
            title=f"📚 {BotName} Help",
            description=(
                f"**Your Role:** {role_display}\n\n"
                "Complete command reference organized by feature.\n"
                "**Legend:** `!command` = Prefix only • `!cmd` / `/cmd` = Both available\n"
                "`<parameter>` = Required • Use buttons for interactive features!"
            ),
            color=PINK,
        )

        # Command descriptions mapping (centralized)
        command_descriptions = {
            "help": "📖 Show this help message",
            "status": "📊 Bot status and latency",
            "profile": "👤 View user profile",
            "preferences": "⚙️ Toggle settings (changelog/daily meme notifications)",
            "roleinfo": "📋 View role information",
            "leaderboard": "🏆 View server leaderboards",
            "ticket": "🎫 Create a support ticket",
            "meme": "🎭 Interactive Meme Hub - Get memes, manage sources [source]",
            "rlstats": "🚀 View Rocket League stats <username>",
            "setrlaccount": "🔗 Link Rocket League account <username>",
            "unlinkrlaccount": "🔓 Unlink your Rocket League account",
            "rocket": "🚀 Rocket League Hub - Stats, rankings, profile",
            "warframe": "🎮 Warframe Hub - Market & Status (Beta)",
            "warframemarket": "💰 Search Warframe market <item> (Beta)",
            "warframestatus": "📊 View Warframe world status",
            "warframeprofile": "👤 View Warframe player profile <username>",
            "warframeinvasions": "⚔️ View current Warframe invasions",
            "warframesortie": "🎯 View daily Warframe sortie",
            "clear": "🧹 Delete messages in bulk <amount>",
            "mod": "🛡️ Moderation actions",
            "modpanel": "🎛️ Interactive moderation control panel",
            "modoverview": "📊 Moderation statistics",
            "moddetails": "🔍 User moderation history <@user>",
            "optins": "📈 Changelog opt-in statistics",
            "todo-update": "✅ Update to-do list",
            "adminrlstats": "🚀 Admin RL stats (bypass cache) <username>",
            "changelog": "📝 Generate and post changelogs",
            "update_changelog_view": "🔄 Update the changelog view message",
            "say": "💬 Send message as bot <message>",
            "testmeme": "🎭 Test daily meme function (force fetch)",
            "memesubreddits": "📋 List current meme subreddits",
            "addsubreddit": "➕ Add a subreddit <name>",
            "removesubreddit": "➖ Remove a subreddit <name>",
            "resetsubreddits": "🔄 Reset subreddits to defaults",
            "lemmycommunities": "📋 List current Lemmy communities",
            "addlemmy": "➕ Add Lemmy community <instance@community>",
            "removelemmy": "➖ Remove Lemmy community <instance@community>",
            "resetlemmy": "🔄 Reset Lemmy communities to defaults",
            "memesources": "🌐 List enabled/disabled meme sources",
            "enablesource": "✅ Enable a meme source <reddit|lemmy>",
            "disablesource": "❌ Disable a meme source <reddit|lemmy>",
            "resetsources": "🔄 Reset meme sources to defaults",
            "dailyconfig": "⚙️ Configure daily meme posting",
            "restorecongratsview": "🔄 Restore congrats button",
            "create-button": "🔘 Create persistent buttons --text <text> --command <cmd>",
            "server-guide": "🌟 Send interactive server guide",
            "load": "📦 Load a cog (interactive if no name provided)",
            "unload": "📤 Unload a cog (interactive if no name provided)",
            "reload": "🔄 Reload a cog (interactive if no name provided)",
            "listcogs": "📋 List all cogs and their status",
            "logs": "📋 View cog-specific logs with statistics",
            "viewlogs": "📋 View cog-specific logs (alias for logs)",
            "coglogs": "📋 View cog-specific logs (alias for logs)",
            "sync": "🔄 Sync all slash commands to the guild",
            "refreshtemplates": "🎨 Refresh meme templates from Imgflip API",
            "creatememe": "🎨 Create a custom meme using popular templates",
            "togglediscordlogs": "📡 Toggle Discord logging",
            "testdiscordlog": "🧪 Test Discord logging",
        }

        # Build command lists from Config.py
        # User commands = SLASH_COMMANDS that are NOT in MOD_COMMANDS or ADMIN_COMMANDS

        restricted_commands = set(MOD_COMMANDS + ADMIN_COMMANDS)
        user_command_names = [cmd for cmd in SLASH_COMMANDS if cmd not in restricted_commands]

        # Build tuples: (name, description, has_slash)
        user_commands_info = [
            (cmd, command_descriptions.get(cmd, "No description"), cmd in SLASH_COMMANDS) for cmd in user_command_names
        ]

        mod_commands_info = [
            (cmd, command_descriptions.get(cmd, "No description"), cmd in SLASH_COMMANDS) for cmd in MOD_COMMANDS
        ]

        admin_commands_info = [
            (cmd, command_descriptions.get(cmd, "No description"), cmd in SLASH_COMMANDS)
            for cmd in ADMIN_COMMANDS
            if cmd not in MOD_COMMANDS  # Don't duplicate commands that are already in MOD_COMMANDS
        ]

        def format_command_list(commands_info):
            """Format commands with parameters in a compact, readable way"""
            formatted = []
            for cmd_name, description, has_prefix in commands_info:
                # Split description into emoji + text and parameters if present
                parts = description.split("<", 1)
                desc_main = parts[0].strip()
                params = f"<{parts[1]}" if len(parts) > 1 else ""

                # Format command name
                if has_prefix:
                    cmd_format = f"`!{cmd_name}` / `/{cmd_name}`"
                else:
                    cmd_format = f"`!{cmd_name}`"

                # Build entry
                if params:
                    entry = f"{cmd_format} {params}\n└─ {desc_main}"
                else:
                    entry = f"{cmd_format}\n└─ {desc_main}"

                formatted.append(entry)
            return formatted

        # Format commands (these are used in grouping functions, not directly)
        admin_commands = format_command_list(admin_commands_info) if is_admin else []

        # Group user commands by category for better readability
        def group_commands_by_category(commands_info):
            """Group commands by feature/category"""
            categories = {
                "🔧 General": ["help", "status", "profile", "preferences", "roleinfo", "leaderboard"],
                "🎭 Memes": ["meme", "creatememe"],
                "🎫 Support": ["ticket"],
                "🚀 Rocket League": ["rlstats", "setrlaccount", "unlinkrlaccount", "rocket"],
                "🎮 Warframe": [
                    "warframe",
                    "warframemarket",
                    "warframestatus",
                    "warframeprofile",
                    "warframeinvasions",
                    "warframesortie",
                ],
            }

            grouped = {}
            for category, cmd_list in categories.items():
                grouped[category] = []
                for cmd_name, description, has_prefix in commands_info:
                    if cmd_name in cmd_list:
                        grouped[category].append((cmd_name, description, has_prefix))

            return grouped

        def group_mod_commands(commands_info):
            """Group mod commands by feature"""
            categories = {
                "🎭 Meme Management": [
                    "testmeme",
                    "memesubreddits",
                    "addsubreddit",
                    "removesubreddit",
                    "resetsubreddits",
                    "lemmycommunities",
                    "addlemmy",
                    "removelemmy",
                    "resetlemmy",
                    "memesources",
                    "enablesource",
                    "disablesource",
                    "resetsources",
                ],
                "🛡️ Moderation": ["mod", "modpanel", "modoverview", "moddetails", "clear"],
                "🔧 Utilities": ["optins", "todo-update", "restorecongratsview", "create-button", "server-guide"],
            }

            grouped = {}
            for category, cmd_list in categories.items():
                grouped[category] = []
                for cmd_name, description, has_prefix in commands_info:
                    if cmd_name in cmd_list:
                        grouped[category].append((cmd_name, description, has_prefix))

            return grouped

        user_commands_grouped = group_commands_by_category(user_commands_info)
        mod_commands_grouped = group_mod_commands(mod_commands_info) if (is_admin or is_mod) else {}

        # Function to add fields in chunks to avoid 1024 char limit
        def add_chunked_fields(name_prefix, commands_list, add_separator=False):
            if not commands_list:
                return

            # Add separator as standalone field before the category
            if add_separator:
                embed.add_field(name="\u200b", value="━━━━━━━━━━━━━━━━━━━━", inline=False)

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
                    current_length += len(entry) + 1  # +1 for newline
            if current_chunk:
                chunks.append(current_chunk)
            for idx, chunk in enumerate(chunks):
                field_name = f"{name_prefix}" if len(chunks) == 1 else f"{name_prefix} ({idx + 1}/{len(chunks)})"
                embed.add_field(name=field_name, value="\n".join(chunk), inline=False)

        # Add user commands by category
        # Add user role header
        embed.add_field(
            name=f"═══ {ROLE_NAMES['user']} Commands ═══",
            value="These commands are available to all server members.",
            inline=False,
        )

        for category, category_commands in user_commands_grouped.items():
            if category_commands:
                formatted_cmds = format_command_list(category_commands)
                add_chunked_fields(category, formatted_cmds, add_separator=False)

        # Add separator before mod commands
        if mod_commands_grouped:
            embed.add_field(name="\u200b", value="━━━━━━━━━━━━━━━━━━━━", inline=False)
            # Add mod role header
            embed.add_field(
                name=f"═══ {ROLE_NAMES['mod']} Commands ═══",
                value="These commands require Slot Keeper permissions or higher.",
                inline=False,
            )

        # Add mod commands by category
        for category, category_commands in mod_commands_grouped.items():
            if category_commands:
                formatted_cmds = format_command_list(category_commands)
                add_chunked_fields(category, formatted_cmds, add_separator=False)

        # Add admin commands
        if admin_commands:
            embed.add_field(name="\u200b", value="━━━━━━━━━━━━━━━━━━━━", inline=False)
            # Add admin role header
            embed.add_field(
                name=f"═══ {ROLE_NAMES['admin']} Commands ═══",
                value="These commands require Inventory Master permissions.",
                inline=False,
            )
            add_chunked_fields("🛡️ Admin Commands", admin_commands, add_separator=False)

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
        logger.info(f"Prefix command !help used by {ctx.author} in {ctx.guild}")
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
        description="📖 Get help with available commands",
    )
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    async def help_slash(self, interaction: discord.Interaction) -> None:
        logger.info(f"Slash command /help used by {interaction.user} in {interaction.guild}")
        is_admin = any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)
        is_mod = any(role.id == MODERATOR_ROLE_ID for role in interaction.user.roles)
        embed = self.create_help_embed(interaction, is_admin, is_mod)
        set_pink_footer(embed, bot=interaction.client.user)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # !status (Prefix)
    @commands.command(name="status")
    async def status(self, ctx: commands.Context) -> None:
        """
        💖 Shows bot status and basic info in pink.
        """
        logger.info(f"Prefix command !status used by {ctx.author} in {ctx.guild}")
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
        logger.info(f"Slash command /status used by {interaction.user} in {interaction.guild}")

    # !clear (Prefix) - Only prefix, no slash
    @commands.command(name="clear")
    async def clear(self, ctx: commands.Context, amount: str = "10") -> None:
        """
        🧹 Deletes the last X messages in the channel (default: 10). Use 'all' to delete all messages.
        Only allowed for users with the Admin or Slot Keeper (Mod) role.
        """
        logger.info(f"Clear command used by {ctx.author} to delete {amount} messages")
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
                logger.info(f"Interactive embed created by {interaction.user}")

            except Exception as e:
                import traceback

                error_trace = traceback.format_exc()
                error_msg = f"❌ Error creating embed: {e}\n\n```\n{error_trace[:1500]}\n```"
                await interaction.response.send_message(error_msg, ephemeral=True)
                logger.error(f"Error in embed builder: {e}\n{error_trace}")

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

                logger.info(f"JSON message sent by {ctx.author}")

            except json.JSONDecodeError as e:
                error_embed = discord.Embed(
                    description=f"❌ Invalid JSON format: {e}",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=error_embed, delete_after=10)
                logger.error(f"JSON decode error: {e}")
            except Exception as e:
                error_embed = discord.Embed(
                    description=f"❌ Error creating message: {e}",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=error_embed, delete_after=10)
                logger.error(f"Error in !say: {e}")
        # Simple Text Embed
        elif message.startswith("--embed "):
            message = message[8:].strip()
            embed = self.create_say_embed(message, self.bot.user)
            await ctx.send(embed=embed)
            logger.info(f"Simple embed sent by {ctx.author}")
        # Plain Text
        else:
            await ctx.send(message)
            logger.info(f"Plain message sent by {ctx.author}")

        logger.info(f"Prefix command !say used by {ctx.author}")

    @commands.command(name="sync")
    @commands.has_permissions(administrator=True)
    async def sync_commands(self, ctx: commands.Context):
        """
        🔄 Sync all slash commands to the guild (Admin only)
        Usage: !sync
        """
        await ctx.send("🔄 Syncing slash commands...")

        try:
            guild = discord.Object(id=get_guild_id())
            synced = await self.bot.tree.sync(guild=guild)
            await ctx.send(f"✅ Successfully synced {len(synced)} slash commands!")
            logger.info(f"Slash commands synced by {ctx.author}: {[cmd.name for cmd in synced]}")
        except Exception as e:
            await ctx.send(f"❌ Failed to sync commands: {e}")
            logger.error(f"Failed to sync slash commands: {e}")


async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the Utility cog.
    """
    await bot.add_cog(Utility(bot))
