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
import discord
from discord.ext import commands
from Config import CommandPrefix, Intents, BotName, SLASH_COMMANDS, FuzzyMatchingThreshold, MessageCooldown
from Utils.Logger import Logger
from dotenv import load_dotenv
from Utils.Env import LoadEnv
import difflib  # For fuzzy matching

load_dotenv()
Token = os.getenv("DISCORD_BOT_TOKEN")
EnvDict = LoadEnv()

# Now log the summary, since Logger is initialized
loaded_count = sum(1 for v in EnvDict.values() if v is not None)
Logger.info(f"🌍 Environment variables loaded: {loaded_count}/{len(list(EnvDict.keys()))}")

class HazeWorldBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=CommandPrefix, intents=Intents)
        self.remove_command('help')
        self.UserCooldowns = {}  # For message cooldowns

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
        # List available ! commands and their slash availability
        slash_commands = SLASH_COMMANDS  # List of commands with slash versions
        Logger.info("📋 Available ! commands:")
        for cog_name, cog in self.cogs.items():
            for cmd in cog.get_commands():
                if not cmd.hidden:
                    slash_available = cmd.name in slash_commands
                    Logger.info(f"   └─ ! {cmd.name} (Cog: {cog_name}) {'(/ available)' if slash_available else ''}")
        # Clear global commands to prevent duplicates
        self.tree.clear_commands(guild=None)
        # Copy global commands to guild and sync
        guild = discord.Object(id=int(os.getenv("DISCORD_GUILD_ID")))
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        Logger.info(f"Synced commands: {[cmd.name for cmd in synced]}")
        Logger.info(f"🔗 Synced {len(synced)} guild slash commands.")

    async def on_ready(self):
        Logger.info(f'{BotName} is online as {self.user}!')

    async def on_command_completion(self, ctx):
        # Löscht die eingegebene Nachricht nach jedem Command
        try:
            await ctx.message.delete()
        except Exception:
            pass  # Ignoriere Fehler, z.B. fehlende Rechte

    async def on_command_error(self, ctx, error):
        """Handle command errors with detailed responses."""
        if isinstance(error, commands.CommandNotFound):
            # Fuzzy matching for unknown commands
            cmd_name = ctx.message.content.split()[0][len(CommandPrefix):]
            all_cmds = [cmd.name for cmd in self.commands if not cmd.hidden]
            matches = difflib.get_close_matches(cmd_name, all_cmds, n=1, cutoff=FuzzyMatchingThreshold)
            if matches:
                embed = discord.Embed(
                    title="❓ Command not found",
                    description=f"Did you mean `!{matches[0]}`?",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed, delete_after=10)
            else:
                embed = discord.Embed(
                    title="❓ Command not found",
                    description="Use `!help` for a list of commands.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed, delete_after=10)
        elif isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="🚫 Missing Permissions",
                description="You don't have the required permissions to use this command.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, delete_after=5)
        elif isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                title="⚠️ Bad Argument",
                description="Invalid argument provided. Check the command usage.",
                color=discord.Color.yellow()
            )
            await ctx.send(embed=embed, delete_after=5)
        elif isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏳ Command on Cooldown",
                description=f"This command is on cooldown. Try again in {error.retry_after:.1f} seconds.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed, delete_after=5)
        else:
            Logger.error(f"Unhandled command error: {error}")
            embed = discord.Embed(
                title="💥 An error occurred",
                description="Something went wrong. Please try again later.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, delete_after=5)

    async def on_message(self, message):
        """Handle messages with cooldowns."""
        if message.author.bot:
            return

        # Check message cooldown
        now = message.created_at.timestamp()
        if message.author.id in self.UserCooldowns:
            if now - self.UserCooldowns[message.author.id] < MessageCooldown:
                return  # Ignore message if on cooldown
        self.UserCooldowns[message.author.id] = now

        await self.process_commands(message)

    async def on_message_edit(self, before, after):
        """Log message edits."""
        if before.author.bot or before.content == after.content:
            return
        Logger.info(f"✏️ Message edited by {before.author} in {before.channel}: '{before.content}' -> '{after.content}'")

    async def on_message_delete(self, message):
        """Log message deletions."""
        if message.author.bot:
            return
        Logger.info(f"🗑️ Message deleted by {message.author} in {message.channel}: '{message.content}'")

bot = HazeWorldBot()
bot.run(Token)