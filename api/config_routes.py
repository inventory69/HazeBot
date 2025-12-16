"""
Configuration Routes Blueprint
Handles all /api/config/* endpoints for HazeBot configuration management
"""

import json
import os
from pathlib import Path

from flask import Blueprint, jsonify, request

# Will be initialized by init_config_routes()
Config = None
logger = None
_save_config_to_file_func = None
log_action = None
token_required = None
require_permission = None
log_config_action = None

# Create Blueprint
config_bp = Blueprint("config", __name__)


def save_config_to_file():
    """Wrapper to call the helpers save_config_to_file with correct arguments"""
    config_file = Path(__file__).parent.parent / Config.DATA_DIR / "api_config_overrides.json"
    return _save_config_to_file_func(Config, config_file)


def init_config_routes(app, config, log, helpers_module, auth_module):
    """
    Initialize config routes Blueprint with dependencies

    Args:
        app: Flask app instance
        config: Config module
        log: Logger instance
        helpers_module: Module containing save_config_to_file, log_action
        auth_module: Module containing decorators (token_required, require_permission, log_config_action)
    """
    global Config, logger, _save_config_to_file_func, log_action
    global token_required, require_permission, log_config_action

    Config = config
    logger = log
    _save_config_to_file_func = helpers_module.save_config_to_file
    log_action = helpers_module.log_action
    token_required = auth_module.token_required
    require_permission = auth_module.require_permission
    log_config_action = auth_module.log_config_action

    # Register blueprint WITHOUT decorators first
    app.register_blueprint(config_bp)

    # NOW apply decorators to already-registered view functions
    vf = app.view_functions
    vf["config.get_config"] = token_required(vf["config.get_config"])
    vf["config.config_general"] = token_required(
        require_permission("all")(log_config_action("general")(vf["config.config_general"]))
    )
    vf["config.reset_general_config"] = token_required(
        require_permission("all")(log_config_action("general")(vf["config.reset_general_config"]))
    )
    vf["config.config_channels"] = token_required(
        require_permission("all")(log_config_action("channels")(vf["config.config_channels"]))
    )
    vf["config.reset_channels_config"] = token_required(
        require_permission("all")(log_config_action("channels")(vf["config.reset_channels_config"]))
    )
    vf["config.config_roles"] = token_required(
        require_permission("all")(log_config_action("roles")(vf["config.config_roles"]))
    )
    vf["config.reset_roles_config"] = token_required(
        require_permission("all")(log_config_action("roles")(vf["config.reset_roles_config"]))
    )
    vf["config.config_meme"] = token_required(
        require_permission("all")(log_config_action("meme")(vf["config.config_meme"]))
    )
    vf["config.config_rocket_league"] = token_required(
        require_permission("all")(log_config_action("rocket_league")(vf["config.config_rocket_league"]))
    )
    vf["config.reset_rocket_league_config"] = token_required(
        require_permission("all")(log_config_action("rocket_league")(vf["config.reset_rocket_league_config"]))
    )
    vf["config.config_welcome"] = token_required(
        require_permission("all")(log_config_action("welcome")(vf["config.config_welcome"]))
    )
    vf["config.reset_welcome_config"] = token_required(
        require_permission("all")(log_config_action("welcome")(vf["config.reset_welcome_config"]))
    )
    vf["config.config_welcome_texts"] = token_required(
        require_permission("all")(log_config_action("welcome_texts")(vf["config.config_welcome_texts"]))
    )
    vf["config.reset_welcome_texts_config"] = token_required(
        require_permission("all")(log_config_action("welcome_texts")(vf["config.reset_welcome_texts_config"]))
    )
    vf["config.config_rocket_league_texts"] = token_required(
        require_permission("all")(log_config_action("rocket_league_texts")(vf["config.config_rocket_league_texts"]))
    )
    vf["config.reset_rocket_league_texts_config"] = token_required(
        require_permission("all")(
            log_config_action("rocket_league_texts")(vf["config.reset_rocket_league_texts_config"])
        )
    )
    vf["config.config_server_guide"] = token_required(
        require_permission("all")(log_config_action("server_guide")(vf["config.config_server_guide"]))
    )
    vf["config.get_ticket_config"] = token_required(vf["config.get_ticket_config"])
    vf["config.update_ticket_config"] = token_required(
        require_permission("all")(log_config_action("tickets")(vf["config.update_ticket_config"]))
    )
    vf["config.reset_ticket_config"] = token_required(
        require_permission("all")(log_config_action("tickets")(vf["config.reset_ticket_config"]))
    )
    vf["config.get_xp_config"] = token_required(vf["config.get_xp_config"])
    vf["config.update_xp_config"] = token_required(
        require_permission("all")(log_config_action("xp_config")(vf["config.update_xp_config"]))
    )
    vf["config.reset_xp_config"] = token_required(
        require_permission("all")(log_config_action("xp_config")(vf["config.reset_xp_config"]))
    )


# ===== MAIN CONFIG ENDPOINT =====


@config_bp.route("/api/config", methods=["GET"])
def get_config():
    """Get all bot configuration"""
    # Try to get actual subreddits/lemmy from DailyMeme cog
    from flask import current_app

    bot = current_app.config.get("bot_instance")
    subreddits = []
    lemmy_communities = []
    daily_meme_config = {}

    if bot:
        daily_meme_cog = bot.get_cog("DailyMeme")
        if daily_meme_cog:
            subreddits = daily_meme_cog.meme_subreddits
            lemmy_communities = daily_meme_cog.meme_lemmy
            # Convert Discord IDs to strings to prevent precision loss in Flutter Web
            daily_meme_config = daily_meme_cog.daily_config.copy()
            if "channel_id" in daily_meme_config and daily_meme_config["channel_id"]:
                daily_meme_config["channel_id"] = str(daily_meme_config["channel_id"])
            if "role_id" in daily_meme_config and daily_meme_config["role_id"]:
                daily_meme_config["role_id"] = str(daily_meme_config["role_id"])

    config_data = {
        # General Settings
        "general": {
            "bot_name": Config.BotName,
            "command_prefix": Config.CommandPrefix,
            "presence_update_interval": Config.PresenceUpdateInterval,
            "message_cooldown": Config.MessageCooldown,
            "fuzzy_matching_threshold": Config.FuzzyMatchingThreshold,
            "prod_mode": Config.PROD_MODE,
        },
        # Logging Configuration
        "logging": {
            "log_level": Config.LogLevel,
            "cog_log_levels": Config.COG_LOG_LEVELS,
        },
        # Discord IDs (convert to strings to prevent precision loss in Flutter Web)
        "discord_ids": {
            "guild_id": str(Config.GUILD_ID) if Config.GUILD_ID else None,
            "guild_name": getattr(Config, "GUILD_NAME", None),
            "admin_role_id": str(Config.ADMIN_ROLE_ID) if Config.ADMIN_ROLE_ID else None,
            "moderator_role_id": str(Config.MODERATOR_ROLE_ID) if Config.MODERATOR_ROLE_ID else None,
            "normal_role_id": str(Config.NORMAL_ROLE_ID) if Config.NORMAL_ROLE_ID else None,
            "member_role_id": str(Config.MEMBER_ROLE_ID) if Config.MEMBER_ROLE_ID else None,
            "changelog_role_id": str(Config.CHANGELOG_ROLE_ID) if Config.CHANGELOG_ROLE_ID else None,
            "meme_role_id": str(Config.MEME_ROLE_ID) if Config.MEME_ROLE_ID else None,
            "interest_role_ids": [str(rid) for rid in Config.INTEREST_ROLE_IDS] if Config.INTEREST_ROLE_IDS else [],
            "interest_roles": Config.INTEREST_ROLES,
        },
        # Channels (convert to strings to prevent precision loss in Flutter Web)
        "channels": {
            "log_channel_id": str(Config.LOG_CHANNEL_ID) if Config.LOG_CHANNEL_ID else None,
            "changelog_channel_id": str(Config.CHANGELOG_CHANNEL_ID) if Config.CHANGELOG_CHANNEL_ID else None,
            "todo_channel_id": str(Config.TODO_CHANNEL_ID) if Config.TODO_CHANNEL_ID else None,
            "rl_channel_id": str(Config.RL_CHANNEL_ID) if Config.RL_CHANNEL_ID else None,
            "meme_channel_id": str(Config.MEME_CHANNEL_ID) if Config.MEME_CHANNEL_ID else None,
            "server_guide_channel_id": str(Config.SERVER_GUIDE_CHANNEL_ID) if Config.SERVER_GUIDE_CHANNEL_ID else None,
            "status_channel_id": str(Config.STATUS_CHANNEL_ID) if Config.STATUS_CHANNEL_ID else None,
            "welcome_rules_channel_id": str(Config.WELCOME_RULES_CHANNEL_ID)
            if Config.WELCOME_RULES_CHANNEL_ID
            else None,
            "welcome_public_channel_id": str(Config.WELCOME_PUBLIC_CHANNEL_ID)
            if Config.WELCOME_PUBLIC_CHANNEL_ID
            else None,
            "transcript_channel_id": str(Config.TRANSCRIPT_CHANNEL_ID) if Config.TRANSCRIPT_CHANNEL_ID else None,
            "tickets_category_id": str(Config.TICKETS_CATEGORY_ID) if Config.TICKETS_CATEGORY_ID else None,
        },
        # Rocket League
        "rocket_league": {
            "rank_check_interval_hours": Config.RL_RANK_CHECK_INTERVAL_HOURS,
            "rank_cache_ttl_seconds": Config.RL_RANK_CACHE_TTL_SECONDS,
        },
        "rocket_league_texts": {
            "promotion_config": Config.RL_RANK_PROMOTION_CONFIG,
            "congrats_replies": Config.RL_CONGRATS_REPLIES,
        },
        # Status Dashboard Configuration
        "status_dashboard": {
            "update_interval_minutes": Config.STATUS_DASHBOARD_CONFIG.get("update_interval_minutes", 5),
            "show_monitoring": Config.STATUS_DASHBOARD_CONFIG.get("show_monitoring", True),
        },
        # Meme Configuration
        "meme": {
            "default_subreddits": Config.DEFAULT_MEME_SUBREDDITS,
            "default_lemmy": Config.DEFAULT_MEME_LEMMY,
            "meme_sources": Config.MEME_SOURCES,
            "templates_cache_duration": Config.MEME_TEMPLATES_CACHE_DURATION,
            "subreddits": subreddits,
            "lemmy_communities": lemmy_communities,
        },
        # Daily Meme
        "daily_meme": daily_meme_config,
        # Welcome System
        "welcome": {
            "rules_text": Config.RULES_TEXT,
            "welcome_messages": Config.WELCOME_MESSAGES,
        },
        "welcome_texts": {
            "welcome_button_replies": Config.WELCOME_BUTTON_REPLIES,
        },
        # Server Guide
        "server_guide": Config.SERVER_GUIDE_CONFIG,
        # Role Display Names
        "role_names": Config.ROLE_NAMES,
    }

    return jsonify(config_data)


# ===== GENERAL CONFIG =====


@config_bp.route("/api/config/general", methods=["GET", "PUT"])
def config_general():
    """Get or update general configuration"""
    if request.method == "GET":
        # Get StatusDashboard config with defaults
        status_dashboard_config = Config.STATUS_DASHBOARD_CONFIG if hasattr(Config, "STATUS_DASHBOARD_CONFIG") else {}

        return jsonify(
            {
                "bot_name": Config.BotName,
                "command_prefix": Config.CommandPrefix,
                "presence_update_interval": Config.PresenceUpdateInterval,
                "message_cooldown": Config.MessageCooldown,
                "fuzzy_matching_threshold": Config.FuzzyMatchingThreshold,
                "pink_color": Config.PINK.value if hasattr(Config, "PINK") else 0xAD1457,
                "embed_footer_text": Config.EMBED_FOOTER_TEXT
                if hasattr(Config, "EMBED_FOOTER_TEXT")
                else "Powered by Haze World 💖",
                "role_names": Config.ROLE_NAMES if hasattr(Config, "ROLE_NAMES") else {},
                "status_dashboard": {
                    "update_interval_minutes": status_dashboard_config.get("update_interval_minutes", 5),
                    "show_monitoring": status_dashboard_config.get("show_monitoring", True),
                },
            }
        )

    if request.method == "PUT":
        data = request.get_json()

        # Track changes for logging
        changes = []

        # Update configuration (in memory)
        if "bot_name" in data:
            changes.append(f"bot_name: {Config.BotName} -> {data['bot_name']}")
            Config.BotName = data["bot_name"]
        if "command_prefix" in data:
            changes.append(f"command_prefix: {Config.CommandPrefix} -> {data['command_prefix']}")
            Config.CommandPrefix = data["command_prefix"]
        if "presence_update_interval" in data:
            changes.append(
                f"presence_update_interval: {Config.PresenceUpdateInterval} -> {data['presence_update_interval']}"
            )
            Config.PresenceUpdateInterval = int(data["presence_update_interval"])
        if "message_cooldown" in data:
            changes.append(f"message_cooldown: {Config.MessageCooldown} -> {data['message_cooldown']}")
            Config.MessageCooldown = int(data["message_cooldown"])
        if "fuzzy_matching_threshold" in data:
            changes.append(
                f"fuzzy_matching_threshold: {Config.FuzzyMatchingThreshold} -> {data['fuzzy_matching_threshold']}"
            )
            Config.FuzzyMatchingThreshold = float(data["fuzzy_matching_threshold"])
        if "pink_color" in data:
            import discord

            changes.append(
                f"pink_color: {Config.PINK.value if hasattr(Config, 'PINK') else 'N/A'} -> {data['pink_color']}"
            )
            Config.PINK = discord.Color(int(data["pink_color"]))
        if "embed_footer_text" in data:
            changes.append("embed_footer_text changed")
            Config.EMBED_FOOTER_TEXT = data["embed_footer_text"]
        if "role_names" in data:
            changes.append(f"role_names updated ({len(data['role_names'])} roles)")
            Config.ROLE_NAMES = data["role_names"]
        if "status_dashboard" in data:
            # Initialize if not exists
            if not hasattr(Config, "STATUS_DASHBOARD_CONFIG"):
                Config.STATUS_DASHBOARD_CONFIG = {}

            status_config = data["status_dashboard"]

            # Validate and update update_interval_minutes (1-60 range)
            if "update_interval_minutes" in status_config:
                interval = int(status_config["update_interval_minutes"])
                if interval < 1 or interval > 60:
                    return jsonify({"error": "update_interval_minutes must be between 1 and 60"}), 400
                changes.append(
                    f"status_dashboard.update_interval_minutes: "
                    f"{Config.STATUS_DASHBOARD_CONFIG.get('update_interval_minutes', 5)} -> {interval}"
                )
                Config.STATUS_DASHBOARD_CONFIG["update_interval_minutes"] = interval

            # Update show_monitoring
            if "show_monitoring" in status_config:
                show_monitoring = bool(status_config["show_monitoring"])
                changes.append(
                    f"status_dashboard.show_monitoring: "
                    f"{Config.STATUS_DASHBOARD_CONFIG.get('show_monitoring', True)} -> {show_monitoring}"
                )
                Config.STATUS_DASHBOARD_CONFIG["show_monitoring"] = show_monitoring

        # Save to file
        save_config_to_file()

        # Log the action
        log_action(request.username, "update_general_config", {"changes": changes})

        return jsonify({"success": True, "message": "Configuration updated"})


@config_bp.route("/api/config/general/reset", methods=["POST"])
def reset_general_config():
    """Reset general configuration to default values"""
    import discord

    # Reset to default values from Config.py
    Config.BotName = "Haze World Bot"
    Config.CommandPrefix = "!"
    Config.PresenceUpdateInterval = 3600
    Config.MessageCooldown = 5
    Config.FuzzyMatchingThreshold = 0.6
    Config.PINK = discord.Color(0xAD1457)
    Config.EMBED_FOOTER_TEXT = "Powered by Haze World 💖"
    Config.ROLE_NAMES = {
        "user": "🎒 Lootling",
        "mod": "📦 Slot Keeper",
        "admin": "🧊 Inventory Master",
    }
    Config.STATUS_DASHBOARD_CONFIG = {"update_interval_minutes": 5, "show_monitoring": True}

    # Save to file
    save_config_to_file()

    # Log the action
    log_action(request.username, "reset_general_config", {"status": "reset to defaults"})

    return jsonify({"success": True, "message": "General configuration reset to defaults"})


# ===== CHANNELS CONFIG =====


@config_bp.route("/api/config/channels", methods=["GET", "PUT"])
def config_channels():
    """Get or update channel configuration"""
    if request.method == "GET":
        # Return IDs as strings to prevent precision loss in Flutter Web (JavaScript)
        return jsonify(
            {
                "log_channel_id": str(Config.LOG_CHANNEL_ID) if Config.LOG_CHANNEL_ID else None,
                "changelog_channel_id": str(Config.CHANGELOG_CHANNEL_ID) if Config.CHANGELOG_CHANNEL_ID else None,
                "todo_channel_id": str(Config.TODO_CHANNEL_ID) if Config.TODO_CHANNEL_ID else None,
                "rl_channel_id": str(Config.RL_CHANNEL_ID) if Config.RL_CHANNEL_ID else None,
                "gaming_channel_id": str(Config.GAMING_CHANNEL_ID) if Config.GAMING_CHANNEL_ID else None,
                "meme_channel_id": str(Config.MEME_CHANNEL_ID) if Config.MEME_CHANNEL_ID else None,
                "server_guide_channel_id": str(Config.SERVER_GUIDE_CHANNEL_ID)
                if Config.SERVER_GUIDE_CHANNEL_ID
                else None,
                "welcome_rules_channel_id": str(Config.WELCOME_RULES_CHANNEL_ID)
                if Config.WELCOME_RULES_CHANNEL_ID
                else None,
                "welcome_public_channel_id": str(Config.WELCOME_PUBLIC_CHANNEL_ID)
                if Config.WELCOME_PUBLIC_CHANNEL_ID
                else None,
                "transcript_channel_id": str(Config.TRANSCRIPT_CHANNEL_ID) if Config.TRANSCRIPT_CHANNEL_ID else None,
                "tickets_category_id": str(Config.TICKETS_CATEGORY_ID) if Config.TICKETS_CATEGORY_ID else None,
                "status_channel_id": str(Config.STATUS_CHANNEL_ID) if Config.STATUS_CHANNEL_ID else None,
            }
        )

    if request.method == "PUT":
        data = request.get_json()

        # Validate and update channel IDs
        for key, value in data.items():
            key_upper = key.upper()
            if key_upper in Config.CURRENT_IDS:
                try:
                    # Validate Discord snowflake (should be a positive integer)
                    channel_id = int(value)
                    if channel_id <= 0:
                        return jsonify({"error": f"Invalid channel ID for {key}: must be positive"}), 400

                    Config.CURRENT_IDS[key_upper] = channel_id
                    setattr(Config, key_upper, channel_id)
                except (ValueError, TypeError):
                    return jsonify({"error": f"Invalid channel ID for {key}: must be an integer"}), 400

        # Save to file
        save_config_to_file()

        return jsonify({"success": True, "message": "Channel configuration updated"})


@config_bp.route("/api/config/channels/reset", methods=["POST"])
def reset_channels_config():
    """Reset channels configuration to default values"""
    # Reset to default values from CURRENT_IDS (which is already set based on PROD_MODE)
    Config.LOG_CHANNEL_ID = Config.CURRENT_IDS["LOG_CHANNEL_ID"]
    Config.CHANGELOG_CHANNEL_ID = Config.CURRENT_IDS["CHANGELOG_CHANNEL_ID"]
    Config.TODO_CHANNEL_ID = Config.CURRENT_IDS["TODO_CHANNEL_ID"]
    Config.RL_CHANNEL_ID = Config.CURRENT_IDS["RL_CHANNEL_ID"]
    Config.GAMING_CHANNEL_ID = Config.CURRENT_IDS.get("GAMING_CHANNEL_ID")
    Config.MEME_CHANNEL_ID = Config.CURRENT_IDS.get("MEME_CHANNEL_ID")
    Config.SERVER_GUIDE_CHANNEL_ID = Config.CURRENT_IDS.get("SERVER_GUIDE_CHANNEL_ID")
    Config.WELCOME_RULES_CHANNEL_ID = Config.CURRENT_IDS["WELCOME_RULES_CHANNEL_ID"]
    Config.WELCOME_PUBLIC_CHANNEL_ID = Config.CURRENT_IDS["WELCOME_PUBLIC_CHANNEL_ID"]
    Config.TRANSCRIPT_CHANNEL_ID = Config.CURRENT_IDS["TRANSCRIPT_CHANNEL_ID"]
    Config.TICKETS_CATEGORY_ID = Config.CURRENT_IDS["TICKETS_CATEGORY_ID"]
    Config.STATUS_CHANNEL_ID = Config.CURRENT_IDS.get("STATUS_CHANNEL_ID")

    # Save to file
    save_config_to_file()

    return jsonify({"success": True, "message": "Channels configuration reset to defaults"})


# ===== ROLES CONFIG =====


@config_bp.route("/api/config/roles", methods=["GET", "PUT"])
def config_roles():
    """Get or update role configuration"""
    if request.method == "GET":
        # Return IDs as strings to prevent precision loss in Flutter Web (JavaScript)
        return jsonify(
            {
                "admin_role_id": str(Config.ADMIN_ROLE_ID) if Config.ADMIN_ROLE_ID else None,
                "moderator_role_id": str(Config.MODERATOR_ROLE_ID) if Config.MODERATOR_ROLE_ID else None,
                "normal_role_id": str(Config.NORMAL_ROLE_ID) if Config.NORMAL_ROLE_ID else None,
                "member_role_id": str(Config.MEMBER_ROLE_ID) if Config.MEMBER_ROLE_ID else None,
                "changelog_role_id": str(Config.CHANGELOG_ROLE_ID) if Config.CHANGELOG_ROLE_ID else None,
                "meme_role_id": str(Config.MEME_ROLE_ID) if Config.MEME_ROLE_ID else None,
                "interest_role_ids": [str(rid) for rid in Config.INTEREST_ROLE_IDS] if Config.INTEREST_ROLE_IDS else [],
                "interest_roles": {k: str(v) if v else None for k, v in Config.INTEREST_ROLES.items()}
                if Config.INTEREST_ROLES
                else {},
            }
        )

    if request.method == "PUT":
        data = request.get_json()

        # Validate and update role IDs
        for key, value in data.items():
            key_upper = key.upper()
            if key_upper in Config.CURRENT_IDS:
                try:
                    # Handle lists (like interest_role_ids) and dicts (like interest_roles)
                    if isinstance(value, list):
                        # Validate each ID in the list
                        validated_list = []
                        for item in value:
                            item_int = int(item)
                            if item_int <= 0:
                                return jsonify({"error": f"Invalid role ID in {key}: must be positive"}), 400
                            validated_list.append(item_int)
                        Config.CURRENT_IDS[key_upper] = validated_list
                        setattr(Config, key_upper, validated_list)
                    elif isinstance(value, dict):
                        # Validate each ID in the dict
                        validated_dict = {}
                        for k, v in value.items():
                            v_int = int(v)
                            if v_int <= 0:
                                return jsonify({"error": f"Invalid role ID for {k} in {key}: must be positive"}), 400
                            validated_dict[k] = v_int
                        Config.CURRENT_IDS[key_upper] = validated_dict
                        setattr(Config, key_upper, validated_dict)
                    else:
                        # Single role ID
                        role_id = int(value)
                        if role_id <= 0:
                            return jsonify({"error": f"Invalid role ID for {key}: must be positive"}), 400
                        Config.CURRENT_IDS[key_upper] = role_id
                        setattr(Config, key_upper, role_id)
                except (ValueError, TypeError):
                    return jsonify({"error": f"Invalid role ID for {key}: must be integer(s)"}), 400

        # Save to file
        save_config_to_file()

        return jsonify({"success": True, "message": "Role configuration updated"})


@config_bp.route("/api/config/roles/reset", methods=["POST"])
def reset_roles_config():
    """Reset all role IDs to defaults from CURRENT_IDS"""
    Config.ADMIN_ROLE_ID = Config.CURRENT_IDS["ADMIN_ROLE_ID"]
    Config.MODERATOR_ROLE_ID = Config.CURRENT_IDS["MODERATOR_ROLE_ID"]
    Config.NORMAL_ROLE_ID = Config.CURRENT_IDS["NORMAL_ROLE_ID"]
    Config.MEMBER_ROLE_ID = Config.CURRENT_IDS["MEMBER_ROLE_ID"]
    Config.CHANGELOG_ROLE_ID = Config.CURRENT_IDS["CHANGELOG_ROLE_ID"]
    Config.MEME_ROLE_ID = Config.CURRENT_IDS.get("MEME_ROLE_ID")

    # Save to file
    save_config_to_file()

    return jsonify({"success": True, "message": "Roles configuration reset to defaults"})


# ===== MEME CONFIG =====


@config_bp.route("/api/config/meme", methods=["GET", "PUT"])
def config_meme():
    """Get or update meme configuration"""
    if request.method == "GET":
        # Try to get actual subreddits/lemmy from DailyMeme cog
        from flask import current_app

        bot = current_app.config.get("bot_instance")
        subreddits = Config.DEFAULT_MEME_SUBREDDITS
        lemmy_communities = Config.DEFAULT_MEME_LEMMY

        if bot:
            daily_meme_cog = bot.get_cog("DailyMeme")
            if daily_meme_cog:
                subreddits = daily_meme_cog.meme_subreddits
                lemmy_communities = daily_meme_cog.meme_lemmy

        return jsonify(
            {
                "default_subreddits": Config.DEFAULT_MEME_SUBREDDITS,
                "default_lemmy": Config.DEFAULT_MEME_LEMMY,
                "meme_sources": Config.MEME_SOURCES,
                "templates_cache_duration": Config.MEME_TEMPLATES_CACHE_DURATION,
                "subreddits": subreddits,
                "lemmy_communities": lemmy_communities,
            }
        )

    if request.method == "PUT":
        data = request.get_json()

        if "default_subreddits" in data:
            Config.DEFAULT_MEME_SUBREDDITS = data["default_subreddits"]
        if "default_lemmy" in data:
            Config.DEFAULT_MEME_LEMMY = data["default_lemmy"]
        if "meme_sources" in data:
            Config.MEME_SOURCES = data["meme_sources"]
        if "templates_cache_duration" in data:
            Config.MEME_TEMPLATES_CACHE_DURATION = int(data["templates_cache_duration"])

        # Save to file
        save_config_to_file()

        return jsonify({"success": True, "message": "Meme configuration updated"})


# ===== ROCKET LEAGUE CONFIG =====


@config_bp.route("/api/config/rocket_league", methods=["GET", "PUT"])
def config_rocket_league():
    """Get or update Rocket League configuration"""
    if request.method == "GET":
        return jsonify(
            {
                "rank_check_interval_hours": Config.RL_RANK_CHECK_INTERVAL_HOURS,
                "rank_cache_ttl_seconds": Config.RL_RANK_CACHE_TTL_SECONDS,
            }
        )

    if request.method == "PUT":
        data = request.get_json()

        logger.info(f"🔍 DEBUG API: Received RL config update: {data}")

        if "rank_check_interval_hours" in data:
            Config.RL_RANK_CHECK_INTERVAL_HOURS = int(data["rank_check_interval_hours"])
            logger.info(f"✅ API: Set RL_RANK_CHECK_INTERVAL_HOURS to {Config.RL_RANK_CHECK_INTERVAL_HOURS}")
        if "rank_cache_ttl_seconds" in data:
            Config.RL_RANK_CACHE_TTL_SECONDS = int(data["rank_cache_ttl_seconds"])
            logger.info(f"✅ API: Set RL_RANK_CACHE_TTL_SECONDS to {Config.RL_RANK_CACHE_TTL_SECONDS}")

        # Save to file
        logger.info("💾 API: Saving config to file...")
        save_config_to_file()

        return jsonify({"success": True, "message": "Rocket League configuration updated"})


@config_bp.route("/api/config/rocket_league/reset", methods=["POST"])
def reset_rocket_league_config():
    """Reset Rocket League configuration to default values"""
    # Reset to default values from Config.py
    Config.RL_RANK_CHECK_INTERVAL_HOURS = 3
    Config.RL_RANK_CACHE_TTL_SECONDS = 10500  # 2h 55min

    # Save to file
    save_config_to_file()

    return jsonify({"success": True, "message": "Rocket League configuration reset to defaults"})


# ===== WELCOME CONFIG =====


@config_bp.route("/api/config/welcome", methods=["GET", "PUT"])
def config_welcome():
    """Get or update welcome system configuration"""
    if request.method == "GET":
        return jsonify(
            {
                "rules_text": Config.RULES_TEXT,
                "welcome_messages": Config.WELCOME_MESSAGES,
            }
        )

    if request.method == "PUT":
        data = request.get_json()

        if "rules_text" in data:
            Config.RULES_TEXT = data["rules_text"]
        if "welcome_messages" in data:
            Config.WELCOME_MESSAGES = data["welcome_messages"]

        # Save to file
        save_config_to_file()

        return jsonify({"success": True, "message": "Welcome configuration updated"})


@config_bp.route("/api/config/welcome/reset", methods=["POST"])
def reset_welcome_config():
    """Reset welcome configuration to defaults"""
    # Import the original defaults
    import importlib
    import Config as OriginalConfig

    importlib.reload(OriginalConfig)

    Config.RULES_TEXT = OriginalConfig.RULES_TEXT
    Config.WELCOME_MESSAGES = OriginalConfig.WELCOME_MESSAGES

    save_config_to_file()

    return jsonify(
        {
            "success": True,
            "message": "Welcome configuration reset to defaults",
            "config": {
                "rules_text": Config.RULES_TEXT,
                "welcome_messages": Config.WELCOME_MESSAGES,
            },
        }
    )


# ===== WELCOME TEXTS CONFIG =====


@config_bp.route("/api/config/welcome_texts", methods=["GET", "PUT"])
def config_welcome_texts():
    """Get or update welcome text configuration"""
    if request.method == "GET":
        return jsonify(
            {
                "welcome_button_replies": Config.WELCOME_BUTTON_REPLIES,
            }
        )

    if request.method == "PUT":
        data = request.get_json()

        if "welcome_button_replies" in data:
            Config.WELCOME_BUTTON_REPLIES = data["welcome_button_replies"]

        # Save to file
        save_config_to_file()

        return jsonify({"success": True, "message": "Welcome text configuration updated"})


@config_bp.route("/api/config/welcome_texts/reset", methods=["POST"])
def reset_welcome_texts_config():
    """Reset welcome text configuration to defaults"""
    # Import the original defaults
    import importlib
    import Config as OriginalConfig

    importlib.reload(OriginalConfig)

    Config.WELCOME_BUTTON_REPLIES = OriginalConfig.WELCOME_BUTTON_REPLIES

    save_config_to_file()

    return jsonify(
        {
            "success": True,
            "message": "Welcome text configuration reset to defaults",
            "config": {
                "welcome_button_replies": Config.WELCOME_BUTTON_REPLIES,
            },
        }
    )


# ===== ROCKET LEAGUE TEXTS CONFIG =====


@config_bp.route("/api/config/rocket_league_texts", methods=["GET", "PUT"])
def config_rocket_league_texts():
    """Get or update Rocket League text configuration"""
    if request.method == "GET":
        return jsonify(
            {
                "promotion_config": Config.RL_RANK_PROMOTION_CONFIG,
                "congrats_replies": Config.RL_CONGRATS_REPLIES,
            }
        )

    if request.method == "PUT":
        data = request.get_json()

        if "promotion_config" in data:
            Config.RL_RANK_PROMOTION_CONFIG = data["promotion_config"]
        if "congrats_replies" in data:
            Config.RL_CONGRATS_REPLIES = data["congrats_replies"]

        # Save to file
        save_config_to_file()

        return jsonify({"success": True, "message": "Rocket League text configuration updated"})


@config_bp.route("/api/config/rocket_league_texts/reset", methods=["POST"])
def reset_rocket_league_texts_config():
    """Reset Rocket League text configuration to defaults"""
    # Import the original defaults
    import importlib
    import Config as OriginalConfig

    importlib.reload(OriginalConfig)

    Config.RL_RANK_PROMOTION_CONFIG = OriginalConfig.RL_RANK_PROMOTION_CONFIG
    Config.RL_CONGRATS_REPLIES = OriginalConfig.RL_CONGRATS_REPLIES

    save_config_to_file()

    return jsonify(
        {
            "success": True,
            "message": "Rocket League text configuration reset to defaults",
            "config": {
                "promotion_config": Config.RL_RANK_PROMOTION_CONFIG,
                "congrats_replies": Config.RL_CONGRATS_REPLIES,
            },
        }
    )


# ===== SERVER GUIDE CONFIG =====


@config_bp.route("/api/config/server_guide", methods=["GET", "PUT"])
def config_server_guide():
    """Get or update server guide configuration"""
    if request.method == "GET":
        return jsonify(Config.SERVER_GUIDE_CONFIG)

    if request.method == "PUT":
        data = request.get_json()
        Config.SERVER_GUIDE_CONFIG = data

        # Save to file
        save_config_to_file()

        return jsonify({"success": True, "message": "Server guide configuration updated"})


# ===== TICKETS CONFIG =====


@config_bp.route("/api/config/tickets", methods=["GET"])
def get_ticket_config():
    """Get ticket system configuration"""
    try:
        # Load config from file if exists, otherwise use defaults
        config_file = Path(__file__).parent.parent / Config.DATA_DIR / "tickets_config.json"

        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                ticket_config = json.load(f)
        else:
            # Default ticket configuration based on bot's TicketTypeSelect
            # Email comes from SUPPORT_EMAIL in .env (same as bot uses)
            support_email = os.getenv("SUPPORT_EMAIL", "")
            ticket_config = {
                "categories": ["Application", "Bug", "Support"],  # From bot's TicketTypeSelect
                "auto_delete_after_close_days": 7,  # Bot deletes closed tickets after 7 days
                "require_claim": False,
                "send_transcript_email": bool(support_email),  # Enable if email configured
                "transcript_email_address": support_email,
            }

        return jsonify(ticket_config)

    except Exception as e:
        import traceback

        logger.error(f"Error fetching ticket config: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch ticket config: {str(e)}"}), 500


@config_bp.route("/api/config/tickets", methods=["PUT"])
def update_ticket_config():
    """Update ticket system configuration"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        config_file = Path(__file__).parent.parent / Config.DATA_DIR / "tickets_config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing config or create default
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            # Default matches bot's TicketTypeSelect
            support_email = os.getenv("SUPPORT_EMAIL", "")
            config = {
                "categories": ["Application", "Bug", "Support"],
                "auto_delete_after_close_days": 7,
                "require_claim": False,
                "send_transcript_email": bool(support_email),
                "transcript_email_address": support_email,
            }

        # Update config with provided data
        if "categories" in data:
            config["categories"] = data["categories"]
        if "auto_delete_after_close_days" in data:
            config["auto_delete_after_close_days"] = data["auto_delete_after_close_days"]
        if "require_claim" in data:
            config["require_claim"] = data["require_claim"]
        if "send_transcript_email" in data:
            config["send_transcript_email"] = data["send_transcript_email"]
        if "transcript_email_address" in data:
            config["transcript_email_address"] = data["transcript_email_address"]

        # Save config
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        logger.info(f"✅ Ticket config updated by {request.username}")

        return jsonify({"success": True, "message": "Ticket configuration updated successfully"})

    except Exception as e:
        import traceback

        logger.error(f"Error updating ticket config: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to update ticket config: {str(e)}"}), 500


@config_bp.route("/api/config/tickets/reset", methods=["POST"])
def reset_ticket_config():
    """Reset ticket configuration to defaults"""
    try:
        config_file = Path(__file__).parent.parent / Config.DATA_DIR / "tickets_config.json"

        # Reset to defaults (matching bot's TicketTypeSelect)
        support_email = os.getenv("SUPPORT_EMAIL", "")
        default_config = {
            "categories": ["Application", "Bug", "Support"],
            "auto_delete_after_close_days": 7,  # Bot deletes closed tickets after 7 days
            "require_claim": False,
            "send_transcript_email": bool(support_email),
            "transcript_email_address": support_email,
        }

        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2)

        log_action(request.username, "reset_ticket_config", {"status": "reset to defaults"})

        return jsonify({"success": True, "message": "Ticket configuration reset to defaults"})

    except Exception as e:
        import traceback

        logger.error(f"Error resetting ticket config: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to reset ticket config: {str(e)}"}), 500


# ============================================================================
# XP/LEVEL SYSTEM CONFIGURATION
# ============================================================================


@config_bp.route("/api/config/xp", methods=["GET"])
def get_xp_config():
    """Get XP System Configuration"""
    try:
        config = {
            "activity_xp": {
                "message_sent": Config.XP_CONFIG["message_sent"],
                "image_sent": Config.XP_CONFIG["image_sent"],
                "ticket_created": Config.XP_CONFIG["ticket_created"],
                "game_request": Config.XP_CONFIG["game_request"],
                "meme_fetch": Config.XP_CONFIG["meme_fetch"],
                "meme_post": Config.XP_CONFIG["meme_post"],
                "meme_generate": Config.XP_CONFIG["meme_generate"],
                "meme_generate_post": Config.XP_CONFIG["meme_generate_post"],
                "rl_account_linked": Config.XP_CONFIG["rl_account_linked"],
                "rl_stats_checked": Config.XP_CONFIG["rl_stats_checked"],
                "ticket_resolved": Config.XP_CONFIG["ticket_resolved"],
                "ticket_claimed": Config.XP_CONFIG["ticket_claimed"],
            },
            "level_calculation": {
                "base_xp_per_level": Config.XP_CONFIG["base_xp_per_level"],
                "xp_multiplier": Config.XP_CONFIG["xp_multiplier"],
            },
            "cooldowns": {
                "message_cooldown": Config.XP_CONFIG["message_cooldown"],
                "meme_fetch_cooldown": Config.XP_CONFIG["meme_fetch_cooldown"],
                "daily_xp_cap": Config.XP_CONFIG["daily_xp_cap"],
            },
            "level_tiers": {
                tier_key: {
                    **tier_data,
                    "color": f"#{tier_data['color']:06X}"
                    if isinstance(tier_data["color"], int)
                    else tier_data["color"],
                    "emoji": Config.LEVEL_TIER_EMOJIS.get(tier_key, "⭐"),
                }
                for tier_key, tier_data in Config.LEVEL_TIERS.items()
            },
            "level_icons": Config.LEVEL_ICONS,
        }

        return jsonify({"success": True, "config": config})
    except Exception as e:
        import traceback

        logger.error(f"Error getting XP config: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to get XP config: {str(e)}"}), 500


@config_bp.route("/api/config/xp", methods=["PUT"])
def update_xp_config():
    """Update XP System Configuration"""
    try:
        data = request.json

        # Update activity XP values
        if "activity_xp" in data:
            for key, value in data["activity_xp"].items():
                if key in Config.XP_CONFIG:
                    Config.XP_CONFIG[key] = int(value)

        # Update level calculation
        if "level_calculation" in data:
            if "base_xp_per_level" in data["level_calculation"]:
                Config.XP_CONFIG["base_xp_per_level"] = int(data["level_calculation"]["base_xp_per_level"])
            if "xp_multiplier" in data["level_calculation"]:
                Config.XP_CONFIG["xp_multiplier"] = float(data["level_calculation"]["xp_multiplier"])

        # Update cooldowns
        if "cooldowns" in data:
            if "message_cooldown" in data["cooldowns"]:
                Config.XP_CONFIG["message_cooldown"] = int(data["cooldowns"]["message_cooldown"])
            if "meme_fetch_cooldown" in data["cooldowns"]:
                Config.XP_CONFIG["meme_fetch_cooldown"] = int(data["cooldowns"]["meme_fetch_cooldown"])
            if "daily_xp_cap" in data["cooldowns"]:
                Config.XP_CONFIG["daily_xp_cap"] = int(data["cooldowns"]["daily_xp_cap"])

        # Save to file
        save_config_to_file()

        log_action(request.username, "update_xp_config", {"updated_fields": list(data.keys())})

        return jsonify({"success": True, "message": "XP config updated successfully"})

    except Exception as e:
        import traceback

        logger.error(f"Error updating XP config: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to update XP config: {str(e)}"}), 500


@config_bp.route("/api/config/xp/reset", methods=["POST"])
def reset_xp_config():
    """Reset XP System Configuration to defaults"""
    try:
        # Reset to default values (from Config.py initial state)
        Config.XP_CONFIG = {
            # Activity XP
            "message_sent": 2,
            "image_sent": 5,
            "ticket_created": 10,
            "game_request": 8,
            # Meme Activities (REBALANCED - 12. Dez 2025)
            "meme_fetch": 2,
            "meme_post": 5,
            "meme_generate": 10,
            "meme_generate_post": 8,
            # Legacy XP types (kept for backward compatibility)
            "meme_fetched": 2,  # Alias for meme_fetch
            "meme_generated": 10,  # Alias for meme_generate
            # Rocket League XP
            "rl_account_linked": 20,
            "rl_stats_checked": 5,
            # Mod Activities (Extra XP)
            "ticket_resolved": 25,
            "ticket_claimed": 15,
            # Community Posts & Engagement (16. Dez 2025)
            "community_post_create": 15,
            "community_post_like": 2,
            "meme_like": 2,
            # Level Calculation
            "base_xp_per_level": 100,
            "xp_multiplier": 1.5,
            # Cooldowns (Spam-Prevention)
            "message_cooldown": 60,
            "meme_fetch_cooldown": 30,
            "community_post_cooldown": 300,
            "community_post_like_cooldown": 10,
            "meme_like_cooldown": 10,
            "daily_xp_cap": 500,
        }

        # Save to file
        save_config_to_file()

        return jsonify({"success": True, "message": "XP config reset to defaults successfully"})

    except Exception as e:
        import traceback

        logger.error(f"Error resetting XP config: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to reset XP config: {str(e)}"}), 500
