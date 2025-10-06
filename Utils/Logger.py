import logging

# Set root logger to only show warnings and errors
logging.getLogger().setLevel(logging.WARNING)

class DiscordEmojiFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(datefmt="%H:%M:%S")

    def format(self, record):
        emoji = "💖" if record.levelno == logging.INFO else "🌸" if record.levelno == logging.WARNING else "🩷" if record.levelno == logging.ERROR else "🚨"
        level = "DC DEBUG" if record.levelno == logging.DEBUG else "DC INFO" if record.levelno == logging.INFO else "DC WARN" if record.levelno == logging.WARNING else "DC ERROR" if record.levelno == logging.ERROR else "DC CRIT"
        time_str = self.formatTime(record, self.datefmt)
        return f"[{time_str}] {emoji}  {level:<7} │ {record.getMessage()}"

# Remove all handlers from the root logger
root_logger = logging.getLogger()
root_logger.handlers.clear()

logging.basicConfig(level=logging.INFO, force=True)

# Set up Discord loggers with emoji formatter
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
        level = "DEBUG" if record.levelno == logging.DEBUG else "INFO" if record.levelno == logging.INFO else "WARN" if record.levelno == logging.WARNING else "ERROR" if record.levelno == logging.ERROR else "CRITICAL"
        time_str = self.formatTime(record, self.datefmt)
        return f"[{time_str}] {emoji}  {level:<7} │ {record.getMessage()}"

def get_logger(name="HazeWorldBot"):
    """
    Returns a logger instance with custom emoji formatting.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        handler.setFormatter(CustomFormatter())
        logger.addHandler(handler)
    return logger

def log_clear(channel, author, amount):
    """
    Logs when messages are cleared from a channel.
    """
    Logger.info(f"🧹 {amount} messages from {channel} deleted by {author}")

Logger = get_logger()