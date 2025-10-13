# 📦 Built-in modules
import logging

# 📥 Custom modules
from rich.console import Console as RichConsole
from rich.highlighter import RegexHighlighter
from rich.traceback import install as Install
from rich.logging import RichHandler
from rich.theme import Theme

# ⚙️ Settings
from Config import LogLevel, CommandPrefix  # Assuming CommandPrefix is available in HazeWorldBot Config

# 💡 Custom highlighter for log messages (adapted for HazeWorldBot)
class Highlighter(RegexHighlighter):
    base_style = f'{__name__}.'
    highlights = [
        r'(?P<Url>https?://[^\s]+)',
        r'Session ID: (?P<SessionID>[0-9a-z]{32})',
        r'Logged in as (?P<Login>.*?) \((?P<ID>[0-9]{19})\)',
        r'\[(?P<Channel>.*?)\]',
        r'Message from (?P<User>.*?): (?P<SentMessage>.*?)',
        r'Message edited by (?P<User>.*?): "(?P<OriginalMessage>.*?)" -> "(?P<EditedMessage>.*?)"',
        r'Message deleted by (?P<User>.*?): "(?P<DeletedMessage>.*?)"',
        rf'(?P<Command>{CommandPrefix}.*)',
        r'🧹 (?P<Clear>.*)',  # Highlight clear logs
        r'(?P<Discord>DC .*)',  # Highlight Discord logs
        r'(?P<RocketLeague>RL .*)',  # Highlight Rocket League logs
        r'(?P<Ticket>Ticket .*)',  # Highlight Ticket logs
    ]

# 🌱 Custom formatter with emojis (retained from old logger)
class EmojiRichFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(datefmt='[%H:%M:%S]')

    def format(self, record):
        emoji = "💖" if record.levelno == logging.INFO else "🌸" if record.levelno == logging.WARNING else "🩷" if record.levelno == logging.ERROR else "🚨"
        level = "DEBUG" if record.levelno == logging.DEBUG else "INFO" if record.levelno == logging.INFO else "WARN" if record.levelno == logging.WARNING else "ERROR" if record.levelno == logging.ERROR else "CRITICAL"
        time_str = self.formatTime(record, self.datefmt)
        return f"{time_str} {emoji}  {level:<7} │ {record.getMessage()}"

# 🌱 Initialize and define logging
def InitLogging():
    # 🎨 Pastel theme dictionary for log highlighting (adapted for HazeWorldBot)
    ThemeDict = {
        'log.time': 'bright_black',
        'logging.level.debug': '#B3D7EC',
        'logging.level.info': '#A0D6B4',
        'logging.level.warning': '#F5D7A3',
        'logging.level.error': '#F5A3A3',
        'logging.level.critical': '#ffc6ff',
        f'{__name__}.Url': '#F5D7A3',
        f'{__name__}.SessionID': '#A0D6B4',
        f'{__name__}.Login': '#B3D7EC',
        f'{__name__}.ID': '#A0D6B4',
        f'{__name__}.Channel': '#F5D7A3',
        f'{__name__}.User': '#B3D7EC',
        f'{__name__}.SentMessage': '#B3D7EC',
        f'{__name__}.OriginalMessage': '#F5A3A3',
        f'{__name__}.EditedMessage': '#A0D6B4',
        f'{__name__}.DeletedMessage': '#F5A3A3',
        f'{__name__}.Command': '#b5ead7',
        f'{__name__}.Clear': '#ff69b4',  # Pink for clear logs
        f'{__name__}.Discord': '#e0bbff',  # Purple for Discord logs
        f'{__name__}.RocketLeague': '#ff9999',  # Light red for RL logs
        f'{__name__}.Ticket': '#99ff99',  # Light green for Ticket logs
    }
    Console = RichConsole(
        theme=Theme(ThemeDict),
        force_terminal=True,
        log_path=False,
        highlighter=Highlighter(),
        color_system='truecolor',
    )

    ConsoleHandler = RichHandler(
        markup=False,
        rich_tracebacks=True,
        show_time=False,  # Disable Rich's time since we use custom formatter
        console=Console,
        show_path=False,
        omit_repeated_times=True,
        highlighter=Highlighter(),
        show_level=False,  # Disable Rich's level since we use custom formatter
    )

    ConsoleHandler.setFormatter(EmojiRichFormatter())  # Use custom formatter with emojis

    logging.basicConfig(level=LogLevel, handlers=[ConsoleHandler], force=True)

    Logger = logging.getLogger('rich')
    Logger.handlers.clear()
    Logger.addHandler(ConsoleHandler)
    Logger.propagate = False

    # Set up Discord loggers with Rich (adapted)
    for logger_name in ["discord", "discord.client", "discord.gateway"]:
        discord_logger = logging.getLogger(logger_name)
        discord_logger.handlers.clear()
        discord_logger.addHandler(ConsoleHandler)
        discord_logger.propagate = False

    return Console, Logger, ConsoleHandler

Console, Logger, ConsoleHandler = InitLogging()
Install()

def log_clear(channel, author, amount):
    """
    Logs when messages are cleared from a channel.
    """
    Logger.info(f"🧹 {amount} messages from {channel} deleted by {author}")

# 🧪 Logging test messages
if __name__ == '__main__':
    Logger.debug('This is a debug message.')
    Logger.info('This is an info message.')
    Logger.warning('This is a warning message.')
    Logger.error('This is an error message.')
    Logger.critical('This is a critical message.')