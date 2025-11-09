"""
Flask API for HazeBot Configuration
Provides REST endpoints to read and update bot configuration
"""

import os
import json
import sys
import logging
from pathlib import Path
from flask import Flask, jsonify, request, redirect
from flask_cors import CORS
import jwt
from datetime import datetime, timedelta
from functools import wraps
import requests
from urllib.parse import urlencode

# Add parent directory to path to import Config
sys.path.insert(0, str(Path(__file__).parent.parent))
import Config
from Utils.ConfigLoader import load_config_from_file

app = Flask(__name__)
CORS(app)  # Enable CORS for Flutter web


# Configure logging - suppress 200 OK responses
class NoSuccessRequestsFilter(logging.Filter):
    def filter(self, record):
        # Filter out successful requests (200 OK)
        msg = record.getMessage()
        # Check if it's a 200 response with any HTTP method
        if " 200 " in msg and any(
            method in msg for method in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        ):
            return False
        return True


# Apply filter to werkzeug logger (Flask's request logger)
werkzeug_logger = logging.getLogger("werkzeug")
werkzeug_logger.addFilter(NoSuccessRequestsFilter())

# Secret key for JWT (should be in environment variable in production)
app.config["SECRET_KEY"] = os.getenv("API_SECRET_KEY", "dev-secret-key-change-in-production")


# Audit logging setup
def log_action(username, action, details=None):
    """Log user actions to file and console"""
    from Utils.Logger import Logger

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "username": username,
        "action": action,
        "details": details or {},
    }

    # Log to console
    Logger.info(f"🔧 [API Action] {username} - {action}" + (f" | {details}" if details else ""))

    # Log to audit file
    audit_log_path = Path(__file__).parent.parent / "Logs" / "api_audit.log"
    audit_log_path.parent.mkdir(exist_ok=True)

    with open(audit_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")


# Decorator for logging config updates
def log_config_action(config_name):
    """Decorator to automatically log configuration changes"""

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Get the request data before processing
            if request.method in ["PUT", "POST"] and request.is_json:
                data = request.get_json()
                action_type = "update" if request.method == "PUT" else "reset" if "reset" in request.path else "action"
                log_action(
                    request.username,
                    f"{action_type}_{config_name}_config",
                    {"keys_modified": list(data.keys()) if data else []},
                )
            elif request.method == "POST" and "reset" in request.path:
                log_action(request.username, f"reset_{config_name}_config", {"status": "reset to defaults"})

            return f(*args, **kwargs)

        return wrapper

    return decorator


# Simple authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")

        if not token:
            return jsonify({"error": "Token is missing"}), 401

        try:
            if token.startswith("Bearer "):
                token = token[7:]
            data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            # Store username and permissions in request context
            request.username = data.get("user", "unknown")
            request.user_role = data.get("role", "admin")
            request.user_permissions = data.get("permissions", ["all"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token is invalid"}), 401
        except Exception:
            # Don't expose internal error details to avoid information leakage
            return jsonify({"error": "Token validation failed"}), 401

        return f(*args, **kwargs)

    return decorated


# Permission checking decorator
def require_permission(permission):
    """Decorator to check if user has required permission"""

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user_permissions = getattr(request, "user_permissions", [])

            # Admin/mod with 'all' permission can access everything
            if "all" in user_permissions:
                return f(*args, **kwargs)

            # Check specific permission
            if permission not in user_permissions:
                return jsonify({"error": "Insufficient permissions"}), 403

            return f(*args, **kwargs)

        return wrapper

    return decorator


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@app.route("/api/auth/login", methods=["POST"])
def login():
    """Simple authentication endpoint"""
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    # Build valid users dictionary from environment variables
    valid_users = {os.getenv("API_ADMIN_USER", "admin"): os.getenv("API_ADMIN_PASS", "changeme")}

    # Add extra users from API_EXTRA_USERS (format: username:password,username2:password2)
    extra_users = os.getenv("API_EXTRA_USERS", "")
    if extra_users:
        for user_entry in extra_users.split(","):
            user_entry = user_entry.strip()
            if ":" in user_entry:
                user, pwd = user_entry.split(":", 1)
                valid_users[user.strip()] = pwd.strip()

    if username in valid_users and password == valid_users[username]:
        token = jwt.encode(
            {
                "user": username,
                "exp": datetime.utcnow() + timedelta(hours=24),
                "role": "admin",
                "permissions": ["all"],
                "auth_type": "legacy",
            },
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )

        return jsonify({"token": token, "user": username, "role": "admin", "permissions": ["all"]})

    return jsonify({"error": "Invalid credentials"}), 401


# Discord OAuth2 Configuration
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "https://test-hazebot-admin.hzwd.xyz/auth/callback")
DISCORD_API_ENDPOINT = "https://discord.com/api/v10"

# Role-based permissions
ROLE_PERMISSIONS = {
    "admin": ["all"],
    "mod": ["all"],
    "lootling": ["meme_generator"],
}


def get_user_role_from_discord(member_data, guild_id):
    """Determine user role based on Discord guild roles"""
    role_ids = member_data.get("roles", [])

    # Get bot instance to fetch role IDs from Config
    bot = app.config.get("bot_instance")
    if not bot:
        return "lootling"

    # Get role IDs from Config
    admin_role_id = str(Config.ADMIN_ROLE_ID)
    mod_role_id = str(Config.MODERATOR_ROLE_ID)

    # Check for admin/mod roles
    if admin_role_id in role_ids:
        return "admin"
    elif mod_role_id in role_ids:
        return "mod"
    else:
        return "lootling"


@app.route("/api/discord/auth", methods=["GET"])
def discord_auth():
    """Initiate Discord OAuth2 flow"""
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds.members.read",
    }

    auth_url = f"{DISCORD_API_ENDPOINT}/oauth2/authorize?{urlencode(params)}"
    return jsonify({"auth_url": auth_url})


@app.route("/api/discord/callback", methods=["GET"])
def discord_callback():
    """Handle Discord OAuth2 callback"""
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "No authorization code provided"}), 400

    # Exchange code for access token
    token_data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    token_response = requests.post(f"{DISCORD_API_ENDPOINT}/oauth2/token", data=token_data, headers=headers)

    if token_response.status_code != 200:
        return jsonify({"error": "Failed to obtain access token"}), 400

    access_token = token_response.json().get("access_token")

    # Get user info
    user_headers = {"Authorization": f"Bearer {access_token}"}
    user_response = requests.get(f"{DISCORD_API_ENDPOINT}/users/@me", headers=user_headers)

    if user_response.status_code != 200:
        return jsonify({"error": "Failed to get user info"}), 400

    user_data = user_response.json()

    # Get guild member info to check roles
    guild_id = os.getenv("DISCORD_GUILD_ID") if os.getenv("PROD_MODE", "false").lower() == "true" else os.getenv("DISCORD_TEST_GUILD_ID")

    member_response = requests.get(
        f"{DISCORD_API_ENDPOINT}/users/@me/guilds/{guild_id}/member", headers=user_headers
    )

    if member_response.status_code != 200:
        return jsonify({"error": "User is not a member of the guild"}), 403

    member_data = member_response.json()

    # Determine role and permissions
    role = get_user_role_from_discord(member_data, guild_id)
    permissions = ROLE_PERMISSIONS.get(role, ["meme_generator"])

    # Create JWT token
    token = jwt.encode(
        {
            "user": user_data["username"],
            "discord_id": user_data["id"],
            "exp": datetime.utcnow() + timedelta(hours=24),
            "role": role,
            "permissions": permissions,
            "auth_type": "discord",
        },
        app.config["SECRET_KEY"],
        algorithm="HS256",
    )

    # Log the action
    log_action(user_data["username"], "discord_oauth_login", {"role": role, "permissions": permissions})

    # Detect if request is from mobile app (check 'state' parameter from OAuth flow)
    state = request.args.get("state", "")
    is_mobile_app = state == "mobile"

    if is_mobile_app:
        # Redirect to deep link for mobile app
        return redirect(f"hazebot://oauth?token={token}")
    else:
        # Redirect to frontend web URL with token
        frontend_url = "https://test-hazebot-admin.hzwd.xyz"
        return redirect(f"{frontend_url}?token={token}")


@app.route("/api/auth/me", methods=["GET"])
@token_required
def get_current_user():
    """Get current user info from JWT token"""
    token = request.headers.get("Authorization")
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        return jsonify(
            {
                "user": data.get("user"),
                "discord_id": data.get("discord_id"),
                "role": data.get("role", "admin"),
                "permissions": data.get("permissions", ["all"]),
                "auth_type": data.get("auth_type", "legacy"),
            }
        )
    except Exception as e:
        return jsonify({"error": "Invalid token"}), 401


@app.route("/api/config", methods=["GET"])
@token_required
@require_permission("all")
def get_config():
    """Get all bot configuration"""
    # Try to get actual subreddits/lemmy from DailyMeme cog
    bot = app.config.get("bot_instance")
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
            "guild_name": getattr(Config, "GUILD_NAME", None),  # Optional: Add GUILD_NAME to Config.py
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
            "welcome_rules_channel_id": str(Config.WELCOME_RULES_CHANNEL_ID) if Config.WELCOME_RULES_CHANNEL_ID else None,
            "welcome_public_channel_id": str(Config.WELCOME_PUBLIC_CHANNEL_ID) if Config.WELCOME_PUBLIC_CHANNEL_ID else None,
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


@app.route("/api/config/general", methods=["GET", "PUT"])
@token_required
@require_permission("all")
def config_general():
    """Get or update general configuration"""
    if request.method == "GET":
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

        # Save to file
        save_config_to_file()

        # Log the action
        log_action(request.username, "update_general_config", {"changes": changes})

        return jsonify({"success": True, "message": "Configuration updated"})


@app.route("/api/config/general/reset", methods=["POST"])
@token_required
@require_permission("all")
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

    # Save to file
    save_config_to_file()

    # Log the action
    log_action(request.username, "reset_general_config", {"status": "reset to defaults"})

    return jsonify({"success": True, "message": "General configuration reset to defaults"})


@app.route("/api/config/channels", methods=["GET", "PUT"])
@token_required
@require_permission("all")
@log_config_action("channels")
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
                "meme_channel_id": str(Config.MEME_CHANNEL_ID) if Config.MEME_CHANNEL_ID else None,
                "server_guide_channel_id": str(Config.SERVER_GUIDE_CHANNEL_ID) if Config.SERVER_GUIDE_CHANNEL_ID else None,
                "welcome_rules_channel_id": str(Config.WELCOME_RULES_CHANNEL_ID) if Config.WELCOME_RULES_CHANNEL_ID else None,
                "welcome_public_channel_id": str(Config.WELCOME_PUBLIC_CHANNEL_ID) if Config.WELCOME_PUBLIC_CHANNEL_ID else None,
                "transcript_channel_id": str(Config.TRANSCRIPT_CHANNEL_ID) if Config.TRANSCRIPT_CHANNEL_ID else None,
                "tickets_category_id": str(Config.TICKETS_CATEGORY_ID) if Config.TICKETS_CATEGORY_ID else None,
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


@app.route("/api/config/channels/reset", methods=["POST"])
@token_required
@require_permission("all")
def reset_channels_config():
    """Reset channels configuration to default values"""
    # Reset to default values from CURRENT_IDS (which is already set based on PROD_MODE)
    Config.LOG_CHANNEL_ID = Config.CURRENT_IDS["LOG_CHANNEL_ID"]
    Config.CHANGELOG_CHANNEL_ID = Config.CURRENT_IDS["CHANGELOG_CHANNEL_ID"]
    Config.TODO_CHANNEL_ID = Config.CURRENT_IDS["TODO_CHANNEL_ID"]
    Config.RL_CHANNEL_ID = Config.CURRENT_IDS["RL_CHANNEL_ID"]
    Config.MEME_CHANNEL_ID = Config.CURRENT_IDS.get("MEME_CHANNEL_ID")
    Config.SERVER_GUIDE_CHANNEL_ID = Config.CURRENT_IDS.get("SERVER_GUIDE_CHANNEL_ID")
    Config.WELCOME_RULES_CHANNEL_ID = Config.CURRENT_IDS["WELCOME_RULES_CHANNEL_ID"]
    Config.WELCOME_PUBLIC_CHANNEL_ID = Config.CURRENT_IDS["WELCOME_PUBLIC_CHANNEL_ID"]
    Config.TRANSCRIPT_CHANNEL_ID = Config.CURRENT_IDS["TRANSCRIPT_CHANNEL_ID"]
    Config.TICKETS_CATEGORY_ID = Config.CURRENT_IDS["TICKETS_CATEGORY_ID"]

    # Save to file
    save_config_to_file()

    return jsonify({"success": True, "message": "Channels configuration reset to defaults"})


@app.route("/api/config/roles", methods=["GET", "PUT"])
@token_required
@require_permission("all")
@log_config_action("roles")
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
                "interest_roles": {k: str(v) if v else None for k, v in Config.INTEREST_ROLES.items()} if Config.INTEREST_ROLES else {},
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


@app.route("/api/config/roles/reset", methods=["POST"])
@token_required
@require_permission("all")
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


@app.route("/api/config/meme", methods=["GET", "PUT"])
@token_required
@require_permission("all")
@log_config_action("meme")
def config_meme():
    """Get or update meme configuration"""
    if request.method == "GET":
        # Try to get actual subreddits/lemmy from DailyMeme cog
        bot = app.config.get("bot_instance")
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


@app.route("/api/config/rocket_league", methods=["GET", "PUT"])
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

    if request.method == "PUT":
        data = request.get_json()

        print(f"🔍 DEBUG API: Received RL config update: {data}")

        if "rank_check_interval_hours" in data:
            Config.RL_RANK_CHECK_INTERVAL_HOURS = int(data["rank_check_interval_hours"])
            print(f"✅ API: Set RL_RANK_CHECK_INTERVAL_HOURS to {Config.RL_RANK_CHECK_INTERVAL_HOURS}")
        if "rank_cache_ttl_seconds" in data:
            Config.RL_RANK_CACHE_TTL_SECONDS = int(data["rank_cache_ttl_seconds"])
            print(f"✅ API: Set RL_RANK_CACHE_TTL_SECONDS to {Config.RL_RANK_CACHE_TTL_SECONDS}")

        # Save to file
        print("💾 API: Saving config to file...")
        save_config_to_file()

        return jsonify({"success": True, "message": "Rocket League configuration updated"})


@app.route("/api/config/rocket_league/reset", methods=["POST"])
@token_required
@require_permission("all")
def reset_rocket_league_config():
    """Reset Rocket League configuration to default values"""
    # Reset to default values from Config.py
    Config.RL_RANK_CHECK_INTERVAL_HOURS = 3
    Config.RL_RANK_CACHE_TTL_SECONDS = 10500  # 2h 55min

    # Save to file
    save_config_to_file()

    return jsonify({"success": True, "message": "Rocket League configuration reset to defaults"})


@app.route("/api/rocket-league/accounts", methods=["GET"])
@token_required
@require_permission("all")
def get_rl_accounts():
    """Get all linked Rocket League accounts"""
    try:
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        rl_cog = bot.get_cog("RocketLeague")
        if not rl_cog:
            return jsonify({"error": "RocketLeague cog not loaded"}), 503

        # Import the load function from the cog's module
        from Cogs.RocketLeague import load_rl_accounts

        accounts = load_rl_accounts()

        # Enrich with Discord user information
        enriched_accounts = []
        for user_id, data in accounts.items():
            user = bot.get_user(int(user_id))
            enriched_accounts.append(
                {
                    "user_id": user_id,
                    "username": user.name if user else "Unknown User",
                    "display_name": user.display_name if user else "Unknown User",
                    "avatar_url": str(user.avatar.url) if user and user.avatar else None,
                    "platform": data.get("platform"),
                    "rl_username": data.get("username"),
                    "ranks": data.get("ranks", {}),
                    "rank_display": data.get("rank_display", {}),
                    "icon_urls": data.get("icon_urls", {}),
                    "last_fetched": data.get("last_fetched"),
                }
            )

        return jsonify(enriched_accounts)
    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to get RL accounts: {str(e)}", "details": traceback.format_exc()}), 500


@app.route("/api/rocket-league/accounts/<user_id>", methods=["DELETE"])
@token_required
@require_permission("all")
def delete_rl_account(user_id):
    """Delete/unlink a Rocket League account (admin function)"""
    try:
        from Cogs.RocketLeague import load_rl_accounts, save_rl_accounts

        accounts = load_rl_accounts()

        if user_id not in accounts:
            return jsonify({"error": "Account not found"}), 404

        # Get username for logging
        rl_username = accounts[user_id].get("username", "Unknown")

        # Delete the account
        del accounts[user_id]
        save_rl_accounts(accounts)

        return jsonify(
            {
                "success": True,
                "message": f"Successfully unlinked account for user {user_id} (RL: {rl_username})",
            }
        )
    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to delete RL account: {str(e)}", "details": traceback.format_exc()}), 500


@app.route("/api/rocket-league/check-ranks", methods=["POST"])
@token_required
@require_permission("all")
def trigger_rank_check():
    """Manually trigger rank check for all linked accounts"""
    try:
        import asyncio

        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        rl_cog = bot.get_cog("RocketLeague")
        if not rl_cog:
            return jsonify({"error": "RocketLeague cog not loaded"}), 503

        # Use the bot's existing event loop
        loop = bot.loop

        # Call the rank check function with force=True
        future = asyncio.run_coroutine_threadsafe(rl_cog._check_and_update_ranks(force=True), loop)

        # Wait for result with timeout
        future.result(timeout=120)  # 2 minutes timeout

        return jsonify(
            {
                "success": True,
                "message": "Rank check completed successfully",
                "note": "Check the RL channel for any rank promotion notifications",
            }
        )
    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to check ranks: {str(e)}", "details": traceback.format_exc()}), 500


@app.route("/api/rocket-league/stats/<platform>/<username>", methods=["GET"])
@token_required
@require_permission("all")
def get_rl_stats(platform, username):
    """Get Rocket League stats for a specific player"""
    try:
        import asyncio

        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        rl_cog = bot.get_cog("RocketLeague")
        if not rl_cog:
            return jsonify({"error": "RocketLeague cog not loaded"}), 503

        # Validate platform
        if platform.lower() not in ["steam", "epic", "psn", "xbl", "switch"]:
            return jsonify({"error": "Invalid platform. Use: steam, epic, psn, xbl, or switch"}), 400

        # Use the bot's existing event loop
        loop = bot.loop

        # Fetch stats using the bot's function
        future = asyncio.run_coroutine_threadsafe(rl_cog.get_player_stats(platform.lower(), username), loop)

        # Wait for result with timeout
        stats = future.result(timeout=90)

        if not stats:
            return jsonify({"error": "Player not found or error fetching stats"}), 404

        return jsonify(
            {
                "success": True,
                "stats": {
                    "username": stats["username"],
                    "platform": platform.upper(),
                    "rank_1v1": stats["rank_1v1"],
                    "rank_2v2": stats["rank_2v2"],
                    "rank_3v3": stats["rank_3v3"],
                    "rank_4v4": stats.get("rank_4v4", "N/A"),
                    "season_reward": stats["season_reward"],
                    "highest_icon_url": stats.get("highest_icon_url"),
                    "tier_names": stats.get("tier_names", {}),
                    "rank_display": stats.get("rank_display", {}),
                    "icon_urls": stats.get("icon_urls", {}),
                },
            }
        )
    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to fetch RL stats: {str(e)}", "details": traceback.format_exc()}), 500


@app.route("/api/config/welcome", methods=["GET", "PUT"])
@token_required
@require_permission("all")
@log_config_action("welcome")
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


@app.route("/api/config/welcome/reset", methods=["POST"])
@token_required
@require_permission("all")
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


@app.route("/api/config/welcome_texts", methods=["GET", "PUT"])
@token_required
@require_permission("all")
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


@app.route("/api/config/welcome_texts/reset", methods=["POST"])
@token_required
@require_permission("all")
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


@app.route("/api/config/rocket_league_texts", methods=["GET", "PUT"])
@token_required
@require_permission("all")
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


@app.route("/api/config/rocket_league_texts/reset", methods=["POST"])
@token_required
@require_permission("all")
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


@app.route("/api/config/server_guide", methods=["GET", "PUT"])
@token_required
@require_permission("all")
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


# ===== LOGS ENDPOINTS =====


@app.route("/api/logs", methods=["GET"])
@token_required
@require_permission("all")
def get_logs():
    """Get bot logs with optional filtering"""
    try:
        # Query parameters
        cog_name = request.args.get("cog", None)  # Filter by cog name
        level = request.args.get("level", None)  # Filter by log level (INFO, WARNING, ERROR, DEBUG)
        limit = int(request.args.get("limit", 500))  # Number of lines to return
        search = request.args.get("search", None)  # Search term

        # Read log file
        log_file = Path(__file__).parent.parent / "Logs" / "HazeBot.log"

        if not log_file.exists():
            return jsonify({"error": "Log file not found", "logs": []}), 404

        # Read last N lines
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            lines = lines[-limit * 2 :]  # Read more to account for filtering

        # Parse and filter logs
        parsed_logs = []
        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue

            # Apply filters
            if cog_name and cog_name.lower() not in line.lower():
                continue

            if level and level.upper() not in line:
                continue

            if search and search.lower() not in line.lower():
                continue

            # Parse log line - format: [timestamp] emoji LEVEL | message
            # Example: [23:23:44] 💖  INFO    │ message
            try:
                # Extract timestamp
                timestamp_match = line.find("[")
                timestamp_end = line.find("]")
                timestamp = line[timestamp_match + 1 : timestamp_end] if timestamp_match != -1 else ""

                # Extract level
                level_match = None
                for log_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                    if log_level in line:
                        level_match = log_level
                        break

                # Extract message (everything after │ or after level)
                separator_idx = line.find("│")
                if separator_idx != -1:
                    message = line[separator_idx + 1 :].strip()
                else:
                    # Fallback: take everything after level
                    if level_match:
                        level_idx = line.find(level_match) + len(level_match)
                        message = line[level_idx:].strip()
                    else:
                        message = line.strip()

                parsed_logs.append(
                    {
                        "timestamp": timestamp,
                        "level": level_match or "INFO",
                        "message": message,
                        "raw": line.strip(),
                    }
                )
            except Exception:
                # If parsing fails, just include the raw line
                parsed_logs.append(
                    {
                        "timestamp": "",
                        "level": "UNKNOWN",
                        "message": line.strip(),
                        "raw": line.strip(),
                    }
                )

        # Limit final results
        parsed_logs = parsed_logs[-limit:]

        return jsonify(
            {
                "total": len(parsed_logs),
                "limit": limit,
                "filters": {
                    "cog": cog_name,
                    "level": level,
                    "search": search,
                },
                "logs": parsed_logs,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/logs/cogs", methods=["GET"])
@token_required
@require_permission("all")
def get_available_cogs():
    """Get list of available cogs for log filtering"""
    try:
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Get all loaded cogs
        cogs = sorted([cog for cog in bot.cogs.keys()])

        return jsonify({"cogs": cogs})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Test endpoints
@app.route("/api/meme-sources", methods=["GET"])
@token_required
def get_meme_sources():
    """Get available meme sources (subreddits and Lemmy communities)"""
    try:
        # Get bot instance
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Make sure to start with start_with_api.py"}), 503

        # Get DailyMeme cog
        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        return jsonify(
            {
                "success": True,
                "sources": {
                    "subreddits": list(daily_meme_cog.meme_subreddits),
                    "lemmy": list(daily_meme_cog.meme_lemmy),
                },
            }
        )

    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to get sources: {str(e)}", "details": traceback.format_exc()}), 500


# ===== MEME GENERATOR ENDPOINTS =====


@app.route("/api/meme-generator/templates", methods=["GET"])
@token_required
@require_permission("meme_generator")
def get_meme_templates():
    """Get available meme templates from Imgflip"""
    try:
        import asyncio

        # Get bot instance
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Make sure to start with start_with_api.py"}), 503

        # Get MemeGenerator cog
        meme_gen_cog = bot.get_cog("MemeGenerator")
        if not meme_gen_cog:
            return jsonify({"error": "MemeGenerator cog not loaded"}), 503

        # Check if credentials are configured
        from Config import IMGFLIP_USERNAME, IMGFLIP_PASSWORD

        if not IMGFLIP_USERNAME or not IMGFLIP_PASSWORD:
            return (
                jsonify(
                    {
                        "error": "Imgflip credentials not configured",
                        "details": "Bot administrator needs to configure IMGFLIP_USERNAME and IMGFLIP_PASSWORD",
                    }
                ),
                503,
            )

        # Get templates (use cached if available)
        loop = bot.loop

        # Ensure templates are loaded
        if not meme_gen_cog.templates:
            future = asyncio.run_coroutine_threadsafe(meme_gen_cog.fetch_templates(), loop)
            future.result(timeout=10)

        templates = meme_gen_cog.templates

        return jsonify(
            {
                "success": True,
                "templates": templates,
                "count": len(templates),
                "cached_since": meme_gen_cog.templates_last_fetched,
            }
        )

    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to get templates: {str(e)}", "details": traceback.format_exc()}), 500


@app.route("/api/meme-generator/templates/refresh", methods=["POST"])
@token_required
@require_permission("meme_generator")
def refresh_meme_templates():
    """Force refresh meme templates from Imgflip API"""
    try:
        import asyncio

        # Get bot instance
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Make sure to start with start_with_api.py"}), 503

        # Get MemeGenerator cog
        meme_gen_cog = bot.get_cog("MemeGenerator")
        if not meme_gen_cog:
            return jsonify({"error": "MemeGenerator cog not loaded"}), 503

        loop = bot.loop

        # Force fetch new templates
        future = asyncio.run_coroutine_threadsafe(meme_gen_cog.fetch_templates(force=True), loop)
        templates = future.result(timeout=10)

        return jsonify(
            {
                "success": True,
                "message": "Templates refreshed successfully",
                "count": len(templates),
                "timestamp": meme_gen_cog.templates_last_fetched,
            }
        )

    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to refresh templates: {str(e)}", "details": traceback.format_exc()}), 500


@app.route("/api/meme-generator/generate", methods=["POST"])
@token_required
@require_permission("meme_generator")
def generate_meme():
    """Generate a meme using Imgflip API"""
    try:
        import asyncio

        data = request.get_json()
        template_id = data.get("template_id")
        texts = data.get("texts", [])  # List of text strings

        if not template_id:
            return jsonify({"error": "template_id is required"}), 400

        # Get bot instance
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Make sure to start with start_with_api.py"}), 503

        # Get MemeGenerator cog
        meme_gen_cog = bot.get_cog("MemeGenerator")
        if not meme_gen_cog:
            return jsonify({"error": "MemeGenerator cog not loaded"}), 503

        loop = bot.loop

        # Generate meme based on text count
        if len(texts) <= 2:
            # Simple meme with top/bottom text
            text0 = texts[0] if len(texts) > 0 else ""
            text1 = texts[1] if len(texts) > 1 else ""
            future = asyncio.run_coroutine_threadsafe(meme_gen_cog.create_meme(template_id, text0, text1), loop)
        else:
            # Advanced meme with multiple text boxes
            text_params = {f"text{i}": text for i, text in enumerate(texts)}
            future = asyncio.run_coroutine_threadsafe(meme_gen_cog.create_meme_advanced(template_id, text_params), loop)

        meme_url = future.result(timeout=15)

        if not meme_url:
            return jsonify({"error": "Failed to generate meme"}), 500

        return jsonify({"success": True, "url": meme_url})

    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to generate meme: {str(e)}", "details": traceback.format_exc()}), 500


@app.route("/api/meme-generator/post-to-discord", methods=["POST"])
@token_required
@require_permission("meme_generator")
def post_generated_meme_to_discord():
    """Post a generated meme to Discord"""
    try:
        import asyncio

        data = request.get_json()
        meme_url = data.get("meme_url")
        template_name = data.get("template_name", "Custom Meme")
        texts = data.get("texts", [])

        if not meme_url:
            return jsonify({"error": "meme_url is required"}), 400

        # Get bot instance
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Make sure to start with start_with_api.py"}), 503

        # Get meme channel
        meme_channel_id = Config.MEME_CHANNEL_ID
        channel = bot.get_channel(meme_channel_id)
        if not channel:
            return jsonify({"error": f"Meme channel {meme_channel_id} not found"}), 404

        loop = bot.loop

        # Post the meme to Discord
        async def post_meme():
            import discord
            from datetime import datetime
            from Utils.EmbedUtils import set_pink_footer

            embed = discord.Embed(
                title=f"🎨 Custom Meme: {template_name}",
                color=Config.PINK,
                timestamp=datetime.now(),
            )
            embed.set_image(url=meme_url)

            # Add text fields if provided
            labels = ["🔝 Top Text", "🔽 Bottom Text", "⏺️ Middle Text", "📝 Text 4", "📝 Text 5"]
            for i, text in enumerate(texts):
                if text and text.strip():
                    label = labels[i] if i < len(labels) else f"📝 Text {i + 1}"
                    embed.add_field(name=label, value=text[:1024], inline=True)

            embed.add_field(name="🖥️ Created via", value="Admin Panel", inline=False)

            set_pink_footer(embed, bot=bot.user)

            await channel.send("🎨 New custom meme generated!", embed=embed)

        future = asyncio.run_coroutine_threadsafe(post_meme(), loop)
        future.result(timeout=30)

        return jsonify(
            {
                "success": True,
                "message": "Meme posted to Discord successfully",
                "channel_id": meme_channel_id,
            }
        )

    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to post meme to Discord: {str(e)}", "details": traceback.format_exc()}), 500


@app.route("/api/test/meme-from-source", methods=["GET"])
@token_required
def test_meme_from_source():
    """Get a meme from a specific source (subreddit or Lemmy community)"""
    try:
        import asyncio
        import random

        # Get source parameter
        source = request.args.get("source")
        if not source or not source.strip():
            return jsonify(
                {"error": "Missing 'source' parameter. Use subreddit name or lemmy community (instance@community)"}
            ), 400

        source = source.strip()

        # Get bot instance
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Make sure to start with start_with_api.py"}), 503

        # Get DailyMeme cog
        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        # Use the bot's existing event loop
        loop = bot.loop

        # Determine if it's Lemmy or Reddit
        if "@" in source:
            # Lemmy community
            lemmy_source = source.lower()
            if lemmy_source not in daily_meme_cog.meme_lemmy:
                available = list(daily_meme_cog.meme_lemmy)
                return jsonify(
                    {
                        "error": f"'{source}' is not configured as a Lemmy community",
                        "available_lemmy": available,
                    }
                ), 400

            # Fetch from Lemmy
            future = asyncio.run_coroutine_threadsafe(
                daily_meme_cog.fetch_lemmy_meme(lemmy_source),
                loop,
            )
            memes = future.result(timeout=30)
            source_display = lemmy_source
            source_type = "lemmy"

        else:
            # Reddit subreddit - normalize the input
            subreddit = source.lower().strip().replace("r/", "")

            if not subreddit:
                return jsonify({"error": "Empty subreddit name"}), 400

            if subreddit not in daily_meme_cog.meme_subreddits:
                available = list(daily_meme_cog.meme_subreddits)
                return jsonify(
                    {
                        "error": f"r/{subreddit} is not configured",
                        "available_subreddits": available,
                    }
                ), 400

            # Fetch from Reddit
            future = asyncio.run_coroutine_threadsafe(
                daily_meme_cog.fetch_reddit_meme(subreddit),
                loop,
            )
            memes = future.result(timeout=30)
            source_display = f"r/{subreddit}"
            source_type = "reddit"

        if not memes:
            return jsonify({"error": f"No memes found from {source_display}"}), 404

        # Pick random meme
        meme = random.choice(memes)

        return jsonify(
            {
                "success": True,
                "source": source_display,
                "source_type": source_type,
                "meme": {
                    "url": meme.get("url"),
                    "title": meme.get("title"),
                    "subreddit": meme.get("subreddit"),
                    "author": meme.get("author"),
                    "score": meme.get("score", meme.get("upvotes", 0)),
                    "nsfw": meme.get("nsfw", False),
                    "permalink": meme.get("permalink", ""),
                },
            }
        )

    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to fetch meme: {str(e)}", "details": traceback.format_exc()}), 500


@app.route("/api/test/random-meme", methods=["GET"])
@token_required
def test_random_meme():
    """Get a random meme from configured sources using the actual bot function"""
    try:
        import asyncio

        # Get bot instance
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Make sure to start with start_with_api.py"}), 503

        # Get DailyMeme cog
        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        # Use the bot's existing event loop instead of creating a new one
        loop = bot.loop

        # Create a future and schedule it on the bot's loop
        future = asyncio.run_coroutine_threadsafe(
            daily_meme_cog.get_daily_meme(
                allow_nsfw=False,  # Don't allow NSFW for admin panel
                max_sources=3,  # Fetch from 3 sources for speed
                min_score=50,  # Lower threshold for testing
                pool_size=25,  # Smaller pool for speed
            ),
            loop,
        )

        # Wait for result with timeout
        meme = future.result(timeout=30)

        if meme:
            return jsonify(
                {
                    "success": True,
                    "meme": {
                        "url": meme.get("url"),
                        "title": meme.get("title"),
                        "subreddit": meme.get("subreddit"),
                        "author": meme.get("author"),
                        "score": meme.get("upvotes", meme.get("score", 0)),
                        "nsfw": meme.get("nsfw", False),
                        "permalink": meme.get("permalink", ""),
                    },
                }
            )
        else:
            return jsonify({"error": "No suitable memes found"}), 404

    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to get random meme: {str(e)}", "details": traceback.format_exc()}), 500


@app.route("/api/proxy/image", methods=["GET"])
def proxy_image():
    """Proxy external images to bypass CORS restrictions"""
    try:
        # Get the image URL from query parameter
        image_url = request.args.get("url")
        if not image_url:
            return jsonify({"error": "Missing 'url' parameter"}), 400
        
        # Validate URL is from allowed domains (security measure)
        allowed_domains = ["i.redd.it", "i.imgur.com", "preview.redd.it", "external-preview.redd.it", "i.imgflip.com", "imgflip.com"]
        from urllib.parse import urlparse
        parsed_url = urlparse(image_url)
        if not any(domain in parsed_url.netloc for domain in allowed_domains):
            return jsonify({"error": "URL domain not allowed"}), 403
        
        # Fetch the image
        response = requests.get(image_url, timeout=10, stream=True)
        response.raise_for_status()
        
        # Get content type
        content_type = response.headers.get('Content-Type', 'image/jpeg')
        
        # Return the image with proper CORS headers
        return app.response_class(
            response.content,
            mimetype=content_type,
            headers={
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'public, max-age=86400',  # Cache for 24 hours
            }
        )
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to fetch image: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": f"Proxy error: {str(e)}"}), 500


@app.route("/api/test/daily-meme", methods=["POST"])
@token_required
def test_daily_meme():
    """Test daily meme posting using the actual bot function"""
    try:
        import asyncio

        # Get bot instance
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Make sure to start with start_with_api.py"}), 503

        # Get DailyMeme cog
        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        # Use the bot's existing event loop
        loop = bot.loop

        # Call the actual daily meme task function
        future = asyncio.run_coroutine_threadsafe(daily_meme_cog.daily_meme_task(), loop)

        # Wait for result with timeout
        future.result(timeout=30)

        return jsonify(
            {
                "success": True,
                "message": "Daily meme posted successfully",
                "note": "Check your Discord meme channel to see the posted meme",
            }
        )

    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to post daily meme: {str(e)}", "details": traceback.format_exc()}), 500


@app.route("/api/test/send-meme", methods=["POST"])
@token_required
def send_meme_to_discord():
    """Send a specific meme to Discord"""
    try:
        import asyncio

        # Get meme data from request
        data = request.get_json()
        if not data or "meme" not in data:
            return jsonify({"error": "Meme data required"}), 400

        meme_data = data["meme"]

        # Ensure meme_data has the correct structure expected by post_meme
        # The bot expects: url, title, subreddit, upvotes, author, permalink, nsfw
        if "upvotes" not in meme_data and "score" in meme_data:
            meme_data["upvotes"] = meme_data["score"]

        # Get bot instance
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available"}), 503

        # Get DailyMeme cog
        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        # Get meme channel
        meme_channel_id = Config.MEME_CHANNEL_ID
        channel = bot.get_channel(meme_channel_id)
        if not channel:
            return jsonify({"error": f"Meme channel {meme_channel_id} not found"}), 404

        # Use the bot's existing event loop
        loop = bot.loop

        # Post the meme to Discord with custom message
        async def post_meme():
            import discord
            from datetime import datetime
            from Utils.EmbedUtils import set_pink_footer

            # Create embed manually (same as post_meme but with custom message)
            embed = discord.Embed(
                title=meme_data["title"][:256],
                url=meme_data["permalink"],
                color=Config.PINK,
                timestamp=datetime.now(),
            )
            embed.set_image(url=meme_data["url"])
            embed.add_field(name="👍 Upvotes", value=f"{meme_data['upvotes']:,}", inline=True)

            # Display source appropriately
            source_name = f"r/{meme_data['subreddit']}"
            if meme_data["subreddit"].startswith("lemmy:"):
                source_name = meme_data["subreddit"].replace("lemmy:", "")

            embed.add_field(name="📍 Source", value=source_name, inline=True)
            embed.add_field(name="👤 Author", value=f"u/{meme_data['author']}", inline=True)

            if meme_data.get("nsfw"):
                embed.add_field(name="⚠️", value="NSFW Content", inline=False)

            set_pink_footer(embed, bot=bot.user)

            # Send with custom message
            await channel.send("🎭 Meme sent from Admin Panel", embed=embed)

        future = asyncio.run_coroutine_threadsafe(post_meme(), loop)
        future.result(timeout=30)

        return jsonify({"success": True, "message": "Meme sent to Discord successfully", "channel_id": meme_channel_id})

    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to send meme to Discord: {str(e)}", "details": traceback.format_exc()}), 500


def set_bot_instance(bot):
    """Set the bot instance for the API to use"""
    app.config["bot_instance"] = bot


def save_config_to_file():
    """Save current configuration to a JSON file for persistence"""
    config_file = Path(__file__).parent.parent / Config.DATA_DIR / "api_config_overrides.json"
    config_file.parent.mkdir(exist_ok=True)

    print(f"💾 DEBUG: Saving config to: {config_file} (DATA_DIR={Config.DATA_DIR})")

    config_data = {
        "general": {
            "bot_name": Config.BotName,
            "command_prefix": Config.CommandPrefix,
            "presence_update_interval": Config.PresenceUpdateInterval,
            "message_cooldown": Config.MessageCooldown,
            "fuzzy_matching_threshold": Config.FuzzyMatchingThreshold,
            "pink_color": Config.PINK.value if hasattr(Config.PINK, "value") else 0xAD1457,
            "embed_footer_text": Config.EMBED_FOOTER_TEXT
            if hasattr(Config, "EMBED_FOOTER_TEXT")
            else "Powered by Haze World 💖",
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

    rl_interval = config_data["rocket_league"]["rank_check_interval_hours"]
    rl_cache = config_data["rocket_league"]["rank_cache_ttl_seconds"]
    print(f"💾 DEBUG: Saving RL config to file: interval={rl_interval}h, cache={rl_cache}s")

    with open(config_file, "w") as f:
        json.dump(config_data, f, indent=2)

    print(f"✅ Config saved to {config_file}")


# ===== DAILY MEME CONFIGURATION ENDPOINTS =====


@app.route("/api/daily-meme/config", methods=["GET"])
@token_required
@require_permission("all")
def get_daily_meme_config():
    """Get daily meme configuration"""
    try:
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        # Merge config with available sources
        config_with_sources = {
            **daily_meme_cog.daily_config,
            "available_subreddits": daily_meme_cog.meme_subreddits,
            "available_lemmy": daily_meme_cog.meme_lemmy,
        }
        
        # Convert Discord IDs to strings to prevent precision loss in Flutter Web
        if "channel_id" in config_with_sources and config_with_sources["channel_id"]:
            config_with_sources["channel_id"] = str(config_with_sources["channel_id"])
        if "role_id" in config_with_sources and config_with_sources["role_id"]:
            config_with_sources["role_id"] = str(config_with_sources["role_id"])

        return jsonify(config_with_sources)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/daily-meme/config", methods=["POST"])
@token_required
@require_permission("all")
@log_config_action("daily_meme")
def update_daily_meme_config():
    """Update daily meme configuration"""
    try:
        data = request.json

        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        # Extract meme sources if provided
        if "subreddits" in data:
            daily_meme_cog.meme_subreddits = data.pop("subreddits")
            daily_meme_cog.save_subreddits()  # Fixed method name

        if "lemmy_communities" in data:
            daily_meme_cog.meme_lemmy = data.pop("lemmy_communities")
            daily_meme_cog.save_lemmy_communities()  # Fixed method name

        # Update configuration
        daily_meme_cog.daily_config.update(data)
        daily_meme_cog.save_daily_config()

        # Restart task if needed
        daily_meme_cog.restart_daily_task()
        
        # Convert Discord IDs to strings for response
        response_config = daily_meme_cog.daily_config.copy()
        if "channel_id" in response_config and response_config["channel_id"]:
            response_config["channel_id"] = str(response_config["channel_id"])
        if "role_id" in response_config and response_config["role_id"]:
            response_config["role_id"] = str(response_config["role_id"])

        return jsonify(
            {"success": True, "message": "Daily meme configuration updated", "config": response_config}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/daily-meme/config/reset", methods=["POST"])
@token_required
@require_permission("all")
def reset_daily_meme_config():
    """Reset daily meme configuration to defaults"""
    try:
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        # Reset to defaults
        daily_meme_cog.daily_config = {
            "enabled": True,
            "hour": 12,
            "minute": 0,
            "channel_id": Config.MEME_CHANNEL_ID,
            "role_id": Config.MEME_ROLE_ID,
            "allow_nsfw": True,
            "min_score": 100,
            "max_sources": 5,
            "pool_size": 50,
            "use_subreddits": None,  # None = use all
            "use_lemmy": None,  # None = use all
        }
        daily_meme_cog.save_daily_config()
        daily_meme_cog.restart_daily_task()
        
        # Convert Discord IDs to strings for response
        response_config = daily_meme_cog.daily_config.copy()
        if "channel_id" in response_config and response_config["channel_id"]:
            response_config["channel_id"] = str(response_config["channel_id"])
        if "role_id" in response_config and response_config["role_id"]:
            response_config["role_id"] = str(response_config["role_id"])

        return jsonify(
            {
                "success": True,
                "message": "Daily meme configuration reset to defaults",
                "config": response_config,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== GUILD INFO ENDPOINTS =====


@app.route("/api/guild/channels", methods=["GET"])
@token_required
def get_guild_channels():
    """Get all text channels and categories in the guild"""
    try:
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        guild = bot.get_guild(Config.GUILD_ID)
        if not guild:
            return jsonify({"error": "Guild not found"}), 404

        # Get all channels (text channels and categories)
        channels = []

        # Add text channels
        for channel in guild.text_channels:
            channels.append(
                {
                    "id": str(channel.id),
                    "name": channel.name,
                    "category": channel.category.name if channel.category else None,
                    "position": channel.position,
                    "type": "text",
                }
            )

        # Add categories
        for category in guild.categories:
            channels.append(
                {
                    "id": str(category.id),
                    "name": category.name,
                    "category": None,
                    "position": category.position,
                    "type": "category",
                }
            )

        # Sort by type (categories first), then by position
        channels.sort(key=lambda x: (0 if x["type"] == "category" else 1, x["position"]))

        return jsonify(channels)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/guild/roles", methods=["GET"])
@token_required
def get_guild_roles():
    """Get all roles in the guild"""
    try:
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        guild = bot.get_guild(Config.GUILD_ID)
        if not guild:
            return jsonify({"error": "Guild not found"}), 404

        # Get all roles (excluding @everyone)
        roles = []
        for role in guild.roles:
            if role.name != "@everyone":
                roles.append(
                    {
                        "id": str(role.id),
                        "name": role.name,
                        "color": role.color.value,
                        "position": role.position,
                        "mentionable": role.mentionable,
                    }
                )

        # Sort by position (highest first)
        roles.sort(key=lambda x: x["position"], reverse=True)

        return jsonify(roles)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Load any saved configuration on startup
    load_config_from_file()

    # Get port from environment or use default
    port = int(os.getenv("API_PORT", 5000))

    # Check if we're in debug mode (only for development)
    debug_mode = os.getenv("API_DEBUG", "false").lower() == "true"

    if debug_mode:
        print("WARNING: Running in DEBUG mode. This should NEVER be used in production!")

    print(f"Starting HazeBot Configuration API on port {port}")
    print(f"API Documentation: http://localhost:{port}/api/health")

    app.run(host="0.0.0.0", port=port, debug=debug_mode)
