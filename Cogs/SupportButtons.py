import json
import logging
import os
import shlex
from typing import Any, Dict, List

import discord
from discord.ext import commands

import Config
from Config import ADMIN_ROLE_ID, get_data_dir
from Utils.EmbedUtils import set_pink_footer

logger = logging.getLogger(__name__)

# === Path to JSON file ===
SUPPORT_BUTTONS_FILE = f"{get_data_dir()}/support_buttons.json"


# === Helper functions for JSON persistence ===
async def load_support_buttons() -> List[Dict[str, Any]]:
    os.makedirs(os.path.dirname(SUPPORT_BUTTONS_FILE), exist_ok=True)
    if not os.path.exists(SUPPORT_BUTTONS_FILE):
        with open(SUPPORT_BUTTONS_FILE, "w") as f:
            json.dump([], f)
    try:
        with open(SUPPORT_BUTTONS_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error(f"Error loading {get_data_dir()}/support_buttons.json – resetting file.")
        return []


async def save_support_button(button_data: Dict[str, Any]) -> None:
    buttons = await load_support_buttons()
    buttons.append(button_data)
    with open(SUPPORT_BUTTONS_FILE, "w") as f:
        json.dump(buttons, f, indent=2)


async def delete_support_button(message_id: int) -> None:
    buttons = await load_support_buttons()
    buttons = [b for b in buttons if b["message_id"] != message_id]
    with open(SUPPORT_BUTTONS_FILE, "w") as f:
        json.dump(buttons, f, indent=2)


# === Dynamic Button View ===
class DynamicButtonView(discord.ui.View):
    def __init__(self, button_type: str, button_data: Dict[str, Any]):
        super().__init__(timeout=None)
        self.button_type = button_type
        self.button_data = button_data

        # Add the appropriate button based on type
        if button_type == "ticket":
            self.add_item(CreateTicketButton(button_data))
        elif button_type == "slash_command":
            self.add_item(SlashCommandButton(button_data))
        elif button_type == "prefix_command":
            self.add_item(PrefixCommandButton(button_data))
        # Add more button types here as needed


class CreateTicketButton(discord.ui.Button):
    def __init__(self, button_data: Dict[str, Any]):
        super().__init__(
            label=button_data.get("text", "Create Support Ticket"),
            style=discord.ButtonStyle.primary,
            emoji=button_data.get("emoji", "🎫"),
        )
        self.button_data = button_data

    async def callback(self, interaction: discord.Interaction):
        # Import here to avoid circular imports
        from Cogs.TicketSystem import TicketView

        # Get the ticket system cog to use its help embed
        ticket_cog = interaction.client.get_cog("TicketSystem")
        if ticket_cog and hasattr(ticket_cog, "get_ticket_help_embed"):
            embed = ticket_cog.get_ticket_help_embed(interaction)
        else:
            # Fallback if ticket system is not available
            embed = discord.Embed(
                title="🎫 Create Support Ticket",
                description="Choose the type of support ticket:",
                color=Config.PINK,
            )
            set_pink_footer(embed, bot=interaction.client.user)

        # Import TicketView
        await interaction.response.send_message(embed=embed, view=TicketView(), ephemeral=True)
        logger.info(f"Support ticket creation initiated by {interaction.user} via persistent button.")


class SlashCommandButton(discord.ui.Button):
    def __init__(self, button_data: Dict[str, Any]):
        super().__init__(
            label=button_data.get("text", "Button"), style=discord.ButtonStyle.secondary, emoji=button_data.get("emoji")
        )
        self.button_data = button_data

    async def callback(self, interaction: discord.Interaction):
        command_name = self.button_data.get("command", "")
        if not command_name.startswith("/"):
            command_name = f"/{command_name}"

        embed = discord.Embed(
            title="🔧 Execute Command",
            description=f"Click the button below to execute `{command_name}`:",
            color=Config.PINK,
        )
        set_pink_footer(embed, bot=interaction.client.user)

        # Create a view with a button that executes the slash command
        view = ExecuteSlashCommandView(command_name)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"Slash command button pressed by {interaction.user} for command: {command_name}")


class PrefixCommandButton(discord.ui.Button):
    def __init__(self, button_data: Dict[str, Any]):
        super().__init__(
            label=button_data.get("text", "Button"), style=discord.ButtonStyle.secondary, emoji=button_data.get("emoji")
        )
        self.button_data = button_data

    async def callback(self, interaction: discord.Interaction):
        command_name = self.button_data.get("command", "")
        if not command_name.startswith("!"):
            command_name = f"!{command_name}"

        embed = discord.Embed(
            title="🔧 Execute Command",
            description=f"Click the button below to execute `{command_name}`:",
            color=Config.PINK,
        )
        set_pink_footer(embed, bot=interaction.client.user)

        # Create a view with a button that executes the prefix command
        view = ExecutePrefixCommandView(command_name)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"Prefix command button pressed by {interaction.user} for command: {command_name}")


class ExecuteSlashCommandView(discord.ui.View):
    def __init__(self, command_name: str):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.command_name = command_name

    @discord.ui.button(label="Execute Command", style=discord.ButtonStyle.primary, emoji="⚡")
    async def execute_command(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Try to execute the slash command
        try:
            # Remove the leading slash
            cmd_name = self.command_name.lstrip("/")

            # Get the command from the bot's tree
            command = interaction.client.tree.get_command(cmd_name)
            if command:
                # Create a mock interaction for the command
                # This is a simplified approach - in practice, you'd need to handle command options
                await interaction.response.send_message(f"Executing `/{cmd_name}`...", ephemeral=True)

                # For now, just send a message indicating the command would be executed
                # In a full implementation, you'd need to properly invoke the slash command
                await interaction.followup.send(f"✅ `/{cmd_name}` would be executed now!", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ Command `/{cmd_name}` not found.", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error executing command: {e}", ephemeral=True)


class ExecutePrefixCommandView(discord.ui.View):
    def __init__(self, command_name: str):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.command_name = command_name

    @discord.ui.button(label="Execute Command", style=discord.ButtonStyle.primary, emoji="⚡")
    async def execute_command(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Try to execute the prefix command by simulating a message
        try:
            # Remove the leading !
            cmd_name = self.command_name.lstrip("!")

            # Create a fake message in the same channel
            fake_message = await interaction.channel.send(f"!{cmd_name}")

            # Create a fake context
            ctx = await interaction.client.get_context(fake_message)

            # Try to invoke the command
            if ctx.command:
                await interaction.response.send_message(f"Executing `!{cmd_name}`...", ephemeral=True)
                await ctx.command.invoke(ctx)
                # Delete the fake message
                await fake_message.delete()
            else:
                await interaction.response.send_message(f"❌ Command `!{cmd_name}` not found.", ephemeral=True)
                await fake_message.delete()

        except Exception as e:
            await interaction.response.send_message(f"❌ Error executing command: {e}", ephemeral=True)


# === Cog definition ===
class SupportButtons(commands.Cog):
    """
    🎫 Support Buttons Cog: Allows admins to create persistent buttons for various commands.
    Buttons survive bot restarts and automatically recreate commands.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # !create-button (Prefix only, admin-only)
    @commands.command(name="create-button")
    async def create_button(self, ctx: commands.Context, *, args: str = "") -> None:
        """
        🎫 Create a persistent button in the current channel.
        Usage: !create-button --text "Button Text" --command "/ticket"
        [--emoji "🎫"] [--type slash_command]
        [--embed-title "Custom Title"] [--embed-description "Custom Description"]
        Types: ticket (default), slash_command, prefix_command
        Only admins can use this command.
        """
        # Check admin permission
        if not any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles):
            embed = discord.Embed(
                description="🚫 You do not have permission to use this command.",
                color=discord.Color.red(),
            )
            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed, delete_after=5)
            return

        # Parse arguments using shlex to handle quoted strings
        button_text = "Button"
        button_command = ""
        button_emoji = None
        button_type = "ticket"  # default
        embed_title = "🛠️ Support"
        embed_description = "Need help? Use the buttons below:"

        try:
            parts = shlex.split(args)
        except ValueError as e:
            embed = discord.Embed(
                description=f"❌ Error parsing arguments: {e}",
                color=discord.Color.red(),
            )
            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed, delete_after=10)
            return

        # Simple argument parsing
        i = 0
        while i < len(parts):
            if parts[i] == "--text" and i + 1 < len(parts):
                button_text = parts[i + 1]
                i += 2
            elif parts[i] == "--command" and i + 1 < len(parts):
                button_command = parts[i + 1]
                i += 2
            elif parts[i] == "--emoji" and i + 1 < len(parts):
                button_emoji = parts[i + 1]
                i += 2
            elif parts[i] == "--type" and i + 1 < len(parts):
                button_type = parts[i + 1]
                i += 2
            elif parts[i] == "--embed-title" and i + 1 < len(parts):
                embed_title = parts[i + 1]
                i += 2
            elif parts[i] == "--embed-description" and i + 1 < len(parts):
                embed_description = parts[i + 1]
                i += 2
            else:
                i += 1

        # Validate arguments
        if button_type not in ["ticket", "slash_command", "prefix_command"]:
            embed = discord.Embed(
                description="❌ Invalid button type. Use: ticket, slash_command, or prefix_command",
                color=discord.Color.red(),
            )
            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed, delete_after=10)
            return

        if button_type in ["slash_command", "prefix_command"] and not button_command:
            embed = discord.Embed(
                description="❌ Command is required for slash_command and prefix_command types",
                color=discord.Color.red(),
            )
            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed, delete_after=10)
            return

        # Delete the command message
        await ctx.message.delete()

        # Create embed for the button message
        embed = discord.Embed(
            title=embed_title,
            description=embed_description,
            color=Config.PINK,
        )
        set_pink_footer(embed, bot=self.bot.user)

        # Create button data
        button_data = {
            "text": button_text,
            "command": button_command,
            "emoji": button_emoji,
            "type": button_type,
            "embed_title": embed_title,
            "embed_description": embed_description,
        }

        # Send message with dynamic view
        view = DynamicButtonView(button_type, button_data)
        msg = await ctx.send(embed=embed, view=view)

        # Save button data for persistence
        persistent_data = {
            "message_id": msg.id,
            "channel_id": ctx.channel.id,
            "guild_id": ctx.guild.id,
            "created_by": ctx.author.id,
            "button_data": button_data,
            "created_at": discord.utils.utcnow().isoformat(),
        }
        await save_support_button(persistent_data)

        confirm_embed = discord.Embed(
            description=(
                f"✅ Persistent button created in {ctx.channel.mention}!\nType: {button_type}\nText: {button_text}"
            ),
            color=discord.Color.green(),
        )
        set_pink_footer(confirm_embed, bot=self.bot.user)
        await ctx.author.send(embed=confirm_embed)

        logger.info(
            f"Persistent button created by {ctx.author} in {ctx.channel} (message ID: {msg.id}, type: {button_type})."
        )

    async def _restore_support_buttons(self) -> None:
        """Restore persistent support buttons - called on ready and after reload"""
        logger.info("SupportButtons Cog ready. Restoring persistent support buttons...")
        buttons = await load_support_buttons()
        restored_count = 0

        for button_data in buttons:
            try:
                # Get the channel
                channel = self.bot.get_channel(button_data["channel_id"])
                if not channel:
                    # Try to fetch from guild if not in cache
                    guild = self.bot.get_guild(button_data["guild_id"])
                    if guild:
                        try:
                            channel = await guild.fetch_channel(button_data["channel_id"])
                        except discord.NotFound:
                            logger.warning(
                                f"Channel {button_data['channel_id']} for support button "
                                "not found. Removing from database."
                            )
                            await delete_support_button(button_data["message_id"])
                            continue
                        except discord.Forbidden:
                            logger.error(
                                f"No permission to access channel {button_data['channel_id']} for support button."
                            )
                            continue

                if channel:
                    # Try to fetch the message
                    try:
                        msg = await channel.fetch_message(button_data["message_id"])

                        button_info = button_data.get("button_data", {})
                        embed = discord.Embed(
                            title=button_info.get("embed_title", "🛠️ Support"),
                            description=button_info.get("embed_description", "Need help? Use the buttons below:"),
                            color=Config.PINK,
                        )
                        set_pink_footer(embed, bot=self.bot.user)

                        button_info = button_data.get("button_data", {})
                        button_type = button_info.get("type", "ticket")
                        view = DynamicButtonView(button_type, button_info)

                        # Update the message with fresh view
                        await msg.edit(embed=embed, view=view)
                        restored_count += 1
                        logger.info(f"Support button restored in {channel.name} (message ID: {msg.id}).")

                    except discord.NotFound:
                        logger.warning(
                            f"Support button message {button_data['message_id']} not found. Removing from database."
                        )
                        await delete_support_button(button_data["message_id"])
                    except Exception as e:
                        logger.error(f"Error restoring support button {button_data['message_id']}: {e}")

            except Exception as e:
                logger.error(f"Unexpected error restoring support button: {e}")

        logger.info(f"SupportButtons restoration complete. {restored_count} buttons restored.")

    # On ready: Restore all persistent support buttons
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self._restore_support_buttons()

    async def cog_load(self) -> None:
        """Called when the cog is loaded (including reloads)"""
        if self.bot.is_ready():
            await self._restore_support_buttons()


# === Setup function ===
async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the SupportButtons cog.
    """
    await bot.add_cog(SupportButtons(bot))
