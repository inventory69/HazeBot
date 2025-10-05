import logging
from rich.logging import RichHandler
from rich.console import Console
from rich.theme import Theme
from discord.ext import commands
import discord

# Pink Theme für RichHandler
pink_theme = Theme({
    "info": "bold magenta",
    "warning": "bold bright_magenta",
    "error": "bold red",
    "critical": "bold white on magenta"
})

console = Console(theme=pink_theme)
ConsoleHandler = RichHandler(console=console)

logging.getLogger().setLevel(logging.WARNING)  # Root-Logger gibt nur Warnungen und Fehler aus

class DiscordEmojiFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(datefmt="%H:%M:%S")

    def format(self, record):
        emoji = "💖" if record.levelno == logging.INFO else "🌸" if record.levelno == logging.WARNING else "🩷" if record.levelno == logging.ERROR else "🚨"
        # Level-Namen bleiben wie im Original
        level = "DC DEBUG" if record.levelno == logging.DEBUG else "DC INFO" if record.levelno == logging.INFO else "DC WARN" if record.levelno == logging.WARNING else "DC ERROR" if record.levelno == logging.ERROR else "DC CRIT"
        time_str = self.formatTime(record, self.datefmt)
        return f"[{time_str}] {emoji}  {level:<7} │ {record.getMessage()}"

# Entferne alle Handler vom Root-Logger
root_logger = logging.getLogger()
root_logger.handlers.clear()

logging.basicConfig(level=logging.INFO, handlers=[ConsoleHandler], force=True)

# Discord-Logger: Verwende eigenen Handler mit Emoji-Formatter
for logger_name in ["discord", "discord.client", "discord.gateway"]:
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()
    discord_handler = logging.StreamHandler()
    discord_handler.setFormatter(DiscordEmojiFormatter())
    logger.addHandler(discord_handler)
    logger.propagate = False

class CustomFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(datefmt="%H:%M:%S")

    def format(self, record):
        emoji = "💖" if record.levelno == logging.INFO else "🌸" if record.levelno == logging.WARNING else "🩷" if record.levelno == logging.ERROR else "🚨"
        # Level-Namen bleiben wie im Original
        level = "DEBUG" if record.levelno == logging.DEBUG else "INFO" if record.levelno == logging.INFO else "WARN" if record.levelno == logging.WARNING else "ERROR" if record.levelno == logging.ERROR else "CRITICAL"
        time_str = self.formatTime(record, self.datefmt)
        return f"[{time_str}] {emoji}  {level:<7} │ {record.getMessage()}"

def get_logger(name="HazeWorldBot"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        handler.setFormatter(CustomFormatter())
        logger.addHandler(handler)
    return logger

def log_clear(channel, author, amount):
    Logger.info(f"🧹 {amount} Nachrichten von {channel} gelöscht durch {author}")

Logger = get_logger()