import json
import logging
import os
from datetime import datetime
from typing import List, Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

import Config
from Config import (
    IMGFLIP_PASSWORD,
    IMGFLIP_USERNAME,
    MEME_TEMPLATES_CACHE_DURATION,
    MEME_TEMPLATES_CACHE_FILE,
    get_data_dir,
    get_guild_id,
)
from Utils.EmbedUtils import set_pink_footer

logger = logging.getLogger(__name__)


class TemplateButton(discord.ui.Button):
    """Button for selecting a template with thumbnail"""

    def __init__(self, template: dict, position: int, row: int):
        # Use emoji numbers for visual clarity
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        emoji = emojis[position] if position < len(emojis) else "▶️"

        # Shorten label to fit button
        label = template["name"][:20]

        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=label,
            emoji=emoji,
            custom_id=f"template_{template['id']}",
            row=row,
        )
        self.template = template
        self.position = position

    async def callback(self, interaction: discord.Interaction):
        view: MemeGeneratorHubView = self.view

        # Update selected template
        view.selected_template = self.template
        view.selected_position = self.position

        # Update embed to show new preview
        embed = view.get_template_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class CreateSelectedButton(discord.ui.Button):
    """Button to create meme with currently selected template"""

    def __init__(self):
        super().__init__(style=discord.ButtonStyle.success, label="Create Meme", emoji="✨", row=2)

    async def callback(self, interaction: discord.Interaction):
        view: MemeGeneratorHubView = self.view

        if not view.selected_template:
            await interaction.response.send_message("⚠️ Please select a template first!", ephemeral=True)
            return

        # Open modal for text input with channel context
        modal = MemeTextModal(view.cog, view.selected_template, post_to_channel_id=view.post_to_channel_id)
        await interaction.response.send_modal(modal)


class MemeGeneratorHubView(discord.ui.View):
    """Main hub for browsing and creating memes with clickable template buttons"""

    def __init__(self, cog: "MemeGenerator", post_to_channel_id: int = None):
        super().__init__(timeout=300)
        self.cog = cog
        self.current_page = 0
        self.templates_per_page = 10  # 10 templates per page
        self.selected_template = None  # Currently selected template
        self.selected_position = 0  # Position of selected template
        self.post_to_channel_id = post_to_channel_id  # If set, post to this channel instead of ephemeral

        # Add navigation buttons (row 3 - bottom)
        prev_btn = PreviousPageButton()
        next_btn = NextPageButton()
        prev_btn.row = 3
        next_btn.row = 3
        self.add_item(prev_btn)
        self.add_item(next_btn)

        # Add create button (row 2)
        self.add_item(CreateSelectedButton())

        # Add template buttons (rows 0-1)
        self.update_template_buttons()

        # Select first template by default
        if self.cog.templates:
            self.selected_template = self.cog.templates[0]
            self.selected_position = 0

    def update_template_buttons(self):
        """Update template buttons for current page"""
        # Remove old template buttons (keep navigation and create buttons)
        items_to_remove = [item for item in self.children if isinstance(item, TemplateButton)]
        for item in items_to_remove:
            self.remove_item(item)

        # Calculate page range
        start_idx = self.current_page * self.templates_per_page
        end_idx = start_idx + self.templates_per_page
        page_templates = self.cog.templates[start_idx:end_idx]

        # Add template buttons (5 per row, up to 2 rows = 10 templates)
        for i, template in enumerate(page_templates):
            row = i // 5  # Row 0-1 for first 10 templates
            button = TemplateButton(template, i, row)
            self.add_item(button)

        # Select first template of new page
        if page_templates:
            self.selected_template = page_templates[0]
            self.selected_position = 0

    async def template_selected(self, interaction: discord.Interaction):
        """Handle template selection"""
        template_id = interaction.data["values"][0]

        # Find template info
        template_info = next(
            (t for t in self.cog.templates if str(t.get("id")) == template_id),
            None,
        )

        if not template_info:
            await interaction.response.send_message("❌ Template not found!", ephemeral=True)
            return

        # Open modal with text fields
        modal = MemeTextModal(self.cog, template_info)
        await interaction.response.send_modal(modal)

    def get_template_embed(self) -> discord.Embed:
        """Create a single compact embed with template list and one preview"""
        total_templates = len(self.cog.templates)
        total_pages = (total_templates + self.templates_per_page - 1) // self.templates_per_page
        current_page = self.current_page + 1

        # Get templates for current page
        start_idx = self.current_page * self.templates_per_page
        end_idx = start_idx + self.templates_per_page
        page_templates = self.cog.templates[start_idx:end_idx]

        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        # Create compact list of all templates
        template_list = []
        for i, template in enumerate(page_templates):
            emoji = emojis[i] if i < len(emojis) else "▶️"
            name = template.get("name", "Unknown")
            box_count = template.get("box_count", 2)

            # Highlight selected template
            if self.selected_template and template.get("id") == self.selected_template.get("id"):
                display_name = f"**➤ {name[:30]}**"
            else:
                display_name = name[:33] if len(name) <= 33 else name[:30] + "..."

            template_list.append(f"{emoji} {display_name} · `{box_count}`")

        # Split into two columns for compact layout
        half = (len(template_list) + 1) // 2
        left_column = "\n".join(template_list[:half])
        right_column = "\n".join(template_list[half:]) if len(template_list) > half else "⠀"

        # Get selected template info
        if self.selected_template:
            selected_name = self.selected_template.get("name", "Unknown")
            selected_boxes = self.selected_template.get("box_count", 2)
            selected_emoji = emojis[self.selected_position] if self.selected_position < len(emojis) else "▶️"
        else:
            selected_name = "None"
            selected_boxes = 0
            selected_emoji = "❓"

        # Single embed with compact grid and large preview
        embed = discord.Embed(
            title="🎨 Meme Template Gallery",
            description=(
                f"**Page {current_page}/{total_pages}** · "
                f"Showing {len(page_templates)} of {total_templates} templates\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"**Selected:** {selected_emoji} {selected_name} · {selected_boxes} boxes\n"
                f"**Click a button to preview · Click ✨ Create to make meme**"
            ),
            color=Config.PINK,
        )

        embed.add_field(name="📋 Templates", value=left_column, inline=True)
        embed.add_field(name="_ _", value=right_column, inline=True)

        # Show selected template as LARGE preview (bottom of embed)
        if self.selected_template:
            embed.set_image(url=self.selected_template.get("url"))

        embed.set_footer(text="💡 Use ◀️ ▶️ to navigate pages")

        return embed


class PreviousPageButton(discord.ui.Button):
    """Button to go to previous page"""

    def __init__(self):
        super().__init__(label="◀️ Previous", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        view: MemeGeneratorHubView = self.view
        if view.current_page > 0:
            view.current_page -= 1
            view.update_template_buttons()
            embed = view.get_template_embed()
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message("⚠️ Already on first page!", ephemeral=True)


class NextPageButton(discord.ui.Button):
    """Button to go to next page"""

    def __init__(self):
        super().__init__(label="Next ▶️", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        view: MemeGeneratorHubView = self.view
        total_pages = (len(view.cog.templates) + view.templates_per_page - 1) // view.templates_per_page
        if view.current_page < total_pages - 1:
            view.current_page += 1
            view.update_template_buttons()
            embed = view.get_template_embed()
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message("⚠️ Already on last page!", ephemeral=True)


class MemeTextModal(discord.ui.Modal):
    """Modal for entering meme text with dynamic fields based on template"""

    def __init__(self, cog: "MemeGenerator", template_info: dict, post_to_channel_id: int = None):
        super().__init__(title=f"Create: {template_info.get('name', 'Meme')[:45]}")
        self.cog = cog
        self.template_info = template_info
        self.box_count = template_info.get("box_count", 2)
        self.post_to_channel_id = post_to_channel_id  # Channel to post to (if from Server Guide)

        # Add text inputs dynamically based on box_count
        # Limit to 5 fields (Discord modal limit)
        max_fields = min(self.box_count, 5)

        # Common labels for standard positions
        labels = ["Top Text", "Bottom Text", "Middle Text", "Text Box 4", "Text Box 5"]

        for i in range(max_fields):
            text_input = discord.ui.TextInput(
                label=labels[i] if i < len(labels) else f"Text Box {i + 1}",
                placeholder=f"Enter text for box {i + 1}...",
                required=False,
                max_length=200,
                style=discord.TextStyle.short,
            )
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission - generate preview and show confirm buttons"""
        await interaction.response.defer(ephemeral=True)

        # Collect text from all fields
        texts = [child.value for child in self.children if isinstance(child, discord.ui.TextInput)]

        # Debug: Log what we received
        logger.info(f"Modal submitted with {len(texts)} texts: {texts}")

        # Check if at least one field has text
        if not any(texts):
            await interaction.followup.send("❌ Please provide at least one text field!", ephemeral=True)
            return

        # Generate preview meme with the texts
        template_id = self.template_info.get("id")

        # Prepare text boxes for API
        boxes = []
        for i, text in enumerate(texts):
            if text:  # Only include non-empty texts
                boxes.append({"text": text, "color": "#ffffff", "outline_color": "#000000"})

        # Call Imgflip API to generate preview
        if self.box_count <= 2:
            meme_url = await self.cog.create_meme(
                template_id,
                texts[0] if texts else "",
                texts[1] if len(texts) > 1 else "",
            )
        else:
            # Convert list to text0, text1, text2, etc. format
            # Include ALL fields (even empty ones) to maintain correct box order
            text_params = {f"text{i}": text if text else "" for i, text in enumerate(texts)}
            logger.info(f"Creating meme with text_params: {text_params}")
            meme_url = await self.cog.create_meme_advanced(template_id, text_params)

        if not meme_url:
            await interaction.followup.send("❌ Failed to generate meme preview. Please try again!", ephemeral=True)
            return

        # Show preview with confirm/cancel buttons
        view = MemePreviewView(
            cog=self.cog,
            template_info=self.template_info,
            texts=texts,
            user=interaction.user,
            channel=interaction.channel,
            meme_url=meme_url,  # Pass the generated meme URL
            post_to_channel_id=self.post_to_channel_id,  # Pass channel context
        )

        # Create preview embed with GENERATED meme
        embed = discord.Embed(
            title=f"🎨 Preview: {self.template_info.get('name', 'Meme')}",
            description="Review your meme before posting:",
            color=Config.PINK,
        )
        embed.set_image(url=meme_url)  # Show the GENERATED meme with texts

        # Show the texts as fields
        for i, text in enumerate(texts):
            if text:
                label = ["Top Text", "Bottom Text", "Middle Text", "Text 4", "Text 5"][i] if i < 5 else f"Text {i + 1}"
                embed.add_field(name=label, value=text or "*Empty*", inline=True)

        embed.set_footer(text="✅ Confirm to post | ❌ Cancel")

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class MemePreviewView(discord.ui.View):
    """View for confirming meme before posting"""

    def __init__(
        self,
        cog: "MemeGenerator",
        template_info: dict,
        texts: list,
        user: discord.User,
        channel: discord.TextChannel,
        meme_url: str,
        post_to_channel_id: int = None,
    ):
        super().__init__(timeout=300)
        self.cog = cog
        self.template_info = template_info
        self.texts = texts
        self.user = user
        self.channel = channel
        self.meme_url = meme_url  # Store the generated meme URL
        self.post_to_channel_id = post_to_channel_id  # Target channel if different

    @discord.ui.button(label="✅ Confirm & Post", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Post the already-generated meme"""
        await interaction.response.defer()

        # Use the already-generated meme URL (no need to generate again)
        meme_url = self.meme_url

        # Create embed for posting
        embed = discord.Embed(
            title=f"🎨 Custom Meme: {self.template_info.get('name', 'Meme')}",
            color=Config.PINK,
            timestamp=datetime.now(),
        )
        embed.set_image(url=meme_url)

        # Add text fields
        for i, text in enumerate(self.texts):
            if text:
                labels = ["🔝 Top Text", "🔽 Bottom Text", "⏺️ Middle Text", "📝 Text 4", "📝 Text 5"]
                label = labels[i] if i < len(labels) else f"📝 Text {i + 1}"
                embed.add_field(name=label, value=text, inline=True)

        embed.add_field(name="👤 Created by", value=self.user.mention, inline=False)

        set_pink_footer(embed, bot=self.cog.bot.user)

        # Determine target channel
        target_channel = self.channel
        if self.post_to_channel_id:
            # If called from Server Guide, post to specified channel (Memes channel)
            target_channel = interaction.guild.get_channel(self.post_to_channel_id)
            if not target_channel:
                await interaction.followup.send("❌ Target channel not found!", ephemeral=True)
                return

        # Post to channel
        await target_channel.send(f"🎨 Custom meme created by {self.user.mention}!", embed=embed)

        # Award XP for meme generation
        level_cog = self.cog.bot.get_cog("LevelSystem")
        if level_cog:
            await level_cog.add_xp(
                user_id=str(self.user.id),
                username=self.user.name,
                xp_type="meme_generated"
            )

        # Track generated meme
        user_id = str(self.user.id)
        self.cog.memes_generated[user_id] = self.cog.memes_generated.get(user_id, 0) + 1
        self.cog.save_memes_generated()

        # Confirm to user
        if self.post_to_channel_id and target_channel != self.channel:
            await interaction.followup.send(f"✅ Meme posted successfully to {target_channel.mention}!", ephemeral=True)
        else:
            await interaction.followup.send("✅ Meme posted successfully!", ephemeral=True)

        logger.info(
            f"Meme created by {self.user}: {self.template_info.get('name')} "
            f"with {len([t for t in self.texts if t])} text boxes "
            f"(posted to #{target_channel.name})"
        )

        self.stop()

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel meme creation"""
        await interaction.response.edit_message(content="❌ Meme creation cancelled.", embed=None, view=None)
        self.stop()


class MemeGenerator(commands.Cog):
    """
    🎨 Meme Generator Cog: Create custom memes using popular templates
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session = None
        self.templates_cache_file = MEME_TEMPLATES_CACHE_FILE
        self.templates_cache_duration = MEME_TEMPLATES_CACHE_DURATION
        self.templates = []
        self.templates_last_fetched = 0
        self._setup_done = False

        # Meme generation tracking
        self.memes_generated_file = os.path.join(get_data_dir(), "memes_generated.json")
        self.memes_generated = self.load_memes_generated()

    async def _setup_cog(self) -> None:
        """Setup the cog - called on ready and after reload"""
        # Create HTTP session if not exists
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

        # Load cached templates
        self.templates = self.load_templates_cache()

        # Check credentials and log status
        if not IMGFLIP_USERNAME or not IMGFLIP_PASSWORD:
            logger.warning("Imgflip credentials not configured - meme generation disabled")
            logger.info("To enable: Add IMGFLIP_USERNAME and IMGFLIP_PASSWORD to .env")
            logger.info("Sign up for free at https://imgflip.com/signup")
        else:
            logger.info(f"Meme Generator ready with {len(self.templates)} cached templates")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Setup when bot is ready"""
        if self._setup_done:
            return  # Only setup once

        self._setup_done = True
        await self._setup_cog()

    async def cog_load(self) -> None:
        """Called when the cog is loaded (including reloads)"""
        if self.bot.is_ready():
            await self._setup_cog()

    async def cog_unload(self):
        """Called when the cog is unloaded"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("HTTP session closed")

    def load_templates_cache(self) -> list:
        """Load templates from cache file"""
        try:
            if os.path.exists(self.templates_cache_file):
                with open(self.templates_cache_file, "r") as f:
                    data = json.load(f)
                    self.templates_last_fetched = data.get("timestamp", 0)
                    templates = data.get("templates", [])
                    # Don't log here - will be logged in cog_load
                    return templates
        except Exception as e:
            logger.error(f"Error loading templates cache: {e}")
        return []

    def save_templates_cache(self) -> None:
        """Save templates to cache file"""
        try:
            os.makedirs(os.path.dirname(self.templates_cache_file), exist_ok=True)
            with open(self.templates_cache_file, "w") as f:
                json.dump(
                    {
                        "timestamp": self.templates_last_fetched,
                        "templates": self.templates,
                    },
                    f,
                    indent=4,
                )
            logger.info(f"Saved {len(self.templates)} templates to cache")
        except Exception as e:
            logger.error(f"Error saving templates cache: {e}")

    async def fetch_templates(self, force: bool = False) -> List[dict]:
        """
        Fetch meme templates from Imgflip API

        Args:
            force: Force refresh even if cache is valid

        Returns:
            List of template dictionaries
        """
        # Check cache validity
        current_time = datetime.now().timestamp()
        cache_age = current_time - self.templates_last_fetched

        if not force and self.templates and cache_age < self.templates_cache_duration:
            logger.debug(f"Using cached templates (age: {int(cache_age)}s)")
            return self.templates

        # Fetch from API
        try:
            url = "https://api.imgflip.com/get_memes"
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Imgflip API returned {response.status}")
                    return self.templates  # Return cached templates on error

                data = await response.json()
                if not data.get("success"):
                    logger.error("Imgflip API request failed")
                    return self.templates

                memes = data.get("data", {}).get("memes", [])
                self.templates = memes
                self.templates_last_fetched = current_time
                self.save_templates_cache()

                logger.info(f"Fetched {len(memes)} templates from Imgflip API")
                return self.templates

        except Exception as e:
            logger.error(f"Error fetching templates: {e}")
            return self.templates

    def load_memes_generated(self) -> dict:
        """Load memes generated count from file"""
        try:
            if os.path.exists(self.memes_generated_file):
                with open(self.memes_generated_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading memes generated: {e}")
        return {}

    def save_memes_generated(self) -> None:
        """Save memes generated count to file"""
        try:
            os.makedirs(os.path.dirname(self.memes_generated_file), exist_ok=True)
            with open(self.memes_generated_file, "w") as f:
                json.dump(self.memes_generated, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving memes generated: {e}")

    async def create_meme(
        self, template_id: str, text0: str = "", text1: str = "", font: str = "impact"
    ) -> Optional[str]:
        """
        Create a meme using Imgflip API

        Args:
            template_id: Imgflip template ID
            text0: Top text
            text1: Bottom text
            font: Font name (impact, arial)

        Returns:
            URL of generated meme or None on error
        """
        if not IMGFLIP_USERNAME or not IMGFLIP_PASSWORD:
            logger.error("Imgflip credentials not configured")
            return None

        try:
            url = "https://api.imgflip.com/caption_image"
            payload = {
                "template_id": template_id,
                "username": IMGFLIP_USERNAME,
                "password": IMGFLIP_PASSWORD,
                "text0": text0,
                "text1": text1,
                "font": font,
            }

            async with self.session.post(url, data=payload) as response:
                if response.status != 200:
                    logger.error(f"Imgflip API returned {response.status}")
                    return None

                data = await response.json()
                if not data.get("success"):
                    error_msg = data.get("error_message", "Unknown error")
                    logger.error(f"Meme creation failed: {error_msg}")
                    return None

                meme_url = data.get("data", {}).get("url")
                logger.info(f"Meme created successfully: {meme_url}")
                return meme_url

        except Exception as e:
            logger.error(f"Error creating meme: {e}")
            return None

    async def create_meme_advanced(self, template_id: str, text_params: dict, font: str = "impact") -> Optional[str]:
        """
        Create a meme with multiple text boxes using Imgflip API

        Args:
            template_id: Imgflip template ID
            text_params: Dictionary with text0, text1, text2, etc.
            font: Font name (impact, arial)

        Returns:
            URL of generated meme or None on error
        """
        if not IMGFLIP_USERNAME or not IMGFLIP_PASSWORD:
            logger.error("Imgflip credentials not configured")
            return None

        try:
            url = "https://api.imgflip.com/caption_image"
            # Build form data using boxes[] array notation for better compatibility
            form_data = aiohttp.FormData()
            form_data.add_field("template_id", str(template_id))
            form_data.add_field("username", IMGFLIP_USERNAME)
            form_data.add_field("password", IMGFLIP_PASSWORD)

            # Add text boxes using boxes[N][text] notation
            for i, (key, value) in enumerate(sorted(text_params.items())):
                form_data.add_field(f"boxes[{i}][text]", value)

            logger.info(
                f"Sending to Imgflip API: template_id={template_id}, boxes={len(text_params)}, params={text_params}"
            )

            async with self.session.post(url, data=form_data) as response:
                if response.status != 200:
                    logger.error(f"Imgflip API returned {response.status}")
                    return None

                data = await response.json()
                if not data.get("success"):
                    error_msg = data.get("error_message", "Unknown error")
                    logger.error(f"Meme creation failed: {error_msg}")
                    return None

                meme_url = data.get("data", {}).get("url")
                logger.info(f"Meme created successfully: {meme_url}")
                return meme_url

        except Exception as e:
            logger.error(f"Error creating meme: {e}")
            return None

    def get_popular_templates(self, limit: int = 100) -> List[dict]:
        """Get the most popular meme templates"""
        return self.templates[:limit]

    def search_templates(self, query: str, limit: int = 25) -> List[dict]:
        """Search templates by name"""
        query_lower = query.lower()
        results = [template for template in self.templates if query_lower in template.get("name", "").lower()]
        return results[:limit]

    async def template_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for meme templates"""
        # Check if credentials are configured
        if not IMGFLIP_USERNAME or not IMGFLIP_PASSWORD:
            return [
                app_commands.Choice(name="⚠️ Imgflip credentials not configured - contact admin", value="not_configured")
            ]

        # Ensure templates are loaded
        if not self.templates:
            await self.fetch_templates()

        if not self.templates:
            return [app_commands.Choice(name="❌ No templates available - try !refreshtemplates", value="no_templates")]

        if not current:
            # Show top 25 popular templates if no search query
            templates = self.get_popular_templates(25)
        else:
            # Search templates
            templates = self.search_templates(current, 25)

        choices = []
        for template in templates:
            name = template.get("name", "Unknown")
            template_id = template.get("id", "")
            # Discord limit: 100 chars for choice name
            display_name = name[:97] + "..." if len(name) > 100 else name
            choices.append(app_commands.Choice(name=display_name, value=str(template_id)))

        return choices[:25]  # Discord limit: 25 choices

    @app_commands.command(name="creatememe", description="🎨 Create a custom meme using popular templates")
    @app_commands.describe(template="Choose a meme template (optional - opens GUI if not provided)")
    @app_commands.autocomplete(template=template_autocomplete)
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    async def create_meme_slash(
        self,
        interaction: discord.Interaction,
        template: str = None,
    ):
        """Slash command to create a custom meme"""
        # Check if credentials are configured
        if not IMGFLIP_USERNAME or not IMGFLIP_PASSWORD:
            await interaction.response.send_message(
                "❌ **Meme Generator Not Configured**\n\n"
                "The bot administrator needs to:\n"
                "1. Create a free account at https://imgflip.com/signup\n"
                "2. Add credentials to `.env` file:\n"
                "```\n"
                "IMGFLIP_USERNAME=your_username\n"
                "IMGFLIP_PASSWORD=your_password\n"
                "```\n"
                "3. Restart the bot",
                ephemeral=True,
            )
            return

        # Ensure templates are loaded
        if not self.templates:
            await interaction.response.defer(ephemeral=True)
            await self.fetch_templates()
            if not self.templates:
                await interaction.followup.send("❌ Failed to load templates. Please try again later.", ephemeral=True)
                return

        # If no template provided, show GUI
        if template is None:
            view = MemeGeneratorHubView(self)
            embed = view.get_template_embed()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            logger.info(f"Meme Generator Hub opened by {interaction.user}")
            return

        # Validate template selection
        if template in ["not_configured", "no_templates"]:
            await interaction.response.send_message("❌ Please select a valid meme template!", ephemeral=True)
            return

        # Get template info
        template_info = next((t for t in self.templates if str(t.get("id")) == template), None)

        if not template_info:
            await interaction.response.send_message("❌ Template not found. Please try again!", ephemeral=True)
            return

        # Open modal with dynamic text fields
        modal = MemeTextModal(self, template_info)
        await interaction.response.send_modal(modal)

    # @app_commands.command(name="memetemplates", description="🎨 Browse popular meme templates")
    # @app_commands.guilds(discord.Object(id=get_guild_id()))
    # async def meme_templates_slash(self, interaction: discord.Interaction):
    #     """Show popular meme templates"""
    #     await interaction.response.defer(ephemeral=True)
    #
    #     # Ensure templates are loaded
    #     if not self.templates:
    #         await self.fetch_templates()
    #
    #     if not self.templates:
    #         await interaction.followup.send("❌ No templates available. Please try again later.", ephemeral=True)
    #         return
    #
    #     # Show top 10 templates
    #     popular = self.get_popular_templates(10)
    #
    #     embed = discord.Embed(
    #         title="🎨 Popular Meme Templates",
    #         description="Use `/creatememe` to create a custom meme with these templates!",
    #         color=Config.PINK,
    #     )
    #
    #     for i, template in enumerate(popular, 1):
    #         name = template.get("name", "Unknown")
    #         template_id = template.get("id", "")
    #         box_count = template.get("box_count", 0)
    #
    #         embed.add_field(name=f"{i}. {name}", value=f"ID: `{template_id}` • Text boxes: {box_count}", inline=False)
    #
    #     embed.set_footer(text=f"Total templates available: {len(self.templates)}")
    #
    #     await interaction.followup.send(embed=embed, ephemeral=True)

    async def show_meme_generator_hub(self, interaction: discord.Interaction, post_to_channel_id: int = None):
        """
        Show the Meme Generator Hub (can be called from other cogs)

        Args:
            interaction: The interaction that triggered this
            post_to_channel_id: If set, memes will be posted to this channel instead of current channel
        """
        # Check if credentials are configured
        if not IMGFLIP_USERNAME or not IMGFLIP_PASSWORD:
            await interaction.response.send_message(
                "❌ **Meme Generator Not Configured**\n\nThe bot administrator needs to configure Imgflip credentials.",
                ephemeral=True,
            )
            return

        # Ensure templates are loaded
        if not self.templates:
            await interaction.response.defer(ephemeral=True)
            await self.fetch_templates()
            if not self.templates:
                await interaction.followup.send("❌ Failed to load templates. Please try again later.", ephemeral=True)
                return

            # Show GUI after loading
            view = MemeGeneratorHubView(self, post_to_channel_id=post_to_channel_id)
            embed = view.get_template_embed()
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            # Templates already loaded, show GUI directly
            view = MemeGeneratorHubView(self, post_to_channel_id=post_to_channel_id)
            embed = view.get_template_embed()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        logger.info(f"Meme Generator Hub opened by {interaction.user} (channel context: {post_to_channel_id})")

    @commands.command(name="refreshtemplates")
    @commands.has_permissions(administrator=True)
    async def refresh_templates(self, ctx: commands.Context):
        """
        🔄 Refresh meme templates from Imgflip (Admin only)
        Usage: !refreshtemplates
        """
        await ctx.send("🔄 Refreshing meme templates...")

        templates = await self.fetch_templates(force=True)

        if templates:
            await ctx.send(f"✅ Successfully fetched {len(templates)} templates!")
        else:
            await ctx.send("❌ Failed to fetch templates.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MemeGenerator(bot))
