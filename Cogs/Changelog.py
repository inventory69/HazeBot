import discord
from discord.ext import commands
import openai
import os
from datetime import datetime
from Utils.Logger import Logger
from Config import PINK
from Utils.EmbedUtils import set_pink_footer

ROLE_ID_CHANGELOG = 1426314743278473307  # Changelog Notifications Role ID
CHANNEL_ID_CHANGELOG = 1424859282284871752  # Ziel-Channel-ID

class ChangelogCog(commands.Cog):
    """
    📝 Changelog Cog: Generates Discord-Markdown changelogs from PR text using GPT-4 Turbo.
    """

    def __init__(self, bot):
        self.bot = bot
        openai.api_key = os.getenv("OPENAI_API_KEY")

    async def generate_changelog_title(self, text: str) -> str:
        """
        Generate a concise title from PR text using OpenAI GPT-4 Turbo.
        """
        if not openai.api_key:
            raise ValueError("OpenAI API key not configured.")

        prompt = f"Generate a concise, catchy title for this PR changelog based on the text. Keep it under 10 words.\n\nPR Text:\n{text}"

        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.7
        )
        return response.choices[0].message.content.strip().strip('"').strip("'")

    async def generate_changelog_text(self, text: str, project: str, author: str) -> str:
        """
        Generate changelog text using OpenAI GPT-4 Turbo.
        """
        if not openai.api_key:
            raise ValueError("OpenAI API key not configured.")

        prompt = f"""
Format the following PR text as a compact Discord-Markdown changelog.
- Do NOT repeat the title in the text.
- Directly below the title, add these lines (with Discord markdown):
  **Project:** `{project}`
  **Author:** `{author}`
- After a blank line, list the changes as bullet points. Each change must start with a small bullet point (•), then an emoji, then a short description.
- Format file names, command names, variables, and settings in backticks (`).
- Do not add a summary or extra text at the end.
- Do not use paragraphs. Only use bullet points as shown below.

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
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.5
        )
        return response.choices[0].message.content.strip()

    def create_changelog_embed(self, changelog: str, title: str, date: str, project: str, author: str) -> discord.Embed:
        embed = discord.Embed(
            title=f"🆕 {title} – {date}",
            description=changelog + "\n\u200b",  # Fügt einen kleinen Abstand vor dem Footer hinzu
            color=PINK
        )
        set_pink_footer(embed, bot=self.bot.user)
        return embed

    @commands.command(name="changelog")
    @commands.has_permissions(administrator=True)
    async def changelog_prefix(self, ctx, *, args: str):
        """
        📝 Generate a changelog from PR text. (Admin only)
        Usage: !changelog title:"Title" date:"2025-10-13" project:"HazeWorldBot" author:"inventory69" text:PR text here
        If title is omitted, it will be generated from the PR text. Date defaults to today.
        """
        params = {}
        for part in args.split(' '):
            if ':' in part:
                key, value = part.split(':', 1)
                params[key] = value

        text = params.get('text', args)
        project = params.get('project', 'HazeWorldBot')
        author = params.get('author', 'inventory69')

        # Generate title if not provided
        if 'title' not in params:
            try:
                title = await self.generate_changelog_title(text)
            except Exception as e:
                Logger.error(f"Error generating title: {e}")
                title = 'Bot Update'
        else:
            title = params['title']

        # Use today's date if not provided
        date = params.get('date', datetime.now().strftime("%Y-%m-%d"))

        try:
            changelog = await self.generate_changelog_text(text, project, author)
            embed = self.create_changelog_embed(changelog, title, date, project, author)
            view = ChangelogChannelView(embed)
            await ctx.send(embed=embed, view=view)
        except Exception as e:
            Logger.error(f"Error generating changelog: {e}")
            await ctx.send("❌ Failed to generate changelog. Check logs.")

# --- Button & Channel Select View ---
class ChangelogChannelView(discord.ui.View):
    def __init__(self, embed):
        super().__init__(timeout=120)
        self.embed = embed

    @discord.ui.button(label="Post to Channel", style=discord.ButtonStyle.primary, emoji="📢")
    async def post_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.guild.get_channel(CHANNEL_ID_CHANGELOG)
        if channel:
            # Sende die Mention-Nachricht vor dem Embed
            await channel.send(f"Role Mention: <@&{ROLE_ID_CHANGELOG}> ...")
            await channel.send(embed=self.embed)
            await interaction.response.send_message(f"✅ Changelog posted to {channel.mention}.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Channel not found.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ChangelogCog(bot))