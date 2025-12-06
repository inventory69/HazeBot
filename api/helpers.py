"""
Helper functions and utilities for the Flask API
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from Utils.Logger import Logger as logger

# Will be initialized by init_helpers()
Config = None


def init_helpers(config):
    """Initialize helpers module with Config"""
    global Config
    Config = config


# COMPLETELY disable werkzeug HTTP request logs
werkzeug_logger = logging.getLogger("werkzeug")
werkzeug_logger.disabled = True  # Nuclear option: disable logger completely


# Upvotes storage helpers
def load_upvotes(upvotes_file):
    """Load upvotes from file"""
    if upvotes_file.exists():
        with open(upvotes_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}  # {message_id: [discord_id1, discord_id2, ...]}


def save_upvotes(upvotes, upvotes_file):
    """Save upvotes to file"""
    upvotes_file.parent.mkdir(parents=True, exist_ok=True)
    with open(upvotes_file, "w", encoding="utf-8") as f:
        json.dump(upvotes, f, indent=2)


# App usage tracking helpers
def load_app_usage(app_usage_file):
    """Load app usage data from file"""
    if app_usage_file.exists():
        with open(app_usage_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}  # {discord_id: last_seen_timestamp}


def save_app_usage(app_usage, app_usage_file):
    """Save app usage data to file"""
    app_usage_file.parent.mkdir(parents=True, exist_ok=True)
    with open(app_usage_file, "w", encoding="utf-8") as f:
        json.dump(app_usage, f, indent=2)


def update_app_usage(discord_id, app_usage_file, Config):
    """Update last seen timestamp for a user"""
    if discord_id and discord_id not in ["legacy_user", "unknown"]:
        app_usage = load_app_usage(app_usage_file)
        app_usage[discord_id] = Config.get_utc_now().isoformat()
        save_app_usage(app_usage, app_usage_file)


def get_active_app_users(app_usage_file, app_usage_expiry_days, Config):
    """Get list of discord IDs who have used the app within the expiry period"""
    app_usage = load_app_usage(app_usage_file)
    current_time = Config.get_utc_now()
    active_users = set()

    for discord_id, last_seen_str in list(app_usage.items()):
        try:
            last_seen = datetime.fromisoformat(last_seen_str)
            days_inactive = (current_time - last_seen).days

            if days_inactive <= app_usage_expiry_days:
                active_users.add(discord_id)
            else:
                # Clean up old entries
                del app_usage[discord_id]
        except (ValueError, TypeError):
            # Invalid timestamp, remove it
            del app_usage[discord_id]

    # Save cleaned up data
    save_app_usage(app_usage, app_usage_file)
    return active_users


# Meme activity tracking helpers
def load_meme_requests():
    """Load meme requests from file"""
    from Config import get_data_dir
    file_path = Path(get_data_dir()) / "meme_requests.json"
    try:
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading meme requests: {e}")
    return {}


def save_meme_requests(meme_requests):
    """Save meme requests to file"""
    from Config import get_data_dir
    file_path = Path(get_data_dir()) / "meme_requests.json"
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(meme_requests, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving meme requests: {e}")


def increment_meme_request(discord_id: str):
    """Increment meme request counter for user"""
    meme_requests = load_meme_requests()
    meme_requests[str(discord_id)] = meme_requests.get(str(discord_id), 0) + 1
    save_meme_requests(meme_requests)
    logger.info(f"📊 Meme request tracked for user {discord_id} (Total: {meme_requests[str(discord_id)]})")


def load_memes_generated():
    """Load memes generated from file"""
    from Config import get_data_dir
    file_path = Path(get_data_dir()) / "memes_generated.json"
    try:
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading memes generated: {e}")
    return {}


def save_memes_generated(memes_generated):
    """Save memes generated to file"""
    from Config import get_data_dir
    file_path = Path(get_data_dir()) / "memes_generated.json"
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(memes_generated, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving memes generated: {e}")


def increment_meme_generated(discord_id: str):
    """Increment meme generated counter for user"""
    memes_generated = load_memes_generated()
    memes_generated[str(discord_id)] = memes_generated.get(str(discord_id), 0) + 1
    save_memes_generated(memes_generated)
    logger.info(f"📊 Meme generation tracked for user {discord_id} (Total: {memes_generated[str(discord_id)]})")


# Audit logging
def log_action(username, action, details=None):
    """Log user actions to file and console"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "username": username,
        "action": action,
        "details": details or {},
    }

    # Log to console
    logger.info(f"🔧 [API Action] {username} - {action}" + (f" | {details}" if details else ""))

    # Log to audit file
    audit_log_path = Path(__file__).parent.parent / "Logs" / "api_audit.log"
    audit_log_path.parent.mkdir(exist_ok=True)

    with open(audit_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")


# Activity logging (for recent activity tracking)
def log_user_activity(username, discord_id, action, endpoint, recent_activity, max_activity_log, Config, details=None):
    """Log user activity for recent interactions tracking - only relevant endpoints"""
    # Only log meaningful actions - filter out read-only monitoring endpoints
    # These endpoints are too frequent and not interesting for activity tracking
    ignored_endpoints = {
        "get_active_sessions",  # Admin monitoring (auto-refresh every 5s)
        "get_gaming_members",  # Gaming hub auto-refresh
        "get_latest_memes",  # Meme feed auto-refresh
        "health",  # Health checks
        "ping",  # Ping checks
    }

    if endpoint in ignored_endpoints:
        return  # Don't log these frequent read operations

    # Aggressive deduplication: check if similar entry exists in last 5 minutes
    # This prevents the same action from appearing multiple times
    now = Config.get_utc_now()
    cutoff_time = now - timedelta(minutes=5)

    for entry in reversed(recent_activity[-20:]):  # Check last 20 entries
        try:
            entry_time = datetime.fromisoformat(entry.get("timestamp", ""))
            if entry_time < cutoff_time:
                break  # Stop checking older entries

            # If same user did same action on same endpoint recently, skip
            if (
                entry.get("username") == username
                and entry.get("discord_id") == discord_id
                and entry.get("action") == action
                and entry.get("endpoint") == endpoint
            ):
                return  # Skip duplicate within 5 minutes
        except (ValueError, TypeError):
            continue

    # Log this new activity
    activity_entry = {
        "timestamp": now.isoformat(),
        "username": username,
        "discord_id": discord_id,
        "action": action,
        "endpoint": endpoint,
        "details": details or {},
    }

    recent_activity.append(activity_entry)

    # Keep only last MAX_ACTIVITY_LOG entries
    if len(recent_activity) > max_activity_log:
        recent_activity[:] = recent_activity[-max_activity_log:]


# Config file management
def save_config_to_file(Config, config_file):
    """Save current configuration to a JSON file for persistence"""
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


# Negative emojis that should NOT count as upvotes
NEGATIVE_EMOJIS = {
    "👎",
    "😠",
    "😡",
    "🤬",
    "💩",
    "🖕",
    "❌",
    "⛔",
    "🚫",
    "💔",
    "😤",
    "😒",
    "🙄",
    "😑",
    "😐",
    "😶",
    "🤐",
    "😬",
}
