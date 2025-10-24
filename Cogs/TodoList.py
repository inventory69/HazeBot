from discord.ext import commands
from discord import app_commands
import discord
import os
import json
import openai
import asyncio
from typing import Dict, List, Any, Optional
from Config import (
    PINK,
    ADMIN_ROLE_ID,
    MODERATOR_ROLE_ID,
    get_guild_id,
    get_data_dir,
    TODO_CHANNEL_ID,
)
from Utils.EmbedUtils import set_pink_footer
from Utils.Logger import Logger


# === File path for to-do list data ===
TODO_DATA_FILE = f"{get_data_dir()}/todo_list.json"

# === Todo List Channel ID ===
# TODO_CHANNEL_ID is now imported from Config.py based on PROD_MODE


# === Helper functions for data persistence ===
async def load_todo_data() -> Dict[str, Any]:
    """Load to-do list data from JSON file."""
    if not os.path.exists(TODO_DATA_FILE):
        Logger.warning(f"To-do data file not found at {TODO_DATA_FILE}. Starting fresh.")
        return {"channel_id": None, "message_id": None, "items": []}
    try:
        with open(TODO_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Migrate old items that don't have author info
        for item in data.get("items", []):
            if "author_id" not in item:
                item["author_id"] = None
                item["author_name"] = "Unknown"

        return data
    except Exception as e:
        Logger.error(f"Error loading to-do data: {e}")
        return {"channel_id": None, "message_id": None, "items": []}


def save_todo_data(data: Dict[str, Any]) -> None:
    """Save to-do list data to JSON file."""
    os.makedirs(os.path.dirname(TODO_DATA_FILE), exist_ok=True)
    try:
        with open(TODO_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        Logger.error(f"Error saving to-do data: {e}")


# === Priority emojis ===
PRIORITY_EMOJIS = {"high": "🔴", "medium": "🟡", "low": "🟢"}


# === Permission helper ===
def is_mod_or_admin(user: discord.User) -> bool:
    """Check if user is moderator or admin."""
    return any(role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in user.roles)


# === View for selecting priority before modal ===
class PrioritySelectView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        action: str = "add",
        item_index: Optional[int] = None,
        current_priority: Optional[str] = None,
        current_text: Optional[str] = None,
    ) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.action = action
        self.item_index = item_index
        self.current_priority = current_priority or "low"
        self.current_text = current_text or ""

    @discord.ui.button(label="High", style=discord.ButtonStyle.danger, emoji="🔴")
    async def select_high(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.open_modal(interaction, "high")

    @discord.ui.button(label="Medium", style=discord.ButtonStyle.secondary, emoji="🟡")
    async def select_medium(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.open_modal(interaction, "medium")

    @discord.ui.button(label="Low", style=discord.ButtonStyle.success, emoji="🟢")
    async def select_low(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.open_modal(interaction, "low")

    async def open_modal(self, interaction: discord.Interaction, priority: str) -> None:
        modal = TodoModal(
            self.bot,
            action=self.action,
            item_index=self.item_index,
            default_priority=priority,
            default_text=self.current_text,
        )
        await interaction.response.send_modal(modal)


# === View for confirming AI-formatted todo item ===
class TodoConfirmView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        formatted_task: Dict[str, str],
        priority: str,
        action: str,
        item_index: Optional[int],
        interaction: discord.Interaction,
    ) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.formatted_task = formatted_task
        self.priority = priority
        self.action = action
        self.item_index = item_index
        self.original_interaction = interaction

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Create new item with AI-formatted text and author info
        new_item = {
            "priority": self.priority,
            "title": self.formatted_task["title"],
            "description": self.formatted_task["description"],
            "author_id": interaction.user.id,
            "author_name": interaction.user.display_name,
        }

        # Load current data
        data = await load_todo_data()

        if self.action == "add":
            data["items"].append(new_item)
            Logger.info(f"To-do item added by {interaction.user}")
        elif self.action == "edit" and self.item_index is not None:
            if 0 <= self.item_index < len(data["items"]):
                data["items"][self.item_index] = new_item
                Logger.info(f"To-do item {self.item_index} edited by {interaction.user}")

        # Save data
        save_todo_data(data)

        # Update message
        modal = TodoModal(self.bot)
        await modal.update_todo_message(self.original_interaction, data)

        # Send confirmation
        await interaction.response.send_message("✅ To-do item added successfully!", ephemeral=True, delete_after=3)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message("❌ Cancelled. Item was not added.", ephemeral=True, delete_after=3)


# === Modal for adding/editing to-do items ===
class TodoModal(discord.ui.Modal, title="✏️ Update To-Do List"):
    priority = discord.ui.TextInput(
        label="Priority (already selected)",
        placeholder="Priority is pre-selected",
        required=True,
        max_length=10,
    )

    raw_text = discord.ui.TextInput(
        label="Raw Task Description",
        placeholder="Add a /todo-update command that uses AI to format todo items with emojis and nice formatting",
        required=True,
        max_length=1000,
        style=discord.TextStyle.paragraph,
    )

    def __init__(
        self,
        bot: commands.Bot,
        action: str = "add",
        item_index: Optional[int] = None,
        default_priority: str = "low",
        default_text: str = "",
    ) -> None:
        super().__init__()
        self.bot = bot
        self.action = action
        self.item_index = item_index
        self.priority.default = default_priority
        self.raw_text.default = default_text
        openai.api_key = os.getenv("OPENAI_API_KEY")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Priority is pre-selected, but validate just in case
        priority = self.priority.value.lower().strip()
        if priority not in ["high", "medium", "low"]:
            await interaction.response.send_message("❌ Invalid priority! This shouldn't happen.", ephemeral=True)
            return

        # Defer response since AI processing takes time
        await interaction.response.defer(ephemeral=True)

        try:
            # Show AI processing message (stays for 3 seconds)
            status_msg = await interaction.followup.send(
                "🤖 AI is formatting your task... Please wait.", ephemeral=True
            )

            # Use AI to format the task
            formatted_task = await self.format_task_with_ai(self.raw_text.value.strip(), priority)

            # Delete status message
            await status_msg.delete()

            # Show confirmation view with formatted task
            embed = discord.Embed(
                title="🤖 AI-Formatted Task Preview",
                description=(
                    f"**Priority:** {priority.title()}\n\n"
                    f"**Title:** {formatted_task['title']}\n\n"
                    f"**Description:** {formatted_task['description']}\n\n"
                    "Do you want to add this to the to-do list?"
                ),
                color=PINK,
            )
            set_pink_footer(embed, bot=self.bot.user)

            view = TodoConfirmView(self.bot, formatted_task, priority, self.action, self.item_index, interaction)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            Logger.error(f"Error processing to-do item: {e}")
            await interaction.followup.send(
                "❌ Failed to format task with AI. Check logs.", ephemeral=True, delete_after=5
            )

    async def format_task_with_ai(self, raw_text: str, priority: str) -> Dict[str, str]:
        """Use OpenAI to format the task with emojis and proper structure."""
        if not openai.api_key:
            raise ValueError("OpenAI API key not configured.")

        prompt = f"""
Format this to-do item for a Discord bot's to-do list. Return ONLY valid JSON with this structure:
{{
    "title": "Short catchy title with relevant emoji (max 80 chars)",
    "description": "2-3 lines explaining the task clearly"
}}

Priority level: {priority}
Raw task: {raw_text}

Rules:
- Title must start with a relevant emoji (e.g., 🎮 for gaming, 📝 for documentation, 🔧 for fixes)
- Title should be concise and action-oriented
- Description should be clear and specific (2-3 short sentences)
- Use professional but friendly tone
- NO markdown formatting in the JSON values themselves
- Return ONLY the JSON, nothing else
- Return in english
"""

        response = openai.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.7,
        )

        result = response.choices[0].message.content.strip()
        # Remove code block markers if present
        if result.startswith("```json"):
            result = result[7:]
        if result.startswith("```"):
            result = result[3:]
        if result.endswith("```"):
            result = result[:-3]

        formatted = json.loads(result.strip())
        return formatted

    async def update_todo_message(self, interaction: discord.Interaction, data: Dict[str, Any]) -> None:
        """Update or create the to-do list message in the channel."""
        embed = self.create_todo_embed(data["items"])

        # Delete old message if exists
        if data.get("message_id") and data.get("channel_id"):
            try:
                old_channel = self.bot.get_channel(data["channel_id"])
                if old_channel:
                    old_message = await old_channel.fetch_message(data["message_id"])
                    await old_message.delete()
                    Logger.info(f"Deleted old to-do message {data['message_id']}")
            except Exception as e:
                Logger.warning(f"Could not delete old to-do message: {e}")

        # Send new message silently
        new_message = await interaction.channel.send(embed=embed)

        # Update data with new message info
        data["channel_id"] = interaction.channel.id
        data["message_id"] = new_message.id
        save_todo_data(data)

        Logger.info(f"Posted new to-do message {new_message.id} in {interaction.channel}")

    def create_todo_embed(self, items: List[Dict[str, Any]]) -> discord.Embed:
        """Create a formatted to-do list embed."""
        embed = discord.Embed(title="📋 To-Do List", description="", color=PINK)

        # Group items by priority
        high_priority = [item for item in items if item["priority"] == "high"]
        medium_priority = [item for item in items if item["priority"] == "medium"]
        low_priority = [item for item in items if item["priority"] == "low"]

        # Add high priority items
        if high_priority:
            embed.description += f"\n{PRIORITY_EMOJIS['high']} **High Priority**\n"
            for i, item in enumerate(high_priority):
                embed.description += f"{item['title']}\n"
                if item.get("description"):
                    embed.description += f"{item['description']}\n"
                embed.description += f"👤 *Added by {item.get('author_name', 'Unknown')}*\n\n"

        # Add medium priority items
        if medium_priority:
            embed.description += f"\n{PRIORITY_EMOJIS['medium']} **Medium Priority**\n"
            for i, item in enumerate(medium_priority):
                embed.description += f"{item['title']}\n"
                if item.get("description"):
                    embed.description += f"{item['description']}\n"
                embed.description += f"👤 *Added by {item.get('author_name', 'Unknown')}*\n\n"

        # Add low priority items
        if low_priority:
            embed.description += f"\n{PRIORITY_EMOJIS['low']} **Low Priority**\n"
            for i, item in enumerate(low_priority):
                embed.description += f"{item['title']}\n"
                if item.get("description"):
                    embed.description += f"{item['description']}\n"
                embed.description += f"👤 *Added by {item.get('author_name', 'Unknown')}*\n\n"

        if not items:
            embed.description = "No items yet! Use `/todo-update` to add one."

        embed.description += "\n🚀 Stay tuned for updates!"
        set_pink_footer(embed, bot=self.bot.user)
        return embed


# === View for managing to-do list ===
class TodoManageView(discord.ui.View):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(label="Add Item", style=discord.ButtonStyle.green, emoji="➕")
    async def add_item(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Check if user is mod or admin
        if not is_mod_or_admin(interaction.user):
            await interaction.response.send_message("❌ You do not have permission to use this.", ephemeral=True)
            return

        # Send priority selection view
        embed = discord.Embed(
            title="Select Priority",
            description="Choose the priority level for the new to-do item:",
            color=PINK,
        )
        set_pink_footer(embed, bot=self.bot.user)
        view = PrioritySelectView(self.bot, action="add")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Edit Item", style=discord.ButtonStyle.primary, emoji="✏️")
    async def edit_item(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Check if user is mod or admin
        if not is_mod_or_admin(interaction.user):
            await interaction.response.send_message("❌ You do not have permission to use this.", ephemeral=True)
            return

        # Load data
        data = await load_todo_data()
        if not data["items"]:
            await interaction.response.send_message("❌ No items to edit!", ephemeral=True)
            return

        # Create view with select
        view = TodoEditSelectView(self.bot, data["items"])

        embed = discord.Embed(
            title="✏️ Edit To-Do Item", description="Select the item you want to edit:", color=PINK
        )
        set_pink_footer(embed, bot=self.bot.user)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Remove Item", style=discord.ButtonStyle.red, emoji="🗑️")
    async def remove_item(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Check if user is mod or admin
        if not is_mod_or_admin(interaction.user):
            await interaction.response.send_message("❌ You do not have permission to use this.", ephemeral=True)
            return

        # Load data
        data = await load_todo_data()
        if not data["items"]:
            await interaction.response.send_message("❌ No items to remove!", ephemeral=True)
            return

        # Create view with select
        view = TodoRemoveSelectView(self.bot, data["items"])

        # Check if select was created
        if not view.select:
            await interaction.response.send_message("❌ Failed to create removal options. Try again.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🗑️ Remove To-Do Item", description="Select the item you want to remove:", color=discord.Color.red()
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Clear All", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def clear_all(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Check if user is mod or admin
        if not is_mod_or_admin(interaction.user):
            await interaction.response.send_message("❌ You do not have permission to use this.", ephemeral=True)
            return

        # Defer immediately to prevent timeout
        await interaction.response.defer()

        try:
            # Load data
            data = await load_todo_data()

            # Clear all items
            data["items"] = []
            save_todo_data(data)

            # Update message
            modal = TodoModal(self.bot)
            await modal.update_todo_message(interaction, data)

            Logger.info(f"All to-do items cleared by {interaction.user}")

            # Send confirmation (stays for 3 seconds)
            confirm_msg = await interaction.followup.send("✅ All to-do items cleared!", ephemeral=True)

            # Delete confirmation after 3 seconds
            await asyncio.sleep(3)
            try:
                await confirm_msg.delete()
            except Exception:
                pass
        except Exception as e:
            Logger.error(f"Error clearing to-do items: {e}")
            await interaction.followup.send(f"❌ Error clearing items: {str(e)}", ephemeral=True, delete_after=5)


# === Select view for editing specific items ===
class TodoEditSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot, items: List[Dict[str, Any]]) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.items = items

        # Create select menu options
        options = []
        for i, item in enumerate(items):
            title = item.get("title", "Untitled")
            if len(title) > 50:
                title = title[:50] + "..."
            author = item.get("author_name", "Unknown")
            priority = item.get("priority", "low").title()
            label = f"{i + 1}. {title}"
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=str(i),
                    description=f"By {author} • Priority: {priority}"[:100],
                )
            )

        # Create and add select
        self.select = discord.ui.Select(
            placeholder="Choose item to edit...",
            options=options,
            custom_id="edit_select",
            min_values=1,
            max_values=1,  # Only one item at a time
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction) -> None:
        index = int(self.select.values[0])
        if 0 <= index < len(self.items):
            item = self.items[index]
            current_priority = item.get("priority", "low")
            # For edit, we need the raw text, but since we have formatted, use description or title
            current_text = item.get("description", item.get("title", ""))

            # Send priority selection view with current values
            embed = discord.Embed(
                title="Edit Priority",
                description=f"Editing: **{item['title']}**\n\nChoose new priority level:",
                color=PINK,
            )
            set_pink_footer(embed, bot=self.bot.user)
            view = PrioritySelectView(
                self.bot,
                action="edit",
                item_index=index,
                current_priority=current_priority,
                current_text=current_text,
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# === Select view for removing specific items ===
class TodoRemoveSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot, items: List[Dict[str, Any]]) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.items = items

        # Create select menu options
        options = []
        for i, item in enumerate(items):
            title = item.get("title", "Untitled")
            if len(title) > 50:
                title = title[:50] + "..."
            author = item.get("author_name", "Unknown")
            priority = item.get("priority", "low").title()
            desc = f"By {author} • Priority: {priority}"[:100]
            label = f"{i + 1}. {title}"
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=str(i),
                    description=desc,
                )
            )

        # Create and add select with multi-select enabled
        self.select = discord.ui.Select(
            placeholder="Choose items to remove...",
            options=options,
            custom_id="remove_select",
            min_values=1,
            max_values=min(len(options), 25),  # Allow selecting up to 25 items (Discord limit)
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction) -> None:
        # Get selected indices (sorted in reverse to remove from end first)
        indices = sorted([int(val) for val in self.select.values], reverse=True)

        # Load current data
        data = await load_todo_data()
        removed_items = []

        # Remove selected items (from end to start to avoid index issues)
        for index in indices:
            if 0 <= index < len(data["items"]):
                removed_items.append(data["items"].pop(index))

        save_todo_data(data)

        # Update message
        modal = TodoModal(self.bot)
        await interaction.response.defer()
        await modal.update_todo_message(interaction, data)

        # Log removed items
        removed_titles = ", ".join([f"'{item['title']}'" for item in reversed(removed_items)])
        Logger.info(f"Removed {len(removed_items)} to-do item(s): {removed_titles} by {interaction.user}")

        # Send confirmation
        confirm_msg = await interaction.followup.send(f"✅ Removed {len(removed_items)} item(s)!", ephemeral=True)

        # Delete confirmation after 3 seconds
        await asyncio.sleep(3)
        try:
            await confirm_msg.delete()
        except Exception:
            pass


class TodoList(commands.Cog):
    """
    📋 To-Do List Cog: Manage a dynamic server to-do list with AI-style formatting.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # 🧩 Shared handler for todo-update logic
    async def handle_todo_update(self, ctx_or_interaction: Any) -> None:
        """Shared handler for todo-update command."""
        # Check permissions
        user = ctx_or_interaction.author if hasattr(ctx_or_interaction, "author") else ctx_or_interaction.user
        if not is_mod_or_admin(user):
            message = "❌ You do not have permission to use this command."
            if hasattr(ctx_or_interaction, "send"):
                await ctx_or_interaction.send(message, delete_after=5)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
            return

        # Check if command is used in the correct channel
        channel = ctx_or_interaction.channel
        if channel.id != TODO_CHANNEL_ID:
            message = f"❌ This command can only be used in <#{TODO_CHANNEL_ID}>."
            if hasattr(ctx_or_interaction, "send"):
                await ctx_or_interaction.send(message, delete_after=5)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
            return

        # Show management view
        data = await load_todo_data()
        embed = discord.Embed(
            title="📋 To-Do List Management",
            description="Use the buttons below to manage the server's to-do list.\n\n"
            "**Current Items:** " + str(len(data["items"])),
            color=PINK,
        )
        set_pink_footer(embed, bot=self.bot.user)

        view = TodoManageView(self.bot)
        if hasattr(ctx_or_interaction, "send"):
            await ctx_or_interaction.send(embed=embed, view=view)
        else:
            await ctx_or_interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        Logger.info(f"todo-update used by {user} in {ctx_or_interaction.guild}")

    # 🧩 Shared handler for todo-show logic
    async def handle_todo_show(self, ctx_or_interaction: Any) -> None:
        """Shared handler for todo-show command."""
        data = await load_todo_data()

        if not data["items"]:
            message = "📋 The to-do list is currently empty!"
            if hasattr(ctx_or_interaction, "send"):
                await ctx_or_interaction.send(message)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
            return

        modal = TodoModal(self.bot)
        embed = modal.create_todo_embed(data["items"])
        if hasattr(ctx_or_interaction, "send"):
            await ctx_or_interaction.send(embed=embed)
        else:
            await ctx_or_interaction.response.send_message(embed=embed, ephemeral=False)

        user = ctx_or_interaction.author if hasattr(ctx_or_interaction, "author") else ctx_or_interaction.user
        Logger.info(f"todo-update used by {user} in {ctx_or_interaction.guild}")

    # !todo-update (Prefix) - Mod/Admin only
    @commands.command(name="todo-update")
    async def todo_update_prefix(self, ctx: commands.Context) -> None:
        """
        📋 Update the server's to-do list with interactive buttons. (Mod/Admin only)
        """
        await self.handle_todo_update(ctx)

    # /todo-update (Slash) - Mod/Admin only
    @app_commands.command(name="todo-update", description="📋 Update the server's to-do list with interactive buttons.")
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    async def todo_update_slash(self, interaction: discord.Interaction) -> None:
        await self.handle_todo_update(interaction)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TodoList(bot))
