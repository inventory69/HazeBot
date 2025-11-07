"""
Configuration Loader Utility
Loads saved configuration overrides from JSON file and applies them to Config module
"""

import json
import os
from pathlib import Path
import Config


def load_config_from_file():
    """
    Load configuration from api_config_overrides.json and apply to Config module.
    This should be called at bot/API startup to restore saved settings.
    """
    config_file = Path(Config.DATA_DIR) / "api_config_overrides.json"
    
    print(f"🔍 DEBUG: Looking for config file at: {config_file} (DATA_DIR={Config.DATA_DIR})")
    
    if not config_file.exists():
        print(f"⚠️ No config file found at {config_file}")
        return  # No saved config yet
    
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        
        # Apply general settings
        if "general" in config_data:
            for key, value in config_data["general"].items():
                attr_name = key.upper() if not key.isupper() else key
                if attr_name == "BOT_NAME":
                    Config.BotName = value
                elif attr_name == "COMMAND_PREFIX":
                    Config.CommandPrefix = value
                else:
                    setattr(Config, attr_name, value)
        
        # Apply channel settings
        if "channels" in config_data:
            for key, value in config_data["channels"].items():
                setattr(Config, key.upper() if not key.isupper() else key, value)
        
        # Apply role settings
        if "roles" in config_data:
            for key, value in config_data["roles"].items():
                setattr(Config, key.upper() if not key.isupper() else key, value)
        
        # Apply meme settings
        if "meme" in config_data:
            for key, value in config_data["meme"].items():
                setattr(Config, key.upper() if not key.isupper() else key, value)
        
        # Apply Rocket League settings
        if "rocket_league" in config_data:
            rl_config = config_data["rocket_league"]
            print(f"🔍 DEBUG: Loading RL config from file: {rl_config}")
            if "rank_check_interval_hours" in rl_config:
                Config.RL_RANK_CHECK_INTERVAL_HOURS = rl_config["rank_check_interval_hours"]
                print(f"✅ Set RL_RANK_CHECK_INTERVAL_HOURS to {Config.RL_RANK_CHECK_INTERVAL_HOURS}")
            if "rank_cache_ttl_seconds" in rl_config:
                Config.RL_RANK_CACHE_TTL_SECONDS = rl_config["rank_cache_ttl_seconds"]
                print(f"✅ Set RL_RANK_CACHE_TTL_SECONDS to {Config.RL_RANK_CACHE_TTL_SECONDS}")
        
        # Apply welcome settings
        if "welcome" in config_data:
            for key, value in config_data["welcome"].items():
                setattr(Config, key.upper() if not key.isupper() else key, value)
        
        # Apply server guide settings
        if "server_guide" in config_data:
            Config.SERVER_GUIDE_CONFIG = config_data["server_guide"]
        
        print(f"✅ Loaded configuration from {config_file}")
        
    except Exception as e:
        print(f"❌ Error loading config from file: {e}")
