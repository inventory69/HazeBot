"""
Shared configuration helper functions for the API.
"""

import json
from pathlib import Path

import Config
from Utils.Logger import Logger


def save_config_to_file():
    """Persist the current in-memory configuration to api_config_overrides.json."""
    config_file = Path(__file__).parent.parent / Config.DATA_DIR / "api_config_overrides.json"
    config_file.parent.mkdir(exist_ok=True)

    Logger.info(f"🔧 Saving config to: {config_file} (DATA_DIR={Config.DATA_DIR})")

    config_data = {
        "general": {
            "bot_name": Config.BotName,
            "command_prefix": Config.CommandPrefix,
            "presence_update_interval": Config.PresenceUpdateInterval,
            "message_cooldown": Config.MessageCooldown,
            "fuzzy_matching_threshold": Config.FuzzyMatchingThreshold,
            "pink_color": Config.PINK.value if hasattr(Config.PINK, "value") else 0xAD1457,
            "embed_footer_text": getattr(Config, "EMBED_FOOTER_TEXT", ""),
        },
        "channels": {
            "log_channel_id": Config.LOG_CHANNEL_ID,
            "changelog_channel_id": Config.CHANGELOG_CHANNEL_ID,
            "todo_channel_id": Config.TODO_CHANNEL_ID,
            "rl_channel_id": Config.RL_CHANNEL_ID,
            "meme_channel_id": Config.MEME_CHANNEL_ID,
            "server_guide_channel_id": Config.SERVER_GUIDE_CHANNEL_ID,
            "welcome_rules_channel_id": Config.WELCOME_RULES_CHANNEL_ID,
            "welcome_public_channel_id": Config.WELCOME_PUBLIC_CHANNEL_ID,
            "transcript_channel_id": Config.TRANSCRIPT_CHANNEL_ID,
            "tickets_category_id": Config.TICKETS_CATEGORY_ID,
        },
        "roles": {
            "admin_role_id": Config.ADMIN_ROLE_ID,
            "moderator_role_id": Config.MODERATOR_ROLE_ID,
            "normal_role_id": Config.NORMAL_ROLE_ID,
            "member_role_id": Config.MEMBER_ROLE_ID,
            "changelog_role_id": Config.CHANGELOG_ROLE_ID,
            "meme_role_id": Config.MEME_ROLE_ID,
            "interest_role_ids": Config.INTEREST_ROLE_IDS,
            "interest_roles": Config.INTEREST_ROLES,
        },
        "meme": {
            "default_subreddits": Config.DEFAULT_MEME_SUBREDDITS,
            "default_lemmy": Config.DEFAULT_MEME_LEMMY,
            "meme_sources": Config.MEME_SOURCES,
            "templates_cache_duration": Config.MEME_TEMPLATES_CACHE_DURATION,
        },
        "rocket_league": {
            "rank_check_interval_hours": Config.RL_RANK_CHECK_INTERVAL_HOURS,
            "rank_cache_ttl_seconds": Config.RL_RANK_CACHE_TTL_SECONDS,
        },
        "rocket_league_texts": {
            "promotion_config": Config.RL_RANK_PROMOTION_CONFIG,
            "congrats_replies": Config.RL_CONGRATS_REPLIES,
        },
        "welcome": {
            "rules_text": Config.RULES_TEXT,
            "welcome_messages": Config.WELCOME_MESSAGES,
        },
        "welcome_texts": {
            "welcome_button_replies": Config.WELCOME_BUTTON_REPLIES,
        },
        "server_guide": Config.SERVER_GUIDE_CONFIG,
    }

    Logger.info(
        f"🔧 Saving RL config: interval={config_data['rocket_league']['rank_check_interval_hours']}h, "
        f"cache={config_data['rocket_league']['rank_cache_ttl_seconds']}s"
    )

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)

    Logger.info(f"✅ Config saved to {config_file}")
