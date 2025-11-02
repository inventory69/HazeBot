import discord
from discord.ext import commands
import json
import os
import logging

from Config import PINK
from Utils.EmbedUtils import set_pink_footer

logger = logging.getLogger(__name__)


class CogReloadView(discord.ui.View):
    """Interactive view for selecting and reloading cogs"""

    def __init__(
        self,
        cog_manager,
        ctx: commands.Context,
        available_cogs: list,
        original_message: discord.Message = None,
    ):
        super().__init__(timeout=300)  # 5 minutes timeout for multiple reloads
        self.cog_manager = cog_manager
        self.ctx = ctx
        self.original_message = original_message

        # Add dropdown with all available cogs
        options = [
            discord.SelectOption(label=cog, description=f"Reload {cog}", emoji="🔄") for cog in sorted(available_cogs)
        ]

        select = discord.ui.Select(
            placeholder="📦 Select a cog to reload...", options=options, min_values=1, max_values=1
        )
        select.callback = self.cog_selected
        self.add_item(select)

    async def cog_selected(self, interaction: discord.Interaction):
        """Handle cog selection"""
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command author can reload cogs!", ephemeral=True)
            return

        selected_cog = interaction.data["values"][0]
        success = await self.cog_manager._perform_reload(self.ctx, selected_cog, interaction)

        # Refresh the view with updated cog list after successful reload
        if success and self.original_message:
            # Get updated list of cogs
            loaded_cogs = [cog for cog in self.cog_manager.bot.cogs.keys() if cog != "CogManager"]

            # Create new view with updated list
            new_view = CogReloadView(self.cog_manager, self.ctx, loaded_cogs, self.original_message)

            # Update the original message with new view
            try:
                await self.original_message.edit(view=new_view)
            except Exception:
                pass  # Message might be deleted or we don't have permissions

    async def on_timeout(self):
        """Disable view on timeout"""
        for item in self.children:
            item.disabled = True


class CogLogsView(discord.ui.View):
    """Interactive view for selecting cog logs to view"""

    def __init__(
        self,
        cog_manager,
        ctx: commands.Context,
        available_cogs: list,
        original_message: discord.Message = None,
    ):
        super().__init__(timeout=300)  # 5 minutes timeout for multiple log views
        self.cog_manager = cog_manager
        self.ctx = ctx
        self.original_message = original_message

        # Split into pages if more than 25 cogs
        self.all_cogs = available_cogs
        self.current_page = 0
        self.cogs_per_page = 25

        self.update_select()

    def update_select(self):
        """Update select menu with current page of cogs"""
        # Remove old select if exists
        for item in self.children[:]:
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)

        # Get cogs for current page
        start = self.current_page * self.cogs_per_page
        end = start + self.cogs_per_page
        page_cogs = self.all_cogs[start:end]

        # Add dropdown with cogs
        options = [discord.SelectOption(label=cog, description=f"View logs for {cog}", emoji="📋") for cog in page_cogs]

        select = discord.ui.Select(
            placeholder="📦 Select a cog to view logs...", options=options, min_values=1, max_values=1
        )
        select.callback = self.cog_selected
        self.add_item(select)

    async def cog_selected(self, interaction: discord.Interaction):
        """Handle cog selection"""
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command author can view logs!", ephemeral=True)
            return

        selected_cog = interaction.data["values"][0]
        await self.cog_manager._show_cog_logs(self.ctx, selected_cog, interaction)

        # Refresh the view after showing logs (don't stop it)
        if self.original_message:
            try:
                # View stays the same, just keep it active
                await self.original_message.edit(view=self)
            except Exception:
                pass  # Message might be deleted or we don't have permissions

    async def on_timeout(self):
        """Disable view on timeout"""
        for item in self.children:
            item.disabled = True


class CogManager(commands.Cog):
    """Cog Manager: Load, unload, and reload cogs with persistent states"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        prod_mode = os.getenv("PROD_MODE", "false").lower() == "false"
        self.disabled_cogs_file = "TestData/disabled_cogs.json" if prod_mode else "Data/disabled_cogs.json"
        self.ensure_disabled_cogs_file()
        # Ensure CogManager is never disabled
        self.enable_cog("cogmanager")

    def ensure_disabled_cogs_file(self):
        """Ensure the disabled cogs file exists"""
        os.makedirs(os.path.dirname(self.disabled_cogs_file), exist_ok=True)
        if not os.path.exists(self.disabled_cogs_file):
            with open(self.disabled_cogs_file, "w") as f:
                json.dump([], f)

    def get_disabled_cogs(self) -> list:
        """Get list of disabled cogs"""
        try:
            with open(self.disabled_cogs_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_disabled_cogs(self, disabled_cogs: list):
        """Save list of disabled cogs"""
        with open(self.disabled_cogs_file, "w") as f:
            json.dump(disabled_cogs, f, indent=2)

    def is_cog_disabled(self, cog_name: str) -> bool:
        """Check if a cog is disabled"""
        return cog_name in self.get_disabled_cogs()

    def disable_cog(self, cog_name: str):
        """Disable a cog (add to disabled list)"""
        disabled = self.get_disabled_cogs()
        if cog_name not in disabled:
            disabled.append(cog_name)
            self.save_disabled_cogs(disabled)

    def enable_cog(self, cog_name: str):
        """Enable a cog (remove from disabled list)"""
        if cog_name.lower() == "cogmanager":
            return  # Never disable CogManager
        disabled = self.get_disabled_cogs()
        if cog_name in disabled:
            disabled.remove(cog_name)
            self.save_disabled_cogs(disabled)

    def _censor_sensitive_data(self, message: str) -> str:
        """Censor sensitive information like URLs, tokens, and passwords in log messages"""
        import re

        # Censor full URLs - replace entire URL with [REDACTED]
        # Example: https://flaresolver.example.com/solve?key=123 -> [REDACTED]
        message = re.sub(r"https?://[^\s]+", "[REDACTED]", message)

        # Censor environment variable values if they appear
        # Example: "password=secretpass123" -> "password=***"
        message = re.sub(
            r"(password|token|key|secret|auth)[\s]*[=:][\s]*[^\s,)]+", r"\1=***", message, flags=re.IGNORECASE
        )

        return message

    @commands.command(name="load")
    @commands.has_permissions(administrator=True)
    async def load_cog(self, ctx: commands.Context, cog_name: str):
        """Load a cog"""
        try:
            await self.bot.load_extension(f"Cogs.{cog_name}")
            self.enable_cog(cog_name)
            embed = discord.Embed(
                title="✅ Cog Loaded", description=f"Successfully loaded cog `{cog_name}`", color=PINK
            )
            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed)
            logger.info(f"Cog {cog_name} loaded by {ctx.author}")
        except Exception as e:
            embed = discord.Embed(
                title="❌ Load Failed", description=f"Failed to load cog `{cog_name}`: {e}", color=discord.Color.red()
            )
            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed)
            logger.error(f"Failed to load cog {cog_name}: {e}")

    @commands.command(name="unload")
    @commands.has_permissions(administrator=True)
    async def unload_cog(self, ctx: commands.Context, cog_name: str):
        """Unload a cog"""
        if cog_name.lower() == "cogmanager":
            embed = discord.Embed(
                title="❌ Cannot Unload",
                description="CogManager cannot be unloaded - it's required for cog management!",
                color=discord.Color.red(),
            )
            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed)
            return

        try:
            await self.bot.unload_extension(f"Cogs.{cog_name}")
            self.disable_cog(cog_name)
            embed = discord.Embed(
                title="✅ Cog Unloaded", description=f"Successfully unloaded cog `{cog_name}`", color=PINK
            )
            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed)
            logger.info(f"Cog {cog_name} unloaded by {ctx.author}")
        except Exception as e:
            embed = discord.Embed(
                title="❌ Unload Failed",
                description=f"Failed to unload cog `{cog_name}`: {e}",
                color=discord.Color.red(),
            )
            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed)
            logger.error(f"Failed to unload cog {cog_name}: {e}")

    @commands.command(name="reload")
    @commands.has_permissions(administrator=True)
    async def reload_cog(self, ctx: commands.Context, cog_name: str = None):
        """Reload a cog - interactive if no cog specified"""

        # If no cog specified, show interactive selector
        if cog_name is None:
            loaded_cogs = [cog for cog in self.bot.cogs.keys() if cog != "CogManager"]

            if not loaded_cogs:
                await ctx.send("❌ No cogs available to reload!")
                return

            embed = discord.Embed(
                title="🔄 Reload Cog", description="Select a cog to reload from the dropdown below:", color=PINK
            )

            # Show list of all available cogs (no limit)
            sorted_cogs = sorted(loaded_cogs)
            cog_list = "\n".join([f"• `{cog}`" for cog in sorted_cogs])

            # Discord embed field has a 1024 character limit, so split if needed
            if len(cog_list) > 1024:
                # Split into multiple fields
                chunks = []
                current_chunk = []
                current_length = 0

                for cog in sorted_cogs:
                    line = f"• `{cog}`\n"
                    if current_length + len(line) > 1024:
                        chunks.append("\n".join(current_chunk))
                        current_chunk = [f"• `{cog}`"]
                        current_length = len(line)
                    else:
                        current_chunk.append(f"• `{cog}`")
                        current_length += len(line)

                if current_chunk:
                    chunks.append("\n".join(current_chunk))

                # Add first chunk as main field
                embed.add_field(name="📋 Available Cogs", value=chunks[0], inline=False)

                # Add remaining chunks as continuation fields
                for i, chunk in enumerate(chunks[1:], 1):
                    embed.add_field(name=f"📋 Available Cogs (continued {i})", value=chunk, inline=False)
            else:
                embed.add_field(name="📋 Available Cogs", value=cog_list, inline=False)

            set_pink_footer(embed, bot=self.bot.user)

            # Send message first, then create view with message reference
            message = await ctx.send(embed=embed)

            # Create interactive view with dropdown and pass the message
            view = CogReloadView(self, ctx, loaded_cogs, message)

            # Edit message to add the view
            await message.edit(view=view)
            return

        # Direct reload if cog name provided
        await self._perform_reload(ctx, cog_name)

    async def _perform_reload(self, ctx: commands.Context, cog_name: str, interaction: discord.Interaction = None):
        """Perform the actual reload operation. Returns True on success, False on failure."""
        try:
            # Show loading message
            if interaction:
                await interaction.response.defer()

            # Find the actual extension name from the cog name
            # Cog names can differ from file names (e.g., ChangelogCog -> Changelog.py)
            extension_name = None
            for ext_name, ext in self.bot.extensions.items():
                if ext_name.startswith("Cogs."):
                    # Get the cog classes from this extension
                    for item in dir(ext):
                        obj = getattr(ext, item, None)
                        if isinstance(obj, type) and issubclass(obj, commands.Cog):
                            # Check if any cog in this extension matches the requested name
                            if obj.__name__ == cog_name:
                                extension_name = ext_name
                                break
                    if extension_name:
                        break

            # If no extension found, the cog might not be loaded
            if not extension_name:
                error_embed = discord.Embed(
                    title="❌ Cog Not Loaded",
                    description=f"**{cog_name}** is not currently loaded.",
                    color=discord.Color.red(),
                )
                error_embed.add_field(
                    name="💡 Tip",
                    value=f"Use `!load {cog_name}` to load it first, or use `!listcogs` to see loaded cogs.",
                    inline=False,
                )
                set_pink_footer(error_embed, bot=self.bot.user)

                if interaction:
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                else:
                    await ctx.send(embed=error_embed)
                return False

            await self.bot.unload_extension(extension_name)
            await self.bot.load_extension(extension_name)

            embed = discord.Embed(
                title="✅ Cog Reloaded Successfully!",
                description=f"**{cog_name}** has been reloaded and is ready to use.",
                color=discord.Color.green(),
            )
            embed.add_field(name="📦 Cog", value=f"`{cog_name}`", inline=True)
            embed.add_field(name="👤 Reloaded by", value=ctx.author.mention, inline=True)
            embed.add_field(name="⏰ Time", value=f"<t:{int(discord.utils.utcnow().timestamp())}:R>", inline=True)

            set_pink_footer(embed, bot=self.bot.user)

            if interaction:
                await interaction.followup.send(embed=embed)
            else:
                await ctx.send(embed=embed)

            logger.info(f"🔧 [CogManager] Cog {cog_name} reloaded by {ctx.author}")
            return True

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Reload Failed",
                description=f"Failed to reload **{cog_name}**",
                color=discord.Color.red(),
            )
            error_embed.add_field(name="🐛 Error", value=f"```{str(e)[:200]}```", inline=False)
            error_embed.add_field(name="💡 Tip", value="Check the console logs for more details", inline=False)

            set_pink_footer(error_embed, bot=self.bot.user)  # Fixed: was 'embed' instead of 'error_embed'

            if interaction:
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            else:
                await ctx.send(embed=error_embed)

            logger.error(f"❌ [CogManager] Failed to reload cog {cog_name}: {e}")
            return False

    @commands.command(name="listcogs")
    @commands.has_permissions(administrator=True)
    async def list_cogs(self, ctx: commands.Context):
        """List all cogs and their status"""
        try:
            disabled = self.get_disabled_cogs()
            loaded = [cog for cog in self.bot.cogs.keys()]

            embed = discord.Embed(title="🔧 Cog Status", color=PINK)

            # Loaded cogs
            loaded_text = "\n".join([f"✅ {cog}" for cog in loaded]) or "None"
            embed.add_field(name="Loaded Cogs", value=loaded_text, inline=False)

            # Disabled cogs
            disabled_text = "\n".join([f"❌ {cog}" for cog in disabled]) or "None"
            embed.add_field(name="Disabled Cogs", value=disabled_text, inline=False)

            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed)
            logger.info(f"Cog list requested by {ctx.author}")
        except Exception as e:
            await ctx.send("❌ Error retrieving cog status.")
            logger.error(f"Error in list_cogs: {e}")

    @commands.command(name="logs", aliases=["viewlogs", "coglogs"])
    @commands.has_permissions(administrator=True)
    async def view_logs(self, ctx: commands.Context, cog_name: str = None):
        """View logs for a specific cog - interactive if no cog specified"""

        # If no cog specified, show interactive selector
        if cog_name is None:
            loaded_cogs = sorted([cog for cog in self.bot.cogs.keys()])

            if not loaded_cogs:
                await ctx.send("❌ No cogs available!")
                return

            embed = discord.Embed(
                title="📋 View Cog Logs", description="Select a cog to view its recent logs:", color=PINK
            )

            # Show list of all available cogs (no limit)
            cog_list = "\n".join([f"• `{cog}`" for cog in loaded_cogs])

            # Discord embed field has a 1024 character limit, so split if needed
            if len(cog_list) > 1024:
                # Split into multiple fields
                chunks = []
                current_chunk = []
                current_length = 0

                for cog in loaded_cogs:
                    line = f"• `{cog}`\n"
                    if current_length + len(line) > 1024:
                        chunks.append("\n".join(current_chunk))
                        current_chunk = [f"• `{cog}`"]
                        current_length = len(line)
                    else:
                        current_chunk.append(f"• `{cog}`")
                        current_length += len(line)

                if current_chunk:
                    chunks.append("\n".join(current_chunk))

                # Add first chunk as main field
                embed.add_field(name="📦 Available Cogs", value=chunks[0], inline=False)

                # Add remaining chunks as continuation fields
                for i, chunk in enumerate(chunks[1:], 1):
                    embed.add_field(name=f"📦 Available Cogs (continued {i})", value=chunk, inline=False)
            else:
                embed.add_field(name="📦 Available Cogs", value=cog_list, inline=False)

            set_pink_footer(embed, bot=self.bot.user)

            # Send message first, then create view with message reference
            message = await ctx.send(embed=embed)

            # Create interactive view with dropdown and pass the message
            view = CogLogsView(self, ctx, loaded_cogs, message)

            # Edit message to add the view
            await message.edit(view=view)
            return

        # Direct log view if cog name provided
        await self._show_cog_logs(ctx, cog_name)

    async def _show_cog_logs(self, ctx: commands.Context, cog_name: str, interaction: discord.Interaction = None):
        """Show logs for a specific cog"""
        try:
            if interaction:
                await interaction.response.defer()

            # Find the actual extension name from the cog name
            # This handles cases where cog name differs from file name (e.g., ChangelogCog -> Changelog.py)
            extension_name = None
            actual_cog_name = cog_name  # Keep the display name

            for ext_name, ext in self.bot.extensions.items():
                if ext_name.startswith("Cogs."):
                    # Get the cog classes from this extension
                    for item in dir(ext):
                        obj = getattr(ext, item, None)
                        if isinstance(obj, type) and issubclass(obj, commands.Cog):
                            # Check if any cog in this extension matches the requested name
                            if obj.__name__ == cog_name:
                                extension_name = ext_name
                                # Extract the file name (e.g., "Cogs.Changelog" -> "Changelog")
                                actual_cog_name = ext_name.split(".")[-1]
                                break
                    if extension_name:
                        break

            # If no extension found, still try with the provided name
            if not actual_cog_name:
                actual_cog_name = cog_name

            # Read log file - use absolute path
            log_file = os.path.join(os.getcwd(), "Logs", "HazeBot.log")

            if not os.path.exists(log_file):
                # Try to find the log file in parent directory or common locations
                alternative_paths = [
                    "Logs/HazeBot.log",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)), "Logs", "HazeBot.log"),
                    "/home/liq/gitProjects/HazeBot/Logs/HazeBot.log",
                ]

                for alt_path in alternative_paths:
                    if os.path.exists(alt_path):
                        log_file = alt_path
                        break
                else:
                    # Still not found
                    error_embed = discord.Embed(
                        title="❌ Log File Not Found",
                        description=(
                            "The log file doesn't exist yet. The bot needs to be restarted to start logging to file."
                        ),
                        color=discord.Color.red(),
                    )
                    error_embed.add_field(name="📂 Expected Location", value=f"```{log_file}```", inline=False)
                    error_embed.add_field(
                        name="💡 Solution", value="Restart the bot to activate file logging.", inline=False
                    )
                    set_pink_footer(error_embed, bot=self.bot.user)

                    if interaction:
                        await interaction.followup.send(embed=error_embed, ephemeral=True)
                    else:
                        await ctx.send(embed=error_embed)
                    return

            # Read last 1000 lines to avoid memory issues
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                lines = lines[-1000:]  # Last 1000 lines

            # Filter logs for this cog using the actual file name (case-insensitive)
            # Look for the cog prefix pattern like "[Changelog]" or "Changelog"
            cog_filter = actual_cog_name.lower()
            filtered_logs = [line for line in lines if cog_filter in line.lower()]

            if not filtered_logs:
                embed = discord.Embed(
                    title=f"📋 Logs: {cog_name}",
                    description=f"No logs found for this cog in recent history.\n*Searching for: `{actual_cog_name}`*",
                    color=PINK,
                )
                set_pink_footer(embed, bot=self.bot.user)

                if interaction:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await ctx.send(embed=embed)
                return

            # Count log levels
            info_count = sum(1 for line in filtered_logs if " INFO " in line)
            warning_count = sum(1 for line in filtered_logs if " WARNING " in line)
            error_count = sum(1 for line in filtered_logs if " ERROR " in line)
            debug_count = sum(1 for line in filtered_logs if " DEBUG " in line)

            # Get recent logs (last 10)
            recent_logs = filtered_logs[-10:]

            # Format logs for display
            formatted_logs = []
            for log in recent_logs:
                # Extract timestamp, level, and message
                parts = log.strip().split(None, 3)
                if len(parts) >= 4:
                    # timestamp = parts[0]  # Not used
                    time = parts[1]
                    level = parts[2]
                    message = parts[3] if len(parts) > 3 else ""

                    # Censor sensitive information in logs
                    message = self._censor_sensitive_data(message)

                    # Shorten message if too long (single cutoff point)
                    max_length = 100
                    if len(message) > max_length:
                        message = message[: max_length - 3] + "..."

                    # Color code by level
                    emoji = "ℹ️"
                    if "ERROR" in level:
                        emoji = "❌"
                    elif "WARNING" in level:
                        emoji = "⚠️"
                    elif "INFO" in level:
                        emoji = "ℹ️"
                    elif "DEBUG" in level:
                        emoji = "🔍"

                    formatted_logs.append(f"{emoji} `{time}` {message}")

            # Create embed
            embed = discord.Embed(
                title=f"📋 Logs: {cog_name}",
                description=f"Showing last {len(recent_logs)} log entries from recent history",
                color=PINK,
            )

            # Add statistics
            stats = []
            if info_count > 0:
                stats.append(f"ℹ️ Info: {info_count}")
            if warning_count > 0:
                stats.append(f"⚠️ Warnings: {warning_count}")
            if error_count > 0:
                stats.append(f"❌ Errors: {error_count}")
            if debug_count > 0:
                stats.append(f"🔍 Debug: {debug_count}")

            if stats:
                embed.add_field(name="📊 Statistics", value=" • ".join(stats), inline=False)

            # Add recent logs
            if formatted_logs:
                logs_text = "\n".join(formatted_logs)
                embed.add_field(
                    name="📝 Recent Entries",
                    value=logs_text[:1024],  # Discord field limit
                    inline=False,
                )

            embed.add_field(name="💾 Total Entries", value=f"`{len(filtered_logs)}` log entries found", inline=True)

            embed.add_field(name="📁 Log File", value=f"`{log_file}`", inline=True)

            set_pink_footer(embed, bot=self.bot.user)

            if interaction:
                await interaction.followup.send(embed=embed)
            else:
                await ctx.send(embed=embed)

            logger.info(f"📋 [CogManager] Logs for {cog_name} viewed by {ctx.author}")

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Failed to Read Logs",
                description=f"Error reading logs for **{cog_name}**",
                color=discord.Color.red(),
            )
            error_embed.add_field(name="🐛 Error", value=f"```{str(e)[:200]}```", inline=False)

            if interaction:
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            else:
                await ctx.send(embed=error_embed)

            logger.error(f"❌ [CogManager] Failed to read logs for {cog_name}: {e}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        """Handle command errors"""
        if isinstance(error, commands.MissingPermissions):
            if ctx.command.name in ["load", "unload", "reload", "listcogs", "logs", "viewlogs", "coglogs"]:
                embed = discord.Embed(
                    title="❌ Permission Denied",
                    description="This command requires administrator permissions.",
                    color=discord.Color.red(),
                )
                set_pink_footer(embed, bot=self.bot.user)
                await ctx.send(embed=embed)
                return

        # Let other errors be handled by global error handler
        raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(CogManager(bot))
