import logging

logging.basicConfig(
    level=logging.INFO,
    format='[{asctime}] 🛈  INFO  │ {message}',
    datefmt='%H:%M:%S',
    style='{'
)
logging.getLogger("discord").handlers.clear()
logging.getLogger("discord").propagate = False

# Setze Root-Logger auf WARNING und entferne alle Handler
root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)
root_logger.handlers.clear()

# Jetzt erst die restlichen Imports!
import os
import pathlib
from discord.ext import commands
from Config import CommandPrefix, Intents, BotName
from Utils.Logger import Logger
from dotenv import load_dotenv

load_dotenv()
Token = os.getenv("DISCORD_BOT_TOKEN")

class HazeWorldBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=CommandPrefix, intents=Intents)
        self.remove_command('help')

    async def setup_hook(self):
        Logger.info("🚀 Starting Cog loading sequence...")
        loaded_cogs = []
        for cog in pathlib.Path("Cogs").glob("*.py"):
            if cog.name.startswith("_"):
                continue
            try:
                await self.load_extension(f"Cogs.{cog.stem}")
                loaded_cogs.append(cog.stem)
                Logger.info(f"   └─ ✅ Loaded: {cog.stem}")
            except Exception as e:
                Logger.error(f"   └─ ❌ Failed to load {cog.stem}: {e}")
        if loaded_cogs:
            Logger.info(f"🧩 All Cogs loaded: {', '.join(loaded_cogs)}")
        else:
            Logger.warning("⚠️ No Cogs loaded!")
        Logger.info("🎯 Cog loading sequence complete.")

    async def on_ready(self):
        Logger.info(f'{BotName} is online as {self.user}!')

    async def on_command_completion(self, ctx):
        # Löscht die eingegebene Nachricht nach jedem Command
        try:
            await ctx.message.delete()
        except Exception:
            pass  # Ignoriere Fehler, z.B. fehlende Rechte

bot = HazeWorldBot()
bot.run(Token)