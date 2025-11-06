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
)
from Utils.EmbedUtils import set_pink_footer
import logging

logger = logging.getLogger(__name__)


# === File path for to-do list data ===
TODO_DATA_FILE = f"{get_data_dir()}/todo_list.json"
TODO_PERSISTENT_VIEWS_FILE = f"{get_data_dir()}/todo_persistent_views.json"

# === Todo List Channel ID ===
# TODO_CHANNEL_ID is now imported from Config.py based on PROD_MODE


# === Helper functions for data persistence ===
async def load_todo_data() -> Dict[str, Any]:
    """Load to-do list data from JSON file."""
    if not os.path.exists(TODO_DATA_FILE):
        logger.warning(f"To-do data file not found at {TODO_DATA_FILE}. Starting fresh.")
        return {"channels": {}}
    try:
        with open(TODO_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Migrate old single-channel format to multi-channel format
        if "channel_id" in data or "items" in data:
            logger.info("Migrating old single-channel format to multi-channel format")
            old_channel_id = data.get("channel_id")
            old_items = data.get("items", [])
            old_message_ids = data.get("message_ids", [])

            # Create new format
            new_data = {"channels": {}}

            # If there was an old channel, migrate it
            if old_channel_id:
                new_data["channels"][str(old_channel_id)] = {"message_ids": old_message_ids, "items": old_items}

            # Save migrated data
            save_todo_data(new_data)
            data = new_data

        # Ensure channels dict exists
        if "channels" not in data:
            data["channels"] = {}

        # Migrate old items that don't have author info
        for channel_id, channel_data in data["channels"].items():
            for item in channel_data.get("items", []):
                if "author_id" not in item:
                    item["author_id"] = None
                    item["author_name"] = "Unknown"

        # Migrate to page-based format
        for channel_id, channel_data in data["channels"].items():
            # If channel has old "items" array instead of "pages"
            if "items" in channel_data and "pages" not in channel_data:
                logger.info(f"Migrating channel {channel_id} to page-based format")
                old_items = channel_data.get("items", [])
                channel_data["pages"] = [{"title": "📋 To-Do List", "items": old_items}]
                channel_data["current_page"] = 0
                del channel_data["items"]

            # Ensure pages structure exists
            if "pages" not in channel_data:
                channel_data["pages"] = [{"title": "📋 To-Do List", "items": []}]

            # Ensure current_page exists
            if "current_page" not in channel_data:
                channel_data["current_page"] = 0

            # Validate current_page is within bounds
            if channel_data["current_page"] >= len(channel_data["pages"]):
                channel_data["current_page"] = 0

        return data
    except Exception as e:
        logger.error(f"Error loading to-do data: {e}")
        return {"channels": {}}


def save_todo_data(data: Dict[str, Any]) -> None:
    """Save to-do list data to JSON file."""
    os.makedirs(os.path.dirname(TODO_DATA_FILE), exist_ok=True)
    try:
        with open(TODO_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving to-do data: {e}")


async def get_channel_data(data: Dict[str, Any], channel_id: int) -> Dict[str, Any]:
    """Get data for a specific channel, creating if doesn't exist."""
    channel_key = str(channel_id)
    if channel_key not in data["channels"]:
        data["channels"][channel_key] = {
            "message_ids": [],
            "current_page": 0,
            "pages": [{"title": "📋 To-Do List", "items": []}],
        }
    return data["channels"][channel_key]


# === Priority emojis ===
PRIORITY_EMOJIS = {"high": "🔴", "medium": "🟡", "low": "🟢"}


# === Permission helper ===
def is_mod_or_admin(user) -> bool:
    """Check if user is moderator or admin."""
    # Handle both discord.Member and discord.User
    if not hasattr(user, "roles"):
        return False
    return any(role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in user.roles)


# === Navigation View for page switching ===
class TodoPageNavigationView(discord.ui.View):
    def __init__(self, bot: commands.Bot, channel_id: int) -> None:
        super().__init__(timeout=None)  # Persistent view
        self.bot = bot
        self.channel_id = channel_id
        self.message = None  # Will be set after sending

        # Cooldown tracking: {user_id: datetime of last use}
        self.navigation_cooldowns = {}

    def check_navigation_cooldown(self, user_id: int) -> tuple[bool, int]:
        """
        Check if user is on cooldown for navigation buttons (1 minute).
        Returns (can_use, cooldown_remaining_seconds).
        """
        import datetime

        if user_id not in self.navigation_cooldowns:
            return True, 0

        now = datetime.datetime.now(datetime.timezone.utc)
        last_used = self.navigation_cooldowns[user_id]
        cooldown_seconds = 60  # 1 minute cooldown

        time_since_last_use = (now - last_used).total_seconds()

        if time_since_last_use < cooldown_seconds:
            remaining = int(cooldown_seconds - time_since_last_use)
            return False, remaining

        return True, 0

    def update_navigation_cooldown(self, user_id: int) -> None:
        """Update cooldown tracking for a user."""
        import datetime

        self.navigation_cooldowns[user_id] = datetime.datetime.now(datetime.timezone.utc)

    async def update_buttons(self) -> None:
        """Update button states based on current page."""
        data = await load_todo_data()
        channel_data = await get_channel_data(data, self.channel_id)
        current_page = channel_data.get("current_page", 0)
        total_pages = len(channel_data.get("pages", []))

        # Update Previous button
        self.previous_button.disabled = current_page <= 0

        # Update Next button
        self.next_button.disabled = current_page >= total_pages - 1

        # Update page info label
        self.page_info.label = f"Page {current_page + 1}/{total_pages}"

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, custom_id="todo_nav_previous")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Check cooldown for non-mods/admins
        if not is_mod_or_admin(interaction.user):
            can_use, remaining = self.check_navigation_cooldown(interaction.user.id)
            if not can_use:
                minutes = remaining // 60
                seconds = remaining % 60
                time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
                await interaction.response.send_message(
                    f"⏳ Please wait {time_str} before navigating again.",
                    ephemeral=True,
                )
                return

        await interaction.response.defer()

        # Load data and update page
        data = await load_todo_data()
        channel_data = await get_channel_data(data, self.channel_id)
        current_page = channel_data.get("current_page", 0)

        if current_page > 0:
            channel_data["current_page"] = current_page - 1
            save_todo_data(data)

            # Update cooldown for non-mods/admins
            if not is_mod_or_admin(interaction.user):
                self.update_navigation_cooldown(interaction.user.id)

            # Update the message
            await self.refresh_display(interaction, data, channel_data)

    @discord.ui.button(label="📄 Page", style=discord.ButtonStyle.primary, custom_id="todo_nav_info", disabled=True)
    async def page_info(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # This button is just for display, not clickable
        pass

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, custom_id="todo_nav_next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Check cooldown for non-mods/admins
        if not is_mod_or_admin(interaction.user):
            can_use, remaining = self.check_navigation_cooldown(interaction.user.id)
            if not can_use:
                minutes = remaining // 60
                seconds = remaining % 60
                time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
                await interaction.response.send_message(
                    f"⏳ Please wait {time_str} before navigating again.",
                    ephemeral=True,
                )
                return

        await interaction.response.defer()

        # Load data and update page
        data = await load_todo_data()
        channel_data = await get_channel_data(data, self.channel_id)
        current_page = channel_data.get("current_page", 0)
        total_pages = len(channel_data.get("pages", []))

        if current_page < total_pages - 1:
            channel_data["current_page"] = current_page + 1
            save_todo_data(data)

            # Update cooldown for non-mods/admins
            if not is_mod_or_admin(interaction.user):
                self.update_navigation_cooldown(interaction.user.id)

            # Update the message
            await self.refresh_display(interaction, data, channel_data)

    @discord.ui.button(
        label="Update", style=discord.ButtonStyle.success, custom_id="todo_nav_update", emoji="🔄", row=1
    )
    async def update_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Check if user is mod or admin
        if not is_mod_or_admin(interaction.user):
            await interaction.response.send_message(
                "❌ You do not have permission to update the todo list.",
                ephemeral=True,
            )
            return

        # Get the cog instance to call handle_todo_update
        cog = self.bot.get_cog("TodoList")
        if cog:
            await cog.handle_todo_update(interaction)

    @discord.ui.button(
        label="Manage Pages", style=discord.ButtonStyle.primary, custom_id="todo_nav_manage", emoji="⚙️", row=1
    )
    async def manage_pages_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Check if user is mod or admin
        if not is_mod_or_admin(interaction.user):
            await interaction.response.send_message(
                "❌ You do not have permission to manage pages.",
                ephemeral=True,
            )
            return

        # Show page management menu
        data = await load_todo_data()
        channel_data = await get_channel_data(data, self.channel_id)
        current_page_idx = channel_data.get("current_page", 0)
        pages = channel_data.get("pages", [])

        # Build description with page list
        description = "Manage your todo list pages:\n\n**Available Pages:**\n"
        for idx, page in enumerate(pages):
            page_title = page.get("title", "Untitled")
            item_count = len(page.get("items", []))
            current_marker = "📍 " if idx == current_page_idx else "   "
            description += f"{current_marker}**{idx + 1}.** {page_title} ({item_count} items)\n"

        embed = discord.Embed(
            title="⚙️ Page Management",
            description=description,
            color=PINK,
        )
        set_pink_footer(embed, bot=self.bot.user)

        view = TodoPageManagementView(self.bot, self.channel_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=60)

    async def refresh_display(
        self, interaction: discord.Interaction, data: Dict[str, Any], channel_data: Dict[str, Any]
    ) -> None:
        """Refresh the todo list display for the current page."""
        current_page_idx = channel_data.get("current_page", 0)
        pages = channel_data.get("pages", [])

        if 0 <= current_page_idx < len(pages):
            current_page = pages[current_page_idx]
            items = current_page.get("items", [])
            page_title = current_page.get("title", "📋 To-Do List")

            # Get cog reference
            cog = self.bot.get_cog("TodoList")

            # Delete old messages if exist
            if channel_data.get("message_ids"):
                try:
                    channel = self.bot.get_channel(self.channel_id)
                    if channel:
                        for message_id in channel_data["message_ids"]:
                            try:
                                old_message = await channel.fetch_message(message_id)
                                await old_message.delete()

                                # Remove from persistent views
                                if cog:
                                    cog._remove_persistent_view(self.channel_id, message_id)
                            except Exception as e:
                                logger.warning(f"Could not delete old to-do message {message_id}: {e}")
                except Exception as e:
                    logger.warning(f"Could not delete old to-do messages: {e}")

            # Split items into multiple embeds if needed (12 items per embed)
            max_per_embed = 12
            new_message_ids = []
            total_items = len(items)

            # Create navigation view (only for last message)
            nav_view = TodoPageNavigationView(self.bot, self.channel_id)
            await nav_view.update_buttons()

            channel = interaction.channel

            # Calculate total number of embeds needed
            num_embeds = max(1, (total_items + max_per_embed - 1) // max_per_embed) if total_items > 0 else 1

            # Send messages, splitting items across multiple embeds if needed
            for embed_idx, i in enumerate(range(0, max(1, total_items), max_per_embed)):
                end = min(i + max_per_embed, total_items)
                embed_items = items[i:end] if total_items > 0 else []
                is_first_embed = embed_idx == 0
                is_last_embed = embed_idx == num_embeds - 1

                modal = TodoModal(self.bot, channel_id=self.channel_id)
                embed = modal.create_todo_embed(
                    embed_items,
                    is_first=is_first_embed,
                    total_items=total_items if is_first_embed else None,
                    page_start=i + 1 if not is_first_embed and total_items > 0 else None,
                    page_end=end if not is_first_embed and total_items > 0 else None,
                    page_title=page_title if is_first_embed else None,
                    page_number=current_page_idx + 1 if is_first_embed else None,
                    total_pages=len(pages) if is_first_embed else None,
                )

                # Only attach navigation view to the last embed
                if is_last_embed:
                    new_message = await channel.send(embed=embed, view=nav_view)
                    nav_view.message = new_message

                    # Save persistent view for last message only
                    if cog:
                        cog._save_persistent_view(self.channel_id, new_message.id)
                else:
                    new_message = await channel.send(embed=embed)

                new_message_ids.append(new_message.id)

                # Break if no items (empty page)
                if total_items == 0:
                    break

            # Update channel data with new message info
            channel_data["message_ids"] = new_message_ids
            save_todo_data(data)

            # Update self.message to point to the last message
            self.message = nav_view.message


# === Page Management View ===
class TodoPageManagementView(discord.ui.View):
    def __init__(self, bot: commands.Bot, channel_id: int) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.channel_id = channel_id

    @discord.ui.button(label="Add Page", style=discord.ButtonStyle.success, emoji="➕")
    async def add_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Show modal to enter page title
        modal = AddPageModal(self.bot, self.channel_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Edit Page Title", style=discord.ButtonStyle.primary, emoji="✏️")
    async def edit_page_title(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Load data
        data = await load_todo_data()
        channel_data = await get_channel_data(data, self.channel_id)
        current_page = channel_data.get("current_page", 0)
        pages = channel_data.get("pages", [])

        if 0 <= current_page < len(pages):
            current_title = pages[current_page].get("title", "📋 To-Do List")
            modal = EditPageTitleModal(self.bot, self.channel_id, current_page, current_title)
            await interaction.response.send_modal(modal)

    @discord.ui.button(label="Delete Page", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Load data
        data = await load_todo_data()
        channel_data = await get_channel_data(data, self.channel_id)
        pages = channel_data.get("pages", [])
        current_page = channel_data.get("current_page", 0)

        # Can't delete if only one page
        if len(pages) <= 1:
            await interaction.response.send_message(
                "❌ Cannot delete the last page! You must have at least one page.",
                ephemeral=True,
                delete_after=10,
            )
            return

        # Show confirmation view
        view = DeletePageConfirmView(self.bot, self.channel_id, current_page)
        page_title = pages[current_page].get("title", "Untitled")
        page_items = len(pages[current_page].get("items", []))
        embed = discord.Embed(
            title="⚠️ Confirm Page Deletion",
            description=f"Are you sure you want to delete page {current_page + 1}: **{page_title}**?\n\n"
            f"This will delete all {page_items} items on this page!",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=30)


# === Modal for adding a new page ===
class AddPageModal(discord.ui.Modal, title="➕ Add New Page"):
    page_title = discord.ui.TextInput(
        label="Page Title",
        placeholder="e.g., Development Tasks, Bug Fixes, Future Ideas",
        required=True,
        max_length=100,
    )

    def __init__(self, bot: commands.Bot, channel_id: int) -> None:
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Load data
        data = await load_todo_data()
        channel_data = await get_channel_data(data, self.channel_id)

        # Add new page
        new_page = {"title": self.page_title.value.strip(), "items": []}
        channel_data["pages"].append(new_page)

        # Switch to new page
        channel_data["current_page"] = len(channel_data["pages"]) - 1

        # Save data
        save_todo_data(data)

        # Update the message
        modal = TodoModal(self.bot, channel_id=self.channel_id)
        await interaction.response.defer()
        await modal.update_todo_message(interaction, data, self.channel_id)

        # Send confirmation (followup doesn't support delete_after)
        await interaction.followup.send(f"✅ Added new page: **{new_page['title']}**", ephemeral=True)

        logger.info(f"Added new todo page '{new_page['title']}' in channel {self.channel_id} by {interaction.user}")


# === Modal for editing page title ===
class EditPageTitleModal(discord.ui.Modal, title="✏️ Edit Page Title"):
    page_title = discord.ui.TextInput(
        label="Page Title",
        placeholder="Enter new page title",
        required=True,
        max_length=100,
    )

    def __init__(self, bot: commands.Bot, channel_id: int, page_index: int, current_title: str) -> None:
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id
        self.page_index = page_index
        self.page_title.default = current_title

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Load data
        data = await load_todo_data()
        channel_data = await get_channel_data(data, self.channel_id)
        pages = channel_data.get("pages", [])

        if 0 <= self.page_index < len(pages):
            old_title = pages[self.page_index]["title"]
            pages[self.page_index]["title"] = self.page_title.value.strip()

            # Save data
            save_todo_data(data)

            # Update the message
            modal = TodoModal(self.bot, channel_id=self.channel_id)
            await interaction.response.defer()
            await modal.update_todo_message(interaction, data, self.channel_id)

            # Send confirmation (followup doesn't support delete_after)
            await interaction.followup.send(
                f"✅ Page title updated from **{old_title}** to **{pages[self.page_index]['title']}**", ephemeral=True
            )

            logger.info(f"Updated page title in channel {self.channel_id} by {interaction.user}")


# === Confirmation view for deleting a page ===
class DeletePageConfirmView(discord.ui.View):
    def __init__(self, bot: commands.Bot, channel_id: int, page_index: int) -> None:
        super().__init__(timeout=30)
        self.bot = bot
        self.channel_id = channel_id
        self.page_index = page_index

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Load data
        data = await load_todo_data()
        channel_data = await get_channel_data(data, self.channel_id)
        pages = channel_data.get("pages", [])

        # Validate
        if len(pages) <= 1:
            await interaction.response.send_message("❌ Cannot delete the last page!", ephemeral=True, delete_after=5)
            return

        if 0 <= self.page_index < len(pages):
            deleted_page = pages.pop(self.page_index)

            # Adjust current page if needed
            if channel_data["current_page"] >= len(pages):
                channel_data["current_page"] = len(pages) - 1

            # Save data
            save_todo_data(data)

            # Update the message
            modal = TodoModal(self.bot, channel_id=self.channel_id)
            await interaction.response.defer()
            await modal.update_todo_message(interaction, data, self.channel_id)

            # Send confirmation
            deleted_title = deleted_page.get("title", "Untitled")
            deleted_items = len(deleted_page.get("items", []))
            await interaction.followup.send(
                f"✅ Deleted page: **{deleted_title}** ({deleted_items} items)", ephemeral=True, delete_after=5
            )

            logger.info(f"Deleted page '{deleted_title}' from channel {self.channel_id} by {interaction.user}")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message("❌ Page deletion cancelled.", ephemeral=True, delete_after=5)


# === View for selecting priority before modal ===
class PrioritySelectView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        channel_id: int,
        action: str = "add",
        item_index: Optional[int] = None,
        current_priority: Optional[str] = None,
        current_text: Optional[str] = None,
        management_message=None,  # Add reference to management message
    ) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.channel_id = channel_id
        self.action = action
        self.item_index = item_index
        self.current_priority = current_priority or "low"
        self.current_text = current_text or ""
        self.management_message = management_message

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
            channel_id=self.channel_id,
            action=self.action,
            item_index=self.item_index,
            default_priority=priority,
            default_text=self.current_text,
            management_message=self.management_message,  # Pass through
        )
        await interaction.response.send_modal(modal)


class TodoConfirmView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        channel_id: int,
        formatted_task: Dict[str, str],
        priority: str,
        action: str,
        item_index: Optional[int],
        interaction: discord.Interaction,
        view_message: Optional[discord.Message] = None,
        management_message=None,  # Add reference to management message
    ) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.channel_id = channel_id
        self.formatted_task = formatted_task
        self.priority = priority
        self.action = action
        self.item_index = item_index
        self.original_interaction = interaction
        self.view_message = view_message
        self.management_message = management_message

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
        channel_data = await get_channel_data(data, self.channel_id)

        # Get current page
        current_page_idx = channel_data.get("current_page", 0)
        pages = channel_data.get("pages", [])

        # Validate and auto-correct if needed
        if not pages:
            logger.error(f"No pages found in channel {self.channel_id}, creating default page")
            pages = [{"title": "📋 To-Do List", "items": []}]
            channel_data["pages"] = pages
            current_page_idx = 0
            channel_data["current_page"] = 0
        elif current_page_idx >= len(pages):
            logger.warning(
                f"Invalid current_page index {current_page_idx} in channel {self.channel_id}, resetting to 0"
            )
            current_page_idx = 0
            channel_data["current_page"] = 0

        current_page = pages[current_page_idx]

        if self.action == "add":
            current_page["items"].append(new_item)
            logger.info(
                f"To-do item added to page {current_page_idx} in channel {self.channel_id} by {interaction.user}"
            )
        elif self.action == "edit" and self.item_index is not None:
            if 0 <= self.item_index < len(current_page["items"]):
                current_page["items"][self.item_index] = new_item
                logger.info(
                    f"To-do item {self.item_index} on page {current_page_idx} in channel "
                    f"{self.channel_id} edited by {interaction.user}"
                )
            else:
                logger.error(
                    f"Invalid item index {self.item_index} for page {current_page_idx} in channel {self.channel_id}"
                )

        # Save data
        save_todo_data(data)

        # Defer the response first since update_todo_message takes time
        await interaction.response.defer(ephemeral=True)

        # Update message
        modal = TodoModal(self.bot, channel_id=self.channel_id)
        await modal.update_todo_message(self.original_interaction, data, self.channel_id)

        # Send confirmation via followup
        await interaction.followup.send("✅ To-do item added successfully!", ephemeral=True)

        # Delete the view message (the original preview with buttons)
        if self.view_message:
            try:
                await self.view_message.delete()
            except Exception:
                pass
        # Delete the management message too
        if self.management_message:
            try:
                await self.management_message.delete()
            except Exception:
                pass  # Ignore if already deleted

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message("❌ Cancelled. Item was not added.", ephemeral=True)

        # Delete the view message (the original preview with buttons)
        if self.view_message:
            try:
                await self.view_message.delete()
            except Exception:
                pass
        # Delete the management message too
        if self.management_message:
            try:
                await self.management_message.delete()
            except Exception:
                pass  # Ignore if already deleted


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
        channel_id: int = None,
        action: str = "add",
        item_index: Optional[int] = None,
        default_priority: str = "low",
        default_text: str = "",
        management_message=None,  # Add reference to management message
    ) -> None:
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id
        self.action = action
        self.item_index = item_index
        self.priority.default = default_priority
        self.raw_text.default = default_text
        self.management_message = management_message
        openai.api_key = os.getenv("OPENAI_API_KEY")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Priority is pre-selected, but validate just in case
        priority = self.priority.value.lower().strip()
        if priority not in ["high", "medium", "low"]:
            await interaction.response.send_message(
                "❌ Invalid priority! This shouldn't happen.",
                ephemeral=True,
                delete_after=10,
            )
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

            # Create the view first, send with the view, then set the message reference
            view = TodoConfirmView(
                self.bot,
                self.channel_id,
                formatted_task,
                priority,
                self.action,
                self.item_index,
                interaction,
                management_message=self.management_message,  # Pass through
            )
            if view is None:
                logger.error("Attempted to send preview message with view=None. This should never happen!")
                await interaction.followup.send(
                    "❌ Internal error: Could not create confirmation view.",
                    ephemeral=True,
                )
                return
            preview_msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            view.view_message = preview_msg

        except Exception as e:
            logger.error(f"Error processing to-do item: {e}")
            await interaction.followup.send("❌ Failed to format task with AI. Check logs.", ephemeral=True)

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

    async def update_todo_message(
        self, interaction: discord.Interaction, data: Dict[str, Any], channel_id: int
    ) -> None:
        """Update or create the to-do list message in the channel."""
        channel_data = await get_channel_data(data, channel_id)
        current_page_idx = channel_data.get("current_page", 0)
        pages = channel_data.get("pages", [])

        # Validate and auto-correct current_page if out of bounds
        if not pages:
            logger.error(f"No pages found in channel {channel_id}, creating default page")
            pages = [{"title": "📋 To-Do List", "items": []}]
            channel_data["pages"] = pages
            current_page_idx = 0
            channel_data["current_page"] = 0
            save_todo_data(data)
        elif current_page_idx >= len(pages):
            logger.warning(f"Invalid current_page index {current_page_idx} in channel {channel_id}, resetting to 0")
            current_page_idx = 0
            channel_data["current_page"] = 0
            save_todo_data(data)

        # Get current page items
        current_page = pages[current_page_idx]
        items = current_page.get("items", [])
        page_title = current_page.get("title", "📋 To-Do List")

        # Get cog reference
        cog = self.bot.get_cog("TodoList")

        # Delete old messages if exist
        if channel_data.get("message_ids"):
            try:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    for message_id in channel_data["message_ids"]:
                        try:
                            old_message = await channel.fetch_message(message_id)
                            await old_message.delete()
                            logger.info(f"Deleted old to-do message {message_id} in channel {channel_id}")

                            # Remove from persistent views
                            if cog:
                                cog._remove_persistent_view(channel_id, message_id)
                        except Exception as e:
                            logger.warning(f"Could not delete old to-do message {message_id}: {e}")
            except Exception as e:
                logger.warning(f"Could not delete old to-do messages: {e}")

        # Split items into multiple embeds if needed (12 items per embed)
        max_per_embed = 12
        new_message_ids = []
        total_items = len(items)

        # Create navigation view (only for last message)
        nav_view = TodoPageNavigationView(self.bot, channel_id)
        await nav_view.update_buttons()

        channel = interaction.channel

        # Calculate total number of embeds needed
        num_embeds = max(1, (total_items + max_per_embed - 1) // max_per_embed) if total_items > 0 else 1

        # Send messages, splitting items across multiple embeds if needed
        for embed_idx, i in enumerate(range(0, max(1, total_items), max_per_embed)):
            end = min(i + max_per_embed, total_items)
            embed_items = items[i:end] if total_items > 0 else []
            is_first_embed = embed_idx == 0
            is_last_embed = embed_idx == num_embeds - 1

            embed = self.create_todo_embed(
                embed_items,
                is_first=is_first_embed,
                total_items=total_items if is_first_embed else None,
                page_start=i + 1 if not is_first_embed and total_items > 0 else None,
                page_end=end if not is_first_embed and total_items > 0 else None,
                page_title=page_title if is_first_embed else None,
                page_number=current_page_idx + 1 if is_first_embed else None,
                total_pages=len(pages) if is_first_embed else None,
            )

            # Only attach navigation view to the last embed
            if is_last_embed:
                new_message = await channel.send(embed=embed, view=nav_view)
                nav_view.message = new_message

                # Save persistent view for last message only
                if cog:
                    cog._save_persistent_view(channel_id, new_message.id)
            else:
                new_message = await channel.send(embed=embed)

            new_message_ids.append(new_message.id)

            # Break if no items (empty page)
            if total_items == 0:
                break

        # Update channel data with new message info
        channel_data["message_ids"] = new_message_ids
        save_todo_data(data)

        logger.info(f"Posted {len(new_message_ids)} to-do message(s) in channel {channel_id}")

    def create_todo_embed(
        self,
        items: List[Dict[str, Any]],
        is_first: bool = True,
        total_items: Optional[int] = None,
        page_start: Optional[int] = None,
        page_end: Optional[int] = None,
        page_title: Optional[str] = None,
        page_number: Optional[int] = None,
        total_pages: Optional[int] = None,
    ) -> discord.Embed:
        """Create a formatted to-do list embed."""
        embed = discord.Embed(color=PINK)

        # Use page title if provided, otherwise use default
        if page_title:
            # Add page counter if multiple pages exist
            if total_pages and total_pages > 1:
                embed.title = f"{page_title} (Page {page_number}/{total_pages})"
            else:
                embed.title = page_title
        elif not is_first and page_start and page_end:
            embed.title = f"📋 To-Do List (Continued - Items {page_start}-{page_end})"
        else:
            embed.title = "📋 To-Do List"

        # Group items by priority
        high_priority = [item for item in items if item["priority"] == "high"]
        medium_priority = [item for item in items if item["priority"] == "medium"]
        low_priority = [item for item in items if item["priority"] == "low"]

        # Build description
        description_parts = []

        # Add high priority items
        if high_priority:
            description_parts.append(f"\n{PRIORITY_EMOJIS['high']} **High Priority**")
            for i, item in enumerate(high_priority):
                description_parts.append(f"{item['title']}")
                if item.get("description"):
                    description_parts.append(f"{item['description']}")
                description_parts.append(f"👤 *Added by {item.get('author_name', 'Unknown')}*")
                description_parts.append("")  # Empty line

        # Add medium priority items
        if medium_priority:
            description_parts.append(f"\n{PRIORITY_EMOJIS['medium']} **Medium Priority**")
            for i, item in enumerate(medium_priority):
                description_parts.append(f"{item['title']}")
                if item.get("description"):
                    description_parts.append(f"{item['description']}")
                description_parts.append(f"👤 *Added by {item.get('author_name', 'Unknown')}*")
                description_parts.append("")  # Empty line

        # Add low priority items
        if low_priority:
            description_parts.append(f"\n{PRIORITY_EMOJIS['low']} **Low Priority**")
            for i, item in enumerate(low_priority):
                description_parts.append(f"{item['title']}")
                if item.get("description"):
                    description_parts.append(f"{item['description']}")
                description_parts.append(f"👤 *Added by {item.get('author_name', 'Unknown')}*")
                description_parts.append("")  # Empty line

        if not items:
            description_parts.append("No items yet! Use `/todo-update` to add one.")

        description_parts.append("\n🚀 Stay tuned for updates!")

        # Join
        full_description = "\n".join(description_parts)

        # For first embed, check if needs truncation
        if is_first and total_items and total_items > len(items):
            shown = len(items)
            total = total_items
            embed.description = (
                full_description + "\n\n⚠️ **List truncated due to length.**\n"
                f"Showing first {shown} items.\n"
                f"Total items: {total}"
            )
        else:
            embed.description = full_description

        set_pink_footer(embed, bot=self.bot.user)
        return embed


# === View for managing to-do list ===
class TodoManageView(discord.ui.View):
    def __init__(self, bot: commands.Bot, channel_id: int, management_message=None) -> None:
        super().__init__(timeout=300)
        self.bot = bot
        self.channel_id = channel_id
        self.management_message = management_message  # Store reference to management embed

    @discord.ui.button(label="Add Item", style=discord.ButtonStyle.green, emoji="➕")
    async def add_item(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Check if user is mod or admin
        if not is_mod_or_admin(interaction.user):
            await interaction.response.send_message(
                "❌ You do not have permission to use this.",
                ephemeral=True,
                delete_after=10,
            )
            return

        # Send priority selection view
        embed = discord.Embed(
            title="Select Priority",
            description="Choose the priority level for the new to-do item:",
            color=PINK,
        )
        set_pink_footer(embed, bot=self.bot.user)
        view = PrioritySelectView(self.bot, self.channel_id, action="add", management_message=self.management_message)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=30)

    @discord.ui.button(label="Edit Item", style=discord.ButtonStyle.primary, emoji="✏️")
    async def edit_item(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Check if user is mod or admin
        if not is_mod_or_admin(interaction.user):
            await interaction.response.send_message(
                "❌ You do not have permission to use this.",
                ephemeral=True,
                delete_after=10,
            )
            return

        # Load data
        data = await load_todo_data()
        channel_data = await get_channel_data(data, self.channel_id)
        current_page_idx = channel_data.get("current_page", 0)
        pages = channel_data.get("pages", [])

        if 0 <= current_page_idx < len(pages):
            current_page = pages[current_page_idx]
            items = current_page.get("items", [])

            if not items:
                await interaction.response.send_message(
                    "❌ No items to edit on current page!", ephemeral=True, delete_after=10
                )
                return

            # Create view with select
            view = TodoEditSelectView(self.bot, self.channel_id, items)

            embed = discord.Embed(
                title="✏️ Edit To-Do Item", description="Select the item you want to edit:", color=PINK
            )
            set_pink_footer(embed, bot=self.bot.user)

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=30)

    @discord.ui.button(label="Remove Item", style=discord.ButtonStyle.red, emoji="🗑️")
    async def remove_item(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Check if user is mod or admin
        if not is_mod_or_admin(interaction.user):
            await interaction.response.send_message(
                "❌ You do not have permission to use this.",
                ephemeral=True,
                delete_after=10,
            )
            return

        # Load data
        data = await load_todo_data()
        channel_data = await get_channel_data(data, self.channel_id)
        current_page_idx = channel_data.get("current_page", 0)
        pages = channel_data.get("pages", [])

        if 0 <= current_page_idx < len(pages):
            current_page = pages[current_page_idx]
            items = current_page.get("items", [])

            if not items:
                await interaction.response.send_message(
                    "❌ No items to remove on current page!", ephemeral=True, delete_after=10
                )
                return

            # Create view with select
            view = TodoRemoveSelectView(self.bot, self.channel_id, items)

            # Check if select was created
            if not view.select:
                await interaction.response.send_message(
                    "❌ Failed to create removal options. Try again.",
                    ephemeral=True,
                    delete_after=10,
                )
                return

            embed = discord.Embed(
                title="🗑️ Remove To-Do Item",
                description="Select the item you want to remove:",
                color=discord.Color.red(),
            )

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=30)

    @discord.ui.button(label="Clear All", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def clear_all(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Check if user is mod or admin
        if not is_mod_or_admin(interaction.user):
            await interaction.response.send_message(
                "❌ You do not have permission to use this.",
                ephemeral=True,
                delete_after=10,
            )
            return

        # Defer immediately to prevent timeout
        await interaction.response.defer()

        try:
            # Load data
            data = await load_todo_data()
            channel_data = await get_channel_data(data, self.channel_id)
            current_page_idx = channel_data.get("current_page", 0)
            pages = channel_data.get("pages", [])

            # Clear all items on current page
            if 0 <= current_page_idx < len(pages):
                pages[current_page_idx]["items"] = []
                save_todo_data(data)

                # Update message
                modal = TodoModal(self.bot, channel_id=self.channel_id)
                await modal.update_todo_message(interaction, data, self.channel_id)

                logger.info(
                    f"All to-do items cleared on page {current_page_idx} in channel "
                    f"{self.channel_id} by {interaction.user}"
                )

                # Send confirmation (stays for 3 seconds)
                confirm_msg = await interaction.followup.send(
                    "✅ All to-do items on current page cleared!", ephemeral=True
                )

                # Delete confirmation after 3 seconds
                await asyncio.sleep(3)
                try:
                    await confirm_msg.delete()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Error clearing to-do items: {e}")
            await interaction.followup.send(f"❌ Error clearing items: {str(e)}", ephemeral=True)


# === Select view for editing specific items ===
class TodoEditSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot, channel_id: int, items: List[Dict[str, Any]]) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.channel_id = channel_id
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
                self.channel_id,
                action="edit",
                item_index=index,
                current_priority=current_priority,
                current_text=current_text,
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=30)


# === Select view for removing specific items ===
class TodoRemoveSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot, channel_id: int, items: List[Dict[str, Any]]) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.channel_id = channel_id
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
        channel_data = await get_channel_data(data, self.channel_id)
        current_page_idx = channel_data.get("current_page", 0)
        pages = channel_data.get("pages", [])
        removed_items = []

        # Remove selected items from current page (from end to start to avoid index issues)
        if 0 <= current_page_idx < len(pages):
            current_page = pages[current_page_idx]
            for index in indices:
                if 0 <= index < len(current_page["items"]):
                    removed_items.append(current_page["items"].pop(index))

        save_todo_data(data)

        # Update message
        modal = TodoModal(self.bot, channel_id=self.channel_id)
        await interaction.response.defer()
        await modal.update_todo_message(interaction, data, self.channel_id)

        # Log removed items
        removed_titles = ", ".join([f"'{item['title']}'" for item in reversed(removed_items)])
        logger.info(
            f"Removed {len(removed_items)} to-do item(s) from page {current_page_idx} in channel {self.channel_id}: "
            f"{removed_titles} by {interaction.user}"
        )

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
        self.persistent_views_file = TODO_PERSISTENT_VIEWS_FILE
        self.persistent_views_data = []

        # Load persistent views data silently (logging happens in restore)
        if os.path.exists(self.persistent_views_file):
            try:
                with open(self.persistent_views_file, "r", encoding="utf-8") as f:
                    self.persistent_views_data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load persistent views data: {e}")
                self.persistent_views_data = []
        else:
            os.makedirs(os.path.dirname(self.persistent_views_file), exist_ok=True)
            self.persistent_views_data = []

    async def cog_load(self) -> None:
        """Called when the cog is loaded (including reloads)."""
        if self.bot.is_ready():
            await self._restore_persistent_views()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Restore persistent views when the bot is ready."""
        await self._restore_persistent_views()

    async def _restore_persistent_views(self) -> None:
        """Restore persistent navigation views for all todo messages."""
        restored_count = 0
        cleaned_data = []

        for view_data in self.persistent_views_data:
            channel_id = view_data.get("channel_id")
            message_id = view_data.get("message_id")

            if not channel_id or not message_id:
                continue

            channel = self.bot.get_channel(channel_id)
            if not channel:
                logger.warning(f"Channel {channel_id} not found, skipping view restoration")
                continue

            try:
                message = await channel.fetch_message(message_id)

                # Create and attach the view
                view = TodoPageNavigationView(self.bot, channel_id)
                await view.update_buttons()
                view.message = message

                # Edit message to re-attach the view
                await message.edit(view=view)

                restored_count += 1
                cleaned_data.append(view_data)
                logger.info(f"Restored todo navigation view for message {message_id} in channel {channel_id}")

                await asyncio.sleep(1)  # Rate limit protection

            except discord.NotFound:
                logger.warning(f"Message {message_id} not found, removing from persistent views")
            except Exception as e:
                logger.error(f"Failed to restore view for message {message_id}: {e}")
                cleaned_data.append(view_data)  # Keep on other errors

        # Save cleaned data
        self.persistent_views_data = cleaned_data
        with open(self.persistent_views_file, "w", encoding="utf-8") as f:
            json.dump(self.persistent_views_data, f, indent=2)

        logger.info(f"Restored {restored_count} persistent navigation views")

    def _save_persistent_view(self, channel_id: int, message_id: int) -> None:
        """Save a persistent view to the data file."""
        # Check if already exists
        for view_data in self.persistent_views_data:
            if view_data.get("channel_id") == channel_id and view_data.get("message_id") == message_id:
                logger.info(f"View for message {message_id} already in persistent storage")
                return  # Already saved

        # Add new entry
        self.persistent_views_data.append({"channel_id": channel_id, "message_id": message_id})

        # Save to file
        try:
            with open(self.persistent_views_file, "w", encoding="utf-8") as f:
                json.dump(self.persistent_views_data, f, indent=2)
            logger.info(f"Saved persistent view for message {message_id} in channel {channel_id}")
        except Exception as e:
            logger.error(f"Failed to save persistent view: {e}")

    def _remove_persistent_view(self, channel_id: int, message_id: int) -> None:
        """Remove a persistent view from the data file."""
        original_count = len(self.persistent_views_data)
        self.persistent_views_data = [
            view_data
            for view_data in self.persistent_views_data
            if not (view_data.get("channel_id") == channel_id and view_data.get("message_id") == message_id)
        ]

        # Save to file if something was removed
        if len(self.persistent_views_data) < original_count:
            try:
                with open(self.persistent_views_file, "w", encoding="utf-8") as f:
                    json.dump(self.persistent_views_data, f, indent=2)
                logger.info(f"Removed persistent view for message {message_id} in channel {channel_id}")
            except Exception as e:
                logger.error(f"Failed to remove persistent view: {e}")

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
                await ctx_or_interaction.response.send_message(
                    message,
                    ephemeral=True,
                    delete_after=10,
                )
            return

        # Get current channel
        channel = ctx_or_interaction.channel
        channel_id = channel.id

        # Show management view
        data = await load_todo_data()
        channel_data = await get_channel_data(data, channel_id)
        current_page_idx = channel_data.get("current_page", 0)
        pages = channel_data.get("pages", [])

        # Get current page item count
        current_items = 0
        if 0 <= current_page_idx < len(pages):
            current_items = len(pages[current_page_idx].get("items", []))

        embed = discord.Embed(
            title="📋 To-Do List Management",
            description=f"Use the buttons below to manage the to-do list for <#{channel_id}>.\n\n"
            f"**Current Page:** {current_page_idx + 1}/{len(pages)}\n"
            f"**Items on Current Page:** {current_items}",
            color=PINK,
        )
        set_pink_footer(embed, bot=self.bot.user)

        view = TodoManageView(self.bot, channel_id)
        if hasattr(ctx_or_interaction, "send"):
            management_msg = await ctx_or_interaction.send(embed=embed, view=view)
        else:
            management_msg = await ctx_or_interaction.response.send_message(
                embed=embed, view=view, ephemeral=True, delete_after=30
            )
            # For slash commands, get the message from the interaction
            management_msg = await ctx_or_interaction.original_response()

        # Update view with the management message reference
        view.management_message = management_msg

        logger.info(f"todo-update used by {user} in channel {channel_id}")

    # 🧩 Shared handler for todo-show logic
    async def handle_todo_show(self, ctx_or_interaction: Any) -> None:
        """Shared handler for todo-show command."""
        # Get current channel
        channel = ctx_or_interaction.channel
        channel_id = channel.id

        data = await load_todo_data()
        channel_data = await get_channel_data(data, channel_id)
        current_page_idx = channel_data.get("current_page", 0)
        pages = channel_data.get("pages", [])

        # Check if current page has items
        has_items = False
        if 0 <= current_page_idx < len(pages):
            has_items = len(pages[current_page_idx].get("items", [])) > 0

        if not has_items:
            message = f"📋 The current page of the to-do list for <#{channel_id}> is empty!"
            if hasattr(ctx_or_interaction, "send"):
                await ctx_or_interaction.send(message)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
            return

        # Get current page data
        current_page = pages[current_page_idx]
        items = current_page.get("items", [])
        page_title = current_page.get("title", "📋 To-Do List")

        modal = TodoModal(self.bot, channel_id=channel_id)
        embed = modal.create_todo_embed(
            items,
            is_first=True,
            total_items=len(items),
            page_title=page_title,
            page_number=current_page_idx + 1,
            total_pages=len(pages),
        )
        if hasattr(ctx_or_interaction, "send"):
            await ctx_or_interaction.send(embed=embed)
        else:
            await ctx_or_interaction.response.send_message(embed=embed, ephemeral=False)

        user = ctx_or_interaction.author if hasattr(ctx_or_interaction, "author") else ctx_or_interaction.user
        logger.info(f"todo-show used by {user} in channel {channel_id}")

    # !todo-update (Prefix) - Mod/Admin only
    @commands.command(name="todo-update")
    async def todo_update_prefix(self, ctx: commands.Context) -> None:
        """
        📋 Update the to-do list for this channel with interactive buttons. (Mod/Admin only)
        Each channel can have its own independent to-do list.
        """
        await self.handle_todo_update(ctx)

    # /todo-update (Slash) - Mod/Admin only
    @app_commands.command(
        name="todo-update", description="📋 Update the to-do list for this channel with interactive buttons."
    )
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    async def todo_update_slash(self, interaction: discord.Interaction) -> None:
        await self.handle_todo_update(interaction)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TodoList(bot))
