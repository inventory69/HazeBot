# 📦 Built-in modules
import random
import asyncio

# 👾 Discord modules
from discord.ext import commands, tasks
import discord

# ⚙️ Settings
from Config import PresenceUpdateInterval  # Assuming you add this to Config.py

# 📥 Custom modules
from Utils.Logger import Logger

class Presence(commands.Cog):
    """
    🎮 Presence Cog: Updates bot presence with dynamic, fun messages related to "inventory".
    """

    def __init__(self, bot):
        self.bot = bot
        self.presence_messages = [
            "🗂️ Organizing Inventory",
            "💎 Counting Rare Items",
            "🏆 Managing Epic Loot",
            "✨ Sorting Artifacts",
            "🌟 Inventory Wonders",
            "🔍 Hunting Treasures",
            "⚔️ Upgrading Gear",
            "🚀 Inventory Activated",
            "🎉 Rare Finds",
            "🔥 Epic Drops"
        ]
        self.emojis = ["🗂️", "💎", "🏆", "✨", "🌟", "🔍", "⚔️", "🚀", "🎉", "🔥"]
        self.update_presence.start()

    @tasks.loop(seconds=PresenceUpdateInterval)  # Update every configured interval
    async def update_presence(self):
        if not self.bot.is_ready():
            return
        try:
            # Pick random message and replace placeholder
            message = random.choice(self.presence_messages)
            emoji = random.choice(self.emojis)
            message = message.format(random_emoji=emoji)
            
            # Set presence
            activity = discord.Game(name=message)
            await self.bot.change_presence(activity=activity, status=discord.Status.online)
            Logger.info(f"🎮 Presence updated: {message}")
        except Exception as e:
            Logger.error(f"Error updating presence: {e}")

    @update_presence.before_loop
    async def before_update_presence(self):
        await self.bot.wait_until_ready()

    def cog_unload(self):
        self.update_presence.cancel()

async def setup(bot):
    """
    Setup function to add the Presence cog.
    """
    await bot.add_cog(Presence(bot))