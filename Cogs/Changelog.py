import logging
import os
from datetime import datetime

import discord
import openai
from discord.ext import commands

import Config
from Config import CHANGELOG_CHANNEL_ID, CHANGELOG_ROLE_ID
from Utils.EmbedUtils import set_pink_footer

logger = logging.getLogger(__name__)


class ChangelogCog(commands.Cog):
    """
    📝 Changelog Cog: Generates Discord-Markdown changelogs from PR text using GPT-4.1-nano.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        openai.api_key = os.getenv("OPENAI_API_KEY")

    async def generate_changelog_title(self, text: str) -> str:
        """
        Generate a concise title from PR text using OpenAI GPT-4.1-nano.
        """
        if not openai.api_key:
            raise ValueError("OpenAI API key not configured.")

        prompt = f"Generate a concise, catchy title for this PR changelog based on the text. Keep it under 10 words.\n\nPR Text:\n{text}"

        response = openai.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip().strip('"').strip("'")

    async def generate_changelog_text(self, text: str, project: str, author: str) -> str:
        """
        Generate changelog text using OpenAI GPT-4.1-nano.
        """
        if not openai.api_key:
            raise ValueError("OpenAI API key not configured.")

        prompt = f"""
Format the following PR text as a compact Discord-Markdown changelog.
- Do NOT repeat the title in the text.
- Directly below the title, add these lines (with Discord markdown):
  **Project:** `{project}`
  **Author:** `{author}`
- After a blank line, list the changes as bullet points. Each change must start with a small bullet point (•), then EXACTLY ONE emoji, then a short description.
- IMPORTANT: Use ONLY ONE emoji per line, never multiple emojis.
- Format file names, command names, variables, and settings in backticks (`).
- Do not add a summary or extra text at the end.
- Do not use paragraphs. Only use bullet points as shown below.
- If the input already contains emojis in the bullet points, keep them as-is and do not add additional emojis.

Example:
**Project:** `HazeWorldBot`
**Author:** `inventory69`

• 🎮 Added dynamic Presence cog with hourly inventory-themed status updates
• 🌍 Introduced `Env.py` for environment variable loading and validation with logging
• 🎨 Replaced legacy logging with Rich-based Logger (emojis, regex highlights, pastel themes, tracebacks)
• 🛠️ Enhanced `Main.py` with fuzzy command matching, cooldowns, error handling, and edit/delete logging
• 📁 Organized JSON files into `Data/` folder (`rl_accounts.json`, `tickets.json`, `persistent_views.json`)
• ⚙️ Updated `Config.py` with new settings: `PresenceUpdateInterval`, `FuzzyMatchingThreshold`, `MessageCooldown`, `LogLevel`
• 📦 Added `rich` to `requirements.txt`
• 🔧 Improved JSON persistence with automatic directory creation
• 📊 Better command syncing, cog loading logs, and user feedback

PR-Text:
{text}
"""

        response = openai.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()

    def create_changelog_embed(self, changelog: str, title: str, date: str, project: str, author: str) -> discord.Embed:
        embed = discord.Embed(
            title=f"🆕 {title} – {date}",
            description=changelog + "\n\u200b",  # Adds a small space before the footer
            color=Config.PINK,
        )
        set_pink_footer(embed, bot=self.bot.user)
        return embed

    @commands.command(name="update_changelog_view")
    @commands.has_permissions(administrator=True)
    async def update_changelog_view(self, ctx: commands.Context, message_id: int) -> None:
        """
        🔄 Update an existing changelog message to add the edit button.
        Usage: !update_changelog_view <message_id>
        """
        try:
            message = await ctx.channel.fetch_message(message_id)
            if not message.embeds:
                await ctx.send("❌ Message has no embed.")
                return

            embed = message.embeds[0]
            view = ChangelogChannelView(embed)
            await message.edit(view=view)
            await ctx.send(f"✅ Updated message {message_id} with new view.", ephemeral=True)
            logger.info(f"Updated changelog message {message_id} with edit button")
        except discord.NotFound:
            await ctx.send("❌ Message not found.")
        except Exception as e:
            logger.error(f"Error updating changelog view: {e}")
            await ctx.send(f"❌ Error updating message: {e}")

    @commands.command(name="changelog")
    @commands.has_permissions(administrator=True)
    async def changelog_prefix(self, ctx: commands.Context, *, args: str) -> None:
        """
        📝 Generate a changelog from PR text. (Admin only)
        Usage: !changelog title:"Title" date:"2025-10-13" project:"HazeWorldBot" author:"inventory69" --text PR text here
        If title is omitted, it will be generated from the PR text. Date defaults to today.
        """
        params = {}

        # Better parsing: Look for --text flag
        if "--text" in args:
            parts = args.split("--text", 1)
            text = parts[1].strip() if len(parts) > 1 else args
            # Parse other params from the first part
            for part in parts[0].split():
                if ":" in part:
                    key, value = part.split(":", 1)
                    params[key.strip()] = value.strip().strip('"').strip("'")
        else:
            # Old parsing for backward compatibility
            text = args
            for part in args.split():
                if ":" in part:
                    key, value = part.split(":", 1)
                    params[key.strip()] = value.strip().strip('"').strip("'")

        project = params.get("project", "HazeWorldBot")
        author = params.get("author", "inventory69")

        # Generate title if not provided
        if "title" not in params:
            try:
                logger.info("Generating title from text...")
                title = await self.generate_changelog_title(text)
            except Exception as e:
                logger.error(f"Error generating title: {e}")
                title = "Bot Update"
        else:
            title = params["title"]

        # Use today's date if not provided
        date = params.get("date", datetime.now().strftime("%Y-%m-%d"))

        logger.info(f"Generating changelog with title='{title}', project='{project}', author='{author}'")
        logger.info(f"Text preview: {text[:100]}...")

        try:
            changelog = await self.generate_changelog_text(text, project, author)
            logger.info("Changelog generated, creating embed...")
            embed = self.create_changelog_embed(changelog, title, date, project, author)
            view = ChangelogChannelView(embed)
            logger.info("Sending changelog embed to channel...")
            await ctx.send(embed=embed, view=view)
            logger.info("Changelog embed sent successfully")
        except Exception as e:
            logger.error(f"Error generating changelog: {e}")
            await ctx.send("❌ Failed to generate changelog. Check logs.")


# --- Edit Modal ---
class ChangelogEditModal(discord.ui.Modal, title="Edit Changelog"):
    def __init__(self, view: "ChangelogChannelView") -> None:
        super().__init__()
        self.view = view

        # Extract current values from embed
        current_title = view.embed.title or ""
        current_description = view.embed.description or ""

        # Title input (without the date part for easier editing)
        title_without_prefix = current_title.replace("🆕 ", "")
        if " – " in title_without_prefix:
            title_part = title_without_prefix.split(" – ")[0]
            date_part = title_without_prefix.split(" – ")[1]
        else:
            title_part = title_without_prefix
            date_part = datetime.now().strftime("%Y-%m-%d")

        self.title_input = discord.ui.TextInput(
            label="Title",
            placeholder="e.g. Feature Update",
            default=title_part,
            max_length=100,
            required=True,
        )

        self.date_input = discord.ui.TextInput(
            label="Date (YYYY-MM-DD)",
            placeholder="e.g. 2025-10-31",
            default=date_part,
            max_length=10,
            required=True,
        )

        self.description_input = discord.ui.TextInput(
            label="Changelog Text",
            placeholder="Enter changes here...",
            default=current_description.replace("\n\u200b", ""),
            style=discord.TextStyle.paragraph,
            max_length=4000,
            required=True,
        )

        self.add_item(self.title_input)
        self.add_item(self.date_input)
        self.add_item(self.description_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Update the embed with new values
        new_title = f"🆕 {self.title_input.value} – {self.date_input.value}"
        new_description = self.description_input.value + "\n\u200b"

        self.view.embed.title = new_title
        self.view.embed.description = new_description

        # Update the message with the new embed
        await interaction.response.edit_message(embed=self.view.embed, view=self.view)
        await interaction.followup.send("✅ Changelog updated successfully!", ephemeral=True)


# --- Button & Channel Select View ---
class ChangelogChannelView(discord.ui.View):
    def __init__(self, embed: discord.Embed) -> None:
        super().__init__(timeout=120)
        self.embed = embed

    @discord.ui.button(label="Post to Channel", style=discord.ButtonStyle.primary, emoji="📢")
    async def post_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        channel = interaction.guild.get_channel(CHANGELOG_CHANNEL_ID)
        if channel:
            # Send the mention message before the embed
            await channel.send(f"Role Mention: <@&{CHANGELOG_ROLE_ID}> ...")
            await channel.send(embed=self.embed)
            await interaction.response.send_message(f"✅ Changelog posted to {channel.mention}.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Channel not found.", ephemeral=True)

    @discord.ui.button(label="Edit Manually", style=discord.ButtonStyle.secondary, emoji="✏️")
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        modal = ChangelogEditModal(self)
        await interaction.response.send_modal(modal)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ChangelogCog(bot))
