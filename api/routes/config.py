"""
Configuration-related routes blueprint.
"""

from flask import Blueprint, jsonify, request

import Config
from api.utils.audit import log_config_action
from api.utils.auth import require_permission, token_required
from api.utils.config_helpers import save_config_to_file

config_bp = Blueprint("config", __name__)


@config_bp.route("/api/config", methods=["GET"])
@token_required
@require_permission("all")
def get_config():
    """Get all bot configuration"""
    bot = config_bp.app.config.get("bot_instance") if hasattr(config_bp, "app") else None  # type: ignore[attr-defined]
    subreddits = []
    lemmy_communities = []
    daily_meme_config = {}

    if bot:
        daily_meme_cog = bot.get_cog("DailyMeme")
        if daily_meme_cog:
            subreddits = daily_meme_cog.meme_subreddits
            lemmy_communities = daily_meme_cog.meme_lemmy
            daily_meme_config = daily_meme_cog.daily_config.copy()
            if "channel_id" in daily_meme_config and daily_meme_config["channel_id"]:
                daily_meme_config["channel_id"] = str(daily_meme_config["channel_id"])
            if "role_id" in daily_meme_config and daily_meme_config["role_id"]:
                daily_meme_config["role_id"] = str(daily_meme_config["role_id"])

    config_data = {
        "general": {
            "bot_name": Config.BotName,
            "command_prefix": Config.CommandPrefix,
            "presence_update_interval": Config.PresenceUpdateInterval,
            "message_cooldown": Config.MessageCooldown,
            "fuzzy_matching_threshold": Config.FuzzyMatchingThreshold,
            "prod_mode": Config.PROD_MODE,
        },
        "logging": {
            "log_level": Config.LogLevel,
            "cog_log_levels": Config.COG_LOG_LEVELS,
        },
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
        "channels": {
            "log_channel_id": str(Config.LOG_CHANNEL_ID) if Config.LOG_CHANNEL_ID else None,
            "changelog_channel_id": str(Config.CHANGELOG_CHANNEL_ID) if Config.CHANGELOG_CHANNEL_ID else None,
            "todo_channel_id": str(Config.TODO_CHANNEL_ID) if Config.TODO_CHANNEL_ID else None,
            "rl_channel_id": str(Config.RL_CHANNEL_ID) if Config.RL_CHANNEL_ID else None,
            "meme_channel_id": str(Config.MEME_CHANNEL_ID) if Config.MEME_CHANNEL_ID else None,
            "server_guide_channel_id": str(Config.SERVER_GUIDE_CHANNEL_ID) if Config.SERVER_GUIDE_CHANNEL_ID else None,
            "welcome_rules_channel_id": str(Config.WELCOME_RULES_CHANNEL_ID)
            if Config.WELCOME_RULES_CHANNEL_ID
            else None,
            "welcome_public_channel_id": str(Config.WELCOME_PUBLIC_CHANNEL_ID)
            if Config.WELCOME_PUBLIC_CHANNEL_ID
            else None,
            "transcript_channel_id": str(Config.TRANSCRIPT_CHANNEL_ID) if Config.TRANSCRIPT_CHANNEL_ID else None,
            "tickets_category_id": str(Config.TICKETS_CATEGORY_ID) if Config.TICKETS_CATEGORY_ID else None,
        },
        "rocket_league": {
            "rank_check_interval_hours": Config.RL_RANK_CHECK_INTERVAL_HOURS,
            "rank_cache_ttl_seconds": Config.RL_RANK_CACHE_TTL_SECONDS,
        },
        "rocket_league_texts": {
            "promotion_config": Config.RL_RANK_PROMOTION_CONFIG,
            "congrats_replies": Config.RL_CONGRATS_REPLIES,
        },
        "meme": {
            "default_subreddits": Config.DEFAULT_MEME_SUBREDDITS,
            "default_lemmy": Config.DEFAULT_MEME_LEMMY,
            "meme_sources": Config.MEME_SOURCES,
            "templates_cache_duration": Config.MEME_TEMPLATES_CACHE_DURATION,
            "subreddits": subreddits,
            "lemmy_communities": lemmy_communities,
            "daily_config": daily_meme_config,
        },
    }

    return jsonify(config_data)


@config_bp.route("/api/config/general", methods=["GET", "PUT"])
@token_required
@require_permission("all")
@log_config_action("general")
def config_general():
    """Get or update general bot configuration"""
    if request.method == "GET":
        return jsonify(
            {
                "bot_name": Config.BotName,
                "command_prefix": Config.CommandPrefix,
                "presence_update_interval": Config.PresenceUpdateInterval,
                "message_cooldown": Config.MessageCooldown,
                "fuzzy_matching_threshold": Config.FuzzyMatchingThreshold,
                "pink_color": Config.PINK.value if hasattr(Config.PINK, "value") else 0xAD1457,
                "embed_footer_text": Config.EMBED_FOOTER_TEXT if hasattr(Config, "EMBED_FOOTER_TEXT") else "",
                "prod_mode": Config.PROD_MODE,
            }
        )

    data = request.get_json()

    if "bot_name" in data:
        Config.BotName = data["bot_name"]
    if "command_prefix" in data:
        Config.CommandPrefix = data["command_prefix"]
    if "presence_update_interval" in data:
        Config.PresenceUpdateInterval = int(data["presence_update_interval"])
    if "message_cooldown" in data:
        Config.MessageCooldown = int(data["message_cooldown"])
    if "fuzzy_matching_threshold" in data:
        Config.FuzzyMatchingThreshold = float(data["fuzzy_matching_threshold"])
    if "pink_color" in data:
        try:
            Config.PINK = int(data["pink_color"])  # type: ignore[assignment]
        except Exception:
            pass
    if "embed_footer_text" in data:
        Config.EMBED_FOOTER_TEXT = data["embed_footer_text"]
    if "prod_mode" in data:
        Config.PROD_MODE = bool(data["prod_mode"])

    save_config_to_file()
    return jsonify({"success": True, "message": "General configuration updated"})


@config_bp.route("/api/config/general/reset", methods=["POST"])
@token_required
@require_permission("all")
def reset_general_config():
    """Reset general config to defaults"""
    Config.BotName = "HazeBot"
    Config.CommandPrefix = "!"
    Config.PresenceUpdateInterval = 60
    Config.MessageCooldown = 3
    Config.FuzzyMatchingThreshold = 0.65
    save_config_to_file()
    return jsonify({"success": True, "message": "General configuration reset to defaults"})


@config_bp.route("/api/config/channels", methods=["GET", "PUT"])
@token_required
@require_permission("all")
@log_config_action("channels")
def config_channels():
    """Get or update channel configuration"""
    if request.method == "GET":
        return jsonify(
            {
                "log_channel_id": str(Config.LOG_CHANNEL_ID) if Config.LOG_CHANNEL_ID else None,
                "changelog_channel_id": str(Config.CHANGELOG_CHANNEL_ID) if Config.CHANGELOG_CHANNEL_ID else None,
                "todo_channel_id": str(Config.TODO_CHANNEL_ID) if Config.TODO_CHANNEL_ID else None,
                "rl_channel_id": str(Config.RL_CHANNEL_ID) if Config.RL_CHANNEL_ID else None,
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
            }
        )

    data = request.get_json()
    int_fields = [
        "log_channel_id",
        "changelog_channel_id",
        "todo_channel_id",
        "rl_channel_id",
        "meme_channel_id",
        "server_guide_channel_id",
        "welcome_rules_channel_id",
        "welcome_public_channel_id",
        "transcript_channel_id",
        "tickets_category_id",
    ]
    for field in int_fields:
        if field in data:
            try:
                setattr(Config, field.upper(), int(data[field]))
            except Exception:
                pass

    save_config_to_file()
    return jsonify({"success": True, "message": "Channel configuration updated"})


@config_bp.route("/api/config/channels/reset", methods=["POST"])
@token_required
@require_permission("all")
def reset_channels_config():
    """Reset channel IDs to defaults"""
    # This assumes defaults are stored in Config.CURRENT_IDS
    for key in [
        "LOG_CHANNEL_ID",
        "CHANGELOG_CHANNEL_ID",
        "TODO_CHANNEL_ID",
        "RL_CHANNEL_ID",
        "MEME_CHANNEL_ID",
        "SERVER_GUIDE_CHANNEL_ID",
        "WELCOME_RULES_CHANNEL_ID",
        "WELCOME_PUBLIC_CHANNEL_ID",
        "TRANSCRIPT_CHANNEL_ID",
        "TICKETS_CATEGORY_ID",
    ]:
        if key in Config.CURRENT_IDS:
            setattr(Config, key, Config.CURRENT_IDS[key])

    save_config_to_file()
    return jsonify({"success": True, "message": "Channel configuration reset to defaults"})


@config_bp.route("/api/config/roles", methods=["GET", "PUT"])
@token_required
@require_permission("all")
@log_config_action("roles")
def config_roles():
    """Get or update role configuration"""
    if request.method == "GET":
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

    data = request.get_json()
    for key, value in data.items():
        key_upper = key.upper()
        if key_upper in Config.CURRENT_IDS:
            try:
                if isinstance(value, list):
                    validated_list = []
                    for item in value:
                        item_int = int(item)
                        if item_int <= 0:
                            return jsonify({"error": f"Invalid role ID in {key}: must be positive"}), 400
                        validated_list.append(item_int)
                    Config.CURRENT_IDS[key_upper] = validated_list
                    setattr(Config, key_upper, validated_list)
                elif isinstance(value, dict):
                    validated_dict = {}
                    for k, v in value.items():
                        v_int = int(v)
                        if v_int <= 0:
                            return jsonify({"error": f"Invalid role ID for {k} in {key}: must be positive"}), 400
                        validated_dict[k] = v_int
                    Config.CURRENT_IDS[key_upper] = validated_dict
                    setattr(Config, key_upper, validated_dict)
                else:
                    role_id = int(value)
                    if role_id <= 0:
                        return jsonify({"error": f"Invalid role ID for {key}: must be positive"}), 400
                    Config.CURRENT_IDS[key_upper] = role_id
                    setattr(Config, key_upper, role_id)
            except (ValueError, TypeError):
                return jsonify({"error": f"Invalid role ID for {key}: must be integer(s)"}), 400

    save_config_to_file()
    return jsonify({"success": True, "message": "Role configuration updated"})


@config_bp.route("/api/config/roles/reset", methods=["POST"])
@token_required
@require_permission("all")
def reset_roles_config():
    """Reset all role IDs to defaults"""
    Config.ADMIN_ROLE_ID = Config.CURRENT_IDS["ADMIN_ROLE_ID"]
    Config.MODERATOR_ROLE_ID = Config.CURRENT_IDS["MODERATOR_ROLE_ID"]
    Config.NORMAL_ROLE_ID = Config.CURRENT_IDS["NORMAL_ROLE_ID"]
    Config.MEMBER_ROLE_ID = Config.CURRENT_IDS["MEMBER_ROLE_ID"]
    Config.CHANGELOG_ROLE_ID = Config.CURRENT_IDS["CHANGELOG_ROLE_ID"]
    Config.MEME_ROLE_ID = Config.CURRENT_IDS.get("MEME_ROLE_ID")
    save_config_to_file()
    return jsonify({"success": True, "message": "Roles configuration reset to defaults"})


@config_bp.route("/api/config/meme", methods=["GET", "PUT"])
@token_required
@require_permission("all")
@log_config_action("meme")
def config_meme():
    """Get or update meme configuration"""
    if request.method == "GET":
        bot = config_bp.app.config.get("bot_instance") if hasattr(config_bp, "app") else None  # type: ignore[attr-defined]
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

    data = request.get_json()
    if "default_subreddits" in data:
        Config.DEFAULT_MEME_SUBREDDITS = data["default_subreddits"]
    if "default_lemmy" in data:
        Config.DEFAULT_MEME_LEMMY = data["default_lemmy"]
    if "meme_sources" in data:
        Config.MEME_SOURCES = data["meme_sources"]
    if "templates_cache_duration" in data:
        Config.MEME_TEMPLATES_CACHE_DURATION = int(data["templates_cache_duration"])
    save_config_to_file()
    return jsonify({"success": True, "message": "Meme configuration updated"})


@config_bp.route("/api/config/rocket_league", methods=["GET", "PUT"])
@token_required
@require_permission("all")
@log_config_action("rocket_league")
def config_rocket_league():
    """Get or update Rocket League configuration"""
    if request.method == "GET":
        return jsonify(
            {
                "rank_check_interval_hours": Config.RL_RANK_CHECK_INTERVAL_HOURS,
                "rank_cache_ttl_seconds": Config.RL_RANK_CACHE_TTL_SECONDS,
            }
        )

    data = request.get_json()
    if "rank_check_interval_hours" in data:
        Config.RL_RANK_CHECK_INTERVAL_HOURS = int(data["rank_check_interval_hours"])
    if "rank_cache_ttl_seconds" in data:
        Config.RL_RANK_CACHE_TTL_SECONDS = int(data["rank_cache_ttl_seconds"])
    save_config_to_file()
    return jsonify({"success": True, "message": "Rocket League configuration updated"})


@config_bp.route("/api/config/rocket_league/reset", methods=["POST"])
@token_required
@require_permission("all")
def reset_rocket_league_config():
    """Reset Rocket League configuration to default values"""
    Config.RL_RANK_CHECK_INTERVAL_HOURS = 3
    Config.RL_RANK_CACHE_TTL_SECONDS = 10500
    save_config_to_file()
    return jsonify({"success": True, "message": "Rocket League configuration reset to defaults"})


@config_bp.route("/api/config/welcome", methods=["GET", "PUT"])
@token_required
@require_permission("all")
@log_config_action("welcome")
def config_welcome():
    """Get or update welcome configuration"""
    if request.method == "GET":
        return jsonify({"rules_text": Config.RULES_TEXT, "welcome_messages": Config.WELCOME_MESSAGES})

    data = request.get_json()
    if "rules_text" in data:
        Config.RULES_TEXT = data["rules_text"]
    if "welcome_messages" in data:
        Config.WELCOME_MESSAGES = data["welcome_messages"]
    save_config_to_file()
    return jsonify({"success": True, "message": "Welcome configuration updated"})


@config_bp.route("/api/config/welcome/reset", methods=["POST"])
@token_required
@require_permission("all")
def reset_welcome_config():
    """Reset welcome config to defaults"""
    Config.RULES_TEXT = Config.CURRENT_RULES_TEXT
    Config.WELCOME_MESSAGES = Config.CURRENT_WELCOME_MESSAGES
    save_config_to_file()
    return jsonify({"success": True, "message": "Welcome configuration reset to defaults"})


@config_bp.route("/api/config/welcome_texts", methods=["GET", "PUT"])
@token_required
@require_permission("all")
@log_config_action("welcome_texts")
def config_welcome_texts():
    """Get or update welcome texts"""
    if request.method == "GET":
        return jsonify({"welcome_button_replies": Config.WELCOME_BUTTON_REPLIES})

    data = request.get_json()
    if "welcome_button_replies" in data:
        Config.WELCOME_BUTTON_REPLIES = data["welcome_button_replies"]
    save_config_to_file()
    return jsonify({"success": True, "message": "Welcome texts updated"})


@config_bp.route("/api/config/welcome_texts/reset", methods=["POST"])
@token_required
@require_permission("all")
def reset_welcome_texts():
    """Reset welcome texts to defaults"""
    Config.WELCOME_BUTTON_REPLIES = Config.CURRENT_WELCOME_BUTTON_REPLIES
    save_config_to_file()
    return jsonify({"success": True, "message": "Welcome texts reset to defaults"})


@config_bp.route("/api/config/rocket_league_texts", methods=["GET", "PUT"])
@token_required
@require_permission("all")
@log_config_action("rocket_league_texts")
def config_rl_texts():
    """Get or update rocket league texts"""
    if request.method == "GET":
        return jsonify(
            {
                "promotion_config": Config.RL_RANK_PROMOTION_CONFIG,
                "congrats_replies": Config.RL_CONGRATS_REPLIES,
            }
        )

    data = request.get_json()
    if "promotion_config" in data:
        Config.RL_RANK_PROMOTION_CONFIG = data["promotion_config"]
    if "congrats_replies" in data:
        Config.RL_CONGRATS_REPLIES = data["congrats_replies"]
    save_config_to_file()
    return jsonify({"success": True, "message": "Rocket league texts updated"})


@config_bp.route("/api/config/rocket_league_texts/reset", methods=["POST"])
@token_required
@require_permission("all")
def reset_rl_texts():
    """Reset rocket league texts to defaults"""
    Config.RL_RANK_PROMOTION_CONFIG = Config.CURRENT_RL_RANK_PROMOTION_CONFIG
    Config.RL_CONGRATS_REPLIES = Config.CURRENT_RL_CONGRATS_REPLIES
    save_config_to_file()
    return jsonify({"success": True, "message": "Rocket league texts reset to defaults"})


@config_bp.route("/api/config/server_guide", methods=["GET", "PUT"])
@token_required
@require_permission("all")
@log_config_action("server_guide")
def config_server_guide():
    """Get or update server guide configuration"""
    if request.method == "GET":
        return jsonify(Config.SERVER_GUIDE_CONFIG)

    data = request.get_json()
    Config.SERVER_GUIDE_CONFIG.update(data)
    save_config_to_file()
    return jsonify({"success": True, "message": "Server guide configuration updated"})
