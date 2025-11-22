"""
Start HazeBot with API Server
Runs both the Discord bot and the Flask API in separate threads
"""

import logging
import sys
import threading
from pathlib import Path

# Setup logging first
logging.basicConfig(
    level=logging.INFO,
    format="[{asctime}] 🛈  INFO  │ {message}",
    datefmt="%H:%M:%S",
    style="{",
)
logging.getLogger("discord").handlers.clear()
logging.getLogger("discord").propagate = False
logging.getLogger("discord").setLevel(logging.ERROR)  # Suppress discord.py warnings

# Set root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)
root_logger.handlers.clear()

# Now imports
import asyncio
import difflib
import os
import pathlib

import discord
from discord.ext import commands
from dotenv import load_dotenv

import Config
from Config import (
    BOT_TOKEN,
    DATA_DIR,
    GUILD_ID,
    PROD_MODE,
    SLASH_COMMANDS,
    BotName,
    CommandPrefix,
    FuzzyMatchingThreshold,
    Intents,
    MessageCooldown,
    get_guild_id,
)
from Utils.ConfigLoader import load_config_from_file
from Utils.EmbedUtils import set_pink_footer
from Utils.Env import LoadEnv
from Utils.Logger import Logger

# Load environment
load_dotenv()
Token = BOT_TOKEN
EnvDict = LoadEnv()

# Load saved configuration overrides before starting the bot
print("🔄 Loading configuration from file...")
load_config_from_file()
print(f"🔍 After load: RL_RANK_CHECK_INTERVAL_HOURS = {Config.RL_RANK_CHECK_INTERVAL_HOURS}")

loaded_count = sum(1 for v in EnvDict.values() if v is not None)
Logger.info(f"🌍 Environment variables loaded: {loaded_count}/{len(list(EnvDict.keys()))}")


class HazeWorldBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix=CommandPrefix, intents=Intents)
        self.remove_command("help")
        self.UserCooldowns = {}

    async def setup_hook(self) -> None:
        Logger.info("🚀 Starting Cog loading sequence...")
        loaded_cogs = []

        # Load APIServer first (so API is available for other cogs)
        try:
            await self.load_extension("Cogs.APIServer")
            loaded_cogs.append("APIServer")
            Logger.info("   └─ ✅ Loaded: APIServer")
        except Exception as e:
            Logger.error(f"   └─ ❌ Failed to load APIServer: {e}")

        # Load CogManager second
        try:
            await self.load_extension("Cogs.CogManager")
            loaded_cogs.append("CogManager")
            Logger.info("   └─ ✅ Loaded: CogManager")
        except Exception as e:
            Logger.error(f"   └─ ❌ Failed to load CogManager: {e}")
            return

        # Load DiscordLogging third
        try:
            await self.load_extension("Cogs.DiscordLogging")
            loaded_cogs.append("DiscordLogging")
            Logger.info("   └─ ✅ Loaded: DiscordLogging")
        except Exception as e:
            Logger.error(f"   └─ ❌ Failed to load DiscordLogging: {e}")

        # Get disabled cogs
        cog_manager = self.get_cog("CogManager")
        disabled_cogs = cog_manager.get_disabled_cogs() if cog_manager else []

        # Load other cogs
        for cog in pathlib.Path("Cogs").glob("*.py"):
            if cog.name.startswith("_") or cog.stem in ["APIServer", "CogManager", "DiscordLogging"]:
                continue
            if cog.stem in disabled_cogs:
                Logger.info(f"   └─ ⏸️ Skipped (disabled): {cog.stem}")
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

        # List commands
        slash_commands = SLASH_COMMANDS
        Logger.info("📋 Available ! commands:")
        for cog_name, cog in self.cogs.items():
            for cmd in cog.get_commands():
                if not cmd.hidden:
                    slash_available = cmd.name in slash_commands
                    Logger.info(f"   └─ ! {cmd.name} (Cog: {cog_name}) {'(/ available)' if slash_available else ''}")

        # Sync commands
        self.tree.clear_commands(guild=None)
        guild = discord.Object(id=get_guild_id())
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        Logger.info(f"Synced commands: {[cmd.name for cmd in synced]}")
        Logger.info(f"🔗 Synced {len(synced)} guild slash commands.")
        Logger.info(f"🤖 HazeWorldBot starting in {'PRODUCTION' if PROD_MODE else 'TEST'} mode")
        Logger.info(f"📊 Using Guild ID: {GUILD_ID}")
        Logger.info(f"📁 Using Data Directory: {DATA_DIR}")

    async def on_ready(self) -> None:
        Logger.info(f"{BotName} is online as {self.user}!")

    async def on_command_completion(self, ctx: commands.Context) -> None:
        try:
            await ctx.message.delete()
        except Exception:
            pass

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Handle command errors with detailed responses."""
        if isinstance(error, commands.CommandNotFound):
            cmd_name = ctx.message.content.split()[0][len(CommandPrefix) :]
            all_cmds = [cmd.name for cog in self.cogs.values() for cmd in cog.get_commands() if not cmd.hidden]
            matches = difflib.get_close_matches(cmd_name, all_cmds, n=1, cutoff=FuzzyMatchingThreshold)
            if matches:
                embed = discord.Embed(
                    title="❓ Command not found",
                    description=f"Did you mean `!{matches[0]}`?",
                    color=discord.Color.orange(),
                )
                set_pink_footer(embed, bot=self.user)
                embed_message = await ctx.send(embed=embed)
                await asyncio.sleep(10)
                try:
                    await embed_message.delete()
                    await ctx.message.delete()
                except Exception:
                    pass
            else:
                embed = discord.Embed(
                    title="❓ Command not found",
                    description="Use `!help` for a list of commands.",
                    color=discord.Color.red(),
                )
                set_pink_footer(embed, bot=self.user)
                embed_message = await ctx.send(embed=embed)
                await asyncio.sleep(10)
                try:
                    await embed_message.delete()
                    await ctx.message.delete()
                except Exception:
                    pass
        elif isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="🚫 Missing Permissions",
                description="You don't have the required permissions to use this command.",
                color=discord.Color.red(),
            )
            set_pink_footer(embed, bot=self.user)
            embed_message = await ctx.send(embed=embed)
            await asyncio.sleep(5)
            try:
                await embed_message.delete()
                await ctx.message.delete()
            except Exception:
                pass
        elif isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                title="⚠️ Bad Argument",
                description="Invalid argument provided. Check the command usage.",
                color=discord.Color.yellow(),
            )
            set_pink_footer(embed, bot=self.user)
            embed_message = await ctx.send(embed=embed)
            await asyncio.sleep(5)
            try:
                await embed_message.delete()
                await ctx.message.delete()
            except Exception:
                pass
        elif isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏳ Command on Cooldown",
                description=f"This command is on cooldown. Try again in {error.retry_after:.1f} seconds.",
                color=discord.Color.blue(),
            )
            set_pink_footer(embed, bot=self.user)
            embed_message = await ctx.send(embed=embed)
            await asyncio.sleep(5)
            try:
                await embed_message.delete()
                await ctx.message.delete()
            except Exception:
                pass
        else:
            Logger.error(f"Unhandled command error: {error}")
            embed = discord.Embed(
                title="💥 An error occurred",
                description="Something went wrong. Please try again later.",
                color=discord.Color.red(),
            )
            set_pink_footer(embed, bot=self.user)
            embed_message = await ctx.send(embed=embed)
            await asyncio.sleep(5)
            try:
                await embed_message.delete()
                await ctx.message.delete()
            except Exception:
                pass

    async def on_message(self, message: discord.Message) -> None:
        """Handle messages with cooldowns."""
        if message.author.bot:
            return

        now = message.created_at.timestamp()
        is_admin_command = message.content.startswith("!") and any(
            cmd in message.content.lower() for cmd in ["load", "unload", "reload", "listcogs"]
        )

        if not is_admin_command:
            if message.author.id in self.UserCooldowns:
                if now - self.UserCooldowns[message.author.id] < MessageCooldown:
                    return
            self.UserCooldowns[message.author.id] = now

        await self.process_commands(message)

    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """Log message edits."""
        if before.author.bot or before.content == after.content:
            return
        Logger.info(f"✏️ Message edited by {before.author} in {before.channel}: '{before.content}' -> '{after.content}'")

    async def on_message_delete(self, message: discord.Message) -> None:
        """Log message deletions."""
        if message.author.bot:
            return
        Logger.info(f"🗑️ Message deleted by {message.author} in {message.channel}: '{message.content}'")


def main():
    """Main entry point"""
    # Create bot instance
    bot = HazeWorldBot()

    # API will be started by the APIServer cog
    Logger.info("🤖 Starting Discord bot (API will start via APIServer cog)...")
    bot.run(Token)


if __name__ == "__main__":
    main()
