"""
Flask API for HazeBot Configuration
Provides REST endpoints to read and update bot configuration
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO

# Add parent directory to path to import Config
sys.path.insert(0, str(Path(__file__).parent.parent))
import Config

from api.routes.admin import admin_bp
from api.routes.auth import auth_bp
from api.routes.config import config_bp
from api.routes.cogs import cogs_bp
from api.routes.gaming import gaming_bp
from api.routes.memes import memes_bp
from api.routes.rocket_league import rl_bp
from api.routes.tickets import tickets_bp
from api.utils.audit import log_config_action
from api.utils.auth import require_permission, token_required
from Utils.ConfigLoader import load_config_from_file

app = Flask(__name__)
CORS(app)  # Enable CORS for Flutter web
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent", logger=False, engineio_logger=False)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(config_bp)
app.register_blueprint(cogs_bp)
app.register_blueprint(gaming_bp)
app.register_blueprint(memes_bp)
app.register_blueprint(rl_bp)
app.register_blueprint(tickets_bp)

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

        return jsonify({"success": True, "message": "Daily meme configuration updated", "config": response_config})
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


@app.route("/api/ping", methods=["GET"])
@token_required
def ping():
    """Simple ping endpoint to test session tracking (no permission required)"""
    return jsonify(
        {
            "success": True,
            "message": "pong",
            "your_username": request.username,
            "your_role": request.user_role,
            "your_session_id": request.session_id,
            "your_permissions": request.user_permissions,
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/api/user/profile", methods=["GET"])
@token_required
def get_user_profile():
    """Get current user's profile information (no special permissions required)"""
    try:
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        discord_id = request.discord_id
        if discord_id == "legacy_user" or discord_id == "unknown":
            return jsonify({"error": "Discord ID not available for legacy users"}), 400

        # Get guild
        guild = bot.get_guild(Config.GUILD_ID)
        if not guild:
            return jsonify({"error": "Guild not found"}), 404

        # Get member
        member = guild.get_member(int(discord_id))
        if not member:
            return jsonify({"error": "Member not found in guild"}), 404

        # Determine role (Admin, Moderator, or Lootling) and get actual role name
        user_role = "lootling"
        user_role_name = "Lootling"
        for role in member.roles:
            if role.id == Config.ADMIN_ROLE_ID:
                user_role = "admin"
                user_role_name = role.name
                break
            elif role.id == Config.MODERATOR_ROLE_ID:
                user_role = "mod"
                user_role_name = role.name
                break

        # Get opt-in roles (interest roles)
        opt_in_roles = []
        for role in member.roles:
            if role.id in Config.INTEREST_ROLE_IDS:
                opt_in_roles.append(
                    {
                        "id": str(role.id),
                        "name": role.name,
                        "color": role.color.value if role.color else 0,
                    }
                )

        # Get Rocket League rank (if available)
        rl_rank = None
        try:
            from Cogs.RocketLeague import RANK_EMOJIS, load_rl_accounts
            from Config import RL_TIER_ORDER

            rl_accounts = load_rl_accounts()
            if str(discord_id) in rl_accounts:
                account = rl_accounts[str(discord_id)]
                ranks = account.get("ranks", {})  # This contains tier names like "Champion II"
                icon_urls = account.get("icon_urls", {})

                # Calculate highest rank from ranks dict
                highest_tier = "Unranked"
                highest_playlist = None
                for playlist, tier in ranks.items():
                    if tier in RL_TIER_ORDER and RL_TIER_ORDER.index(tier) > RL_TIER_ORDER.index(highest_tier):
                        highest_tier = tier
                        highest_playlist = playlist

                if highest_tier and highest_tier != "Unranked" and highest_playlist:
                    # Get the rank emoji and icon URL for the highest playlist
                    rank_emoji = RANK_EMOJIS.get(highest_tier, "")
                    icon_url = icon_urls.get(highest_playlist)

                    rl_rank = {
                        "rank": highest_tier,
                        "emoji": rank_emoji,
                        "icon_url": icon_url,
                        "platform": account.get("platform"),
                        "username": account.get("username"),
                    }
        except Exception:
            # RL data is optional, don't fail if not available
            pass

        # Get notification opt-ins
        has_changelog = any(role.id == Config.CHANGELOG_ROLE_ID for role in member.roles)
        has_meme = any(role.id == Config.MEME_ROLE_ID for role in member.roles)

        # Get warnings
        warnings_count = 0
        try:
            from Cogs.ModPerks import load_mod_data

            mod_data_sync = load_mod_data()
            # If it's async, we need to handle it
            if hasattr(mod_data_sync, "__await__"):
                import asyncio

                mod_data = asyncio.run(mod_data_sync)
            else:
                mod_data = mod_data_sync
            warnings_data = mod_data.get("warnings", {})
            user_warnings = warnings_data.get(str(discord_id), {})
            warnings_count = user_warnings.get("count", 0)
        except Exception:
            pass

        # Get resolved tickets (for admins/mods)
        resolved_tickets = 0
        if any(role.id in [Config.ADMIN_ROLE_ID, Config.MODERATOR_ROLE_ID] for role in member.roles):
            try:
                from Cogs.TicketSystem import load_tickets

                tickets_sync = load_tickets()
                if hasattr(tickets_sync, "__await__"):
                    import asyncio

                    tickets = asyncio.run(tickets_sync)
                else:
                    tickets = tickets_sync

                for ticket in tickets:
                    if ticket["status"] == "Closed" and (
                        ticket.get("claimed_by") == int(discord_id) or ticket.get("assigned_to") == int(discord_id)
                    ):
                        resolved_tickets += 1
            except Exception:
                pass

        # Get activity stats
        activity = {"messages": 0, "images": 0, "memes_requested": 0, "memes_generated": 0}
        try:
            from Cogs.Leaderboard import get_user_activity

            activity_sync = get_user_activity(int(discord_id))
            if hasattr(activity_sync, "__await__"):
                import asyncio

                activity_data = asyncio.run(activity_sync)
            else:
                activity_data = activity_sync
            activity["messages"] = activity_data.get("messages", 0)
            activity["images"] = activity_data.get("images", 0)
        except Exception:
            pass

        # Get meme stats
        try:
            from Cogs.Profile import load_meme_requests, load_memes_generated

            meme_requests = load_meme_requests()
            memes_generated = load_memes_generated()
            activity["memes_requested"] = meme_requests.get(str(discord_id), 0)
            activity["memes_generated"] = memes_generated.get(str(discord_id), 0)
        except Exception:
            pass

        return jsonify(
            {
                "success": True,
                "profile": {
                    "discord_id": str(discord_id),
                    "username": member.name,
                    "display_name": member.display_name,
                    "role": user_role,
                    "role_name": user_role_name,
                    "avatar_url": str(member.avatar.url) if member.avatar else None,
                    "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                    "created_at": member.created_at.isoformat() if member.created_at else None,
                    "opt_in_roles": opt_in_roles,
                    "rl_rank": rl_rank,
                    "notifications": {"changelog_opt_in": has_changelog, "meme_opt_in": has_meme},
                    "custom_stats": {"warnings": warnings_count, "resolved_tickets": resolved_tickets},
                    "activity": activity,
                },
            }
        )

    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to get user profile: {str(e)}", "details": traceback.format_exc()}), 500


# ===== COG MANAGEMENT ENDPOINTS =====


if __name__ == "__main__":
    # Load any saved configuration on startup
    load_config_from_file()

    # Initialize Firebase Cloud Messaging (optional)
    try:
        from Utils.notification_service import initialize_firebase

        firebase_initialized = initialize_firebase()
        if firebase_initialized:
            print("✅ Firebase Cloud Messaging initialized")
        else:
            print("⚠️  Firebase Cloud Messaging not available (push notifications disabled)")
    except Exception as e:
        print(f"⚠️  Failed to initialize Firebase: {e}")
        print("   Push notifications will be disabled")

    # Get port from environment or use default
    port = int(os.getenv("API_PORT", 5000))

    # Check if we're in debug mode (only for development)
    debug_mode = os.getenv("API_DEBUG", "false").lower() == "true"

    if debug_mode:
        print("WARNING: Running in DEBUG mode. This should NEVER be used in production!")

    print(f"Starting HazeBot Configuration API on port {port}")
    print(f"WebSocket support enabled with gevent on ws://localhost:{port}/socket.io/")
    print(f"API Documentation: http://localhost:{port}/api/health")

    # Use socketio.run instead of app.run for WebSocket support
    socketio.run(app, host="0.0.0.0", port=port, debug=debug_mode)
