import discord
from discord.ext import commands
import json
import os
import logging

logger = logging.getLogger(__name__)

class CogManager(commands.Cog):
    """Cog Manager: Load, unload, and reload cogs with persistent states"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.disabled_cogs_file = "TestData/disabled_cogs.json" if os.getenv("PROD_MODE", "false").lower() == "false" else "Data/disabled_cogs.json"
        self.ensure_disabled_cogs_file()
        # Ensure CogManager is never disabled
        self.enable_cog("cogmanager")

    def ensure_disabled_cogs_file(self):
        """Ensure the disabled cogs file exists"""
        os.makedirs(os.path.dirname(self.disabled_cogs_file), exist_ok=True)
        if not os.path.exists(self.disabled_cogs_file):
            with open(self.disabled_cogs_file, 'w') as f:
                json.dump([], f)

    def get_disabled_cogs(self) -> list:
        """Get list of disabled cogs"""
        try:
            with open(self.disabled_cogs_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_disabled_cogs(self, disabled_cogs: list):
        """Save list of disabled cogs"""
        with open(self.disabled_cogs_file, 'w') as f:
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

    @commands.command(name="load")
    @commands.has_permissions(administrator=True)
    async def load_cog(self, ctx: commands.Context, cog_name: str):
        """Load a cog"""
        try:
            await self.bot.load_extension(f"Cogs.{cog_name}")
            self.enable_cog(cog_name)
            await ctx.send(f"✅ Cog `{cog_name}` loaded successfully!")
            logger.info(f"Cog {cog_name} loaded by {ctx.author}")
        except Exception as e:
            await ctx.send(f"❌ Failed to load cog `{cog_name}`: {e}")
            logger.error(f"Failed to load cog {cog_name}: {e}")

    @commands.command(name="unload")
    @commands.has_permissions(administrator=True)
    async def unload_cog(self, ctx: commands.Context, cog_name: str):
        """Unload a cog"""
        if cog_name.lower() == "cogmanager":
            await ctx.send("❌ Cannot unload CogManager - it's required for cog management!")
            return
            
        try:
            await self.bot.unload_extension(f"Cogs.{cog_name}")
            self.disable_cog(cog_name)
            await ctx.send(f"✅ Cog `{cog_name}` unloaded successfully!")
            logger.info(f"Cog {cog_name} unloaded by {ctx.author}")
        except Exception as e:
            await ctx.send(f"❌ Failed to unload cog `{cog_name}`: {e}")
            logger.error(f"Failed to unload cog {cog_name}: {e}")

    @commands.command(name="reload")
    @commands.has_permissions(administrator=True)
    async def reload_cog(self, ctx: commands.Context, cog_name: str):
        """Reload a cog"""
        try:
            await self.bot.unload_extension(f"Cogs.{cog_name}")
            await self.bot.load_extension(f"Cogs.{cog_name}")
            # Don't change disabled state on reload
            await ctx.send(f"✅ Cog `{cog_name}` reloaded successfully!")
            logger.info(f"Cog {cog_name} reloaded by {ctx.author}")
        except Exception as e:
            await ctx.send(f"❌ Failed to reload cog `{cog_name}`: {e}")
            logger.error(f"Failed to reload cog {cog_name}: {e}")

    @commands.command(name="listcogs")
    @commands.has_permissions(administrator=True)
    async def list_cogs(self, ctx: commands.Context):
        """List all cogs and their status"""
        disabled = self.get_disabled_cogs()
        loaded = [cog for cog in self.bot.cogs.keys()]

        embed = discord.Embed(title="🔧 Cog Status", color=0x00ff00)

        # Loaded cogs
        loaded_text = "\n".join([f"✅ {cog}" for cog in loaded]) or "None"
        embed.add_field(name="Loaded Cogs", value=loaded_text, inline=False)

        # Disabled cogs
        disabled_text = "\n".join([f"❌ {cog}" for cog in disabled]) or "None"
        embed.add_field(name="Disabled Cogs", value=disabled_text, inline=False)

        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(CogManager(bot))