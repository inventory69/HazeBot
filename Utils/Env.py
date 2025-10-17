# 📦 Built-in modules
import os

# 📥 Custom modules
from dotenv import load_dotenv
from typing import Dict, Optional
from Utils.Logger import Logger


# 🌱 Load environment variables from .env file
def LoadEnv() -> Dict[str, Optional[str]]:
    """
    Loads environment variables from .env file and sets them in os.environ.
    If .env is not found, uses existing os.environ values.
    Logs errors if critical keys are missing.
    """
    EnvDict = {}
    try:
        # Load .env file
        load_dotenv()
        Logger.info("📄 .env file loaded successfully.")
    except Exception as e:
        Logger.warning(f"⚠️ Could not load .env file: {e}. Using existing environment variables.")

    # Define required keys (adapted for HazeWorldBot)
    required_keys = [
        "DISCORD_BOT_TOKEN",
        "DISCORD_GUILD_ID",
        "ROCKET_API_BASE",
        "ROCKET_API_KEY",
        "FLARESOLVERR_URL",
        "SMTP_SERVER",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASS",
        "SUPPORT_EMAIL",
    ]

    # Load and validate keys
    for key in required_keys:
        value = os.getenv(key)
        if value:
            os.environ[key] = value  # Ensure it's set in os.environ
            EnvDict[key] = value
            Logger.debug(f"✅ Loaded {key}")
        else:
            Logger.error(f"❌ Missing required environment variable: {key}")
            EnvDict[key] = None

    # Optional: Log summary (moved to Main.py to ensure Logger is ready)
    # loaded_count = sum(1 for v in EnvDict.values() if v is not None)
    # Logger.info(f"🌍 Environment variables loaded: {loaded_count}/{len(required_keys)}")

    return EnvDict
