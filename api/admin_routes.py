"""
Admin Routes Blueprint
Handles all /api/admin/* and /api/logs endpoints for administrative functions
"""

from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request

# Will be initialized by init_admin_routes()
Config = None
logger = None
active_sessions = None
recent_activity = None
log_action = None
token_required = None
require_permission = None
get_cache_stats = None
clear_cache = None
invalidate_cache = None
analytics_aggregator = None

# Create Blueprint
admin_bp = Blueprint("admin", __name__)


def init_admin_routes(
    app, config, log, sessions_dict, activity_list, helpers_module, auth_module, cache_module, analytics=None
):
    """
    Initialize admin routes Blueprint with dependencies

    Args:
        app: Flask app instance
        config: Config module
        log: Logger instance
        sessions_dict: Reference to active_sessions dict
        activity_list: Reference to recent_activity list
        helpers_module: Module containing log_action
        auth_module: Module containing decorators (token_required, require_permission)
        cache_module: Module containing cache functions (get_cache_stats, clear_cache, invalidate_cache)
        analytics: Analytics aggregator instance (optional)
    """
    global Config, logger, active_sessions, recent_activity, log_action
    global token_required, require_permission
    global get_cache_stats, clear_cache, invalidate_cache, analytics_aggregator

    Config = config
    logger = log
    active_sessions = sessions_dict
    recent_activity = activity_list
    log_action = helpers_module.log_action
    token_required = auth_module.token_required
    analytics_aggregator = analytics
    require_permission = auth_module.require_permission
    get_cache_stats = cache_module.get_cache_stats
    clear_cache = cache_module.clear_cache
    invalidate_cache = cache_module.invalidate_cache

    # Register blueprint WITHOUT decorators first
    app.register_blueprint(admin_bp)

    # NOW apply decorators to already-registered view functions
    vf = app.view_functions
    vf["admin.get_active_sessions_endpoint"] = token_required(
        require_permission("all")(vf["admin.get_active_sessions_endpoint"])
    )
    vf["admin.get_cache_stats_endpoint"] = token_required(
        require_permission("all")(vf["admin.get_cache_stats_endpoint"])
    )
    vf["admin.clear_cache_endpoint"] = token_required(require_permission("all")(vf["admin.clear_cache_endpoint"]))
    vf["admin.invalidate_cache_key_endpoint"] = token_required(
        require_permission("all")(vf["admin.invalidate_cache_key_endpoint"])
    )
    vf["admin.get_logs"] = token_required(require_permission("all")(vf["admin.get_logs"]))
    vf["admin.get_available_cogs"] = token_required(require_permission("all")(vf["admin.get_available_cogs"]))
    vf["admin.get_guild_channels"] = token_required(vf["admin.get_guild_channels"])
    vf["admin.get_guild_roles"] = token_required(vf["admin.get_guild_roles"])

    # Analytics endpoints (if analytics enabled)
    if analytics is not None:
        vf["admin.get_analytics_export"] = token_required(require_permission("all")(vf["admin.get_analytics_export"]))
        vf["admin.get_analytics_stats"] = token_required(require_permission("all")(vf["admin.get_analytics_stats"]))
        vf["admin.cleanup_analytics"] = token_required(require_permission("all")(vf["admin.cleanup_analytics"]))


# ===== ACTIVE SESSIONS =====


@admin_bp.route("/api/admin/active-sessions", methods=["GET"])
def get_active_sessions_endpoint():
    """Get all active API sessions + recent activity (Admin/Mod only)"""
    # Clean up old sessions (older than 30 minutes - increased from 5 min)
    current_time = Config.get_utc_now()
    expired_sessions = []

    for session_id, session_data in list(active_sessions.items()):
        try:
            last_seen = datetime.fromisoformat(session_data["last_seen"])
            if (current_time - last_seen).total_seconds() > 1800:  # 30 minutes
                expired_sessions.append(session_id)
        except Exception:
            expired_sessions.append(session_id)

    # Remove expired sessions
    for session_id in expired_sessions:
        del active_sessions[session_id]

    # Format active sessions and deduplicate by discord_id (show only most recent session per user)
    user_sessions = {}  # {discord_id: session_data}
    
    for session_id, session_data in active_sessions.items():
        try:
            last_seen = datetime.fromisoformat(session_data["last_seen"])
            seconds_ago = int((current_time - last_seen).total_seconds())
            discord_id = session_data.get("discord_id", "Unknown")

            session_entry = {
                "session_id": session_id,
                "username": session_data.get("username", "Unknown"),
                "discord_id": discord_id,
                "role": session_data.get("role", "unknown"),
                "permissions": session_data.get("permissions", []),
                "last_seen": session_data["last_seen"],
                "seconds_ago": seconds_ago,
                "ip": session_data.get("ip", "Unknown"),
                "user_agent": session_data.get("user_agent", "Unknown"),
                "last_endpoint": session_data.get("endpoint", "unknown"),
                "app_version": session_data.get("app_version", "Unknown"),
                "platform": session_data.get("platform", "Unknown"),
                "device_info": session_data.get("device_info", "Unknown"),
            }
            
            # Add special indicator for uptime_kuma_monitor
            if session_data.get("username") == "uptime_kuma_monitor":
                session_entry["username"] = "Invy McPingFace"  # Friendly monitor name
                session_entry["is_monitor"] = True
                session_entry["monitor_type"] = "Uptime Kuma"
                session_entry["monitor_status"] = "active" if seconds_ago < 60 else "stale"
            
            # Keep only the most recent session per user
            if (
                discord_id not in user_sessions
                or last_seen > datetime.fromisoformat(user_sessions[discord_id]["last_seen"])
            ):
                user_sessions[discord_id] = session_entry
                
        except Exception:
            continue

    # Convert to list and sort by last_seen (most recent first)
    sessions_list = list(user_sessions.values())
    sessions_list.sort(key=lambda x: x["last_seen"], reverse=True)

    # Get recent activity (already sorted by timestamp, most recent first)
    recent_activity_list = list(reversed(recent_activity[-50:]))  # Last 50 activities

    # Enrich activity with Discord user info
    from flask import current_app

    bot = current_app.config.get("bot_instance")
    for activity in recent_activity_list:
        discord_id = activity.get("discord_id")
        if bot and discord_id and discord_id not in ["legacy_user", "unknown"]:
            try:
                guild = bot.get_guild(Config.GUILD_ID)
                if guild:
                    member = guild.get_member(int(discord_id))
                    if member:
                        activity["display_name"] = member.display_name
                        activity["avatar_url"] = str(member.display_avatar.url) if member.display_avatar else None
            except Exception:
                pass  # Silently fail if user not found

    # Filter out uptime_kuma_monitor from recent activity (keep only in active sessions)
    recent_activity_list = [
        activity for activity in recent_activity_list 
        if activity.get("username") != "uptime_kuma_monitor"
    ]

    return jsonify(
        {
            "total_active": len(sessions_list),
            "sessions": sessions_list,
            "recent_activity": recent_activity_list,
            "checked_at": current_time.isoformat(),
        }
    )


# ===== CACHE MANAGEMENT =====


@admin_bp.route("/api/admin/cache/stats", methods=["GET"])
def get_cache_stats_endpoint():
    """Get cache statistics (Admin only)"""
    stats = get_cache_stats()
    return jsonify(stats)


@admin_bp.route("/api/admin/cache/clear", methods=["POST"])
def clear_cache_endpoint():
    """Clear entire cache (Admin only)"""
    clear_cache()
    log_action(request.username, "clear_cache", {"status": "success"})
    return jsonify({"success": True, "message": "Cache cleared"})


@admin_bp.route("/api/admin/cache/invalidate", methods=["POST"])
def invalidate_cache_key_endpoint():
    """Invalidate cache entries by pattern (Admin only)"""
    data = request.get_json()
    pattern = data.get("pattern")

    if not pattern:
        return jsonify({"error": "Pattern is required"}), 400

    count = invalidate_cache(pattern)
    log_action(request.username, "invalidate_cache", {"pattern": pattern, "count": count})

    return jsonify({"success": True, "invalidated": count, "pattern": pattern})


# ===== LOGS =====


@admin_bp.route("/api/logs", methods=["GET"])
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

        # Get available cogs from bot instance
        from flask import current_app

        available_cogs = []
        bot = current_app.config.get("bot_instance")
        if bot:
            available_cogs = sorted([cog for cog in bot.cogs.keys()])

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
                "available_cogs": available_cogs,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/api/logs/cogs", methods=["GET"])
def get_available_cogs():
    """Get list of available cogs for log filtering"""
    try:
        from flask import current_app

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Get all loaded cogs
        cogs = sorted([cog for cog in bot.cogs.keys()])

        return jsonify({"cogs": cogs})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/api/guild/channels", methods=["GET"])
def get_guild_channels():
    """Get all text channels and categories in the guild"""
    try:
        from flask import current_app

        bot = current_app.config.get("bot_instance")
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


@admin_bp.route("/api/guild/roles", methods=["GET"])
def get_guild_roles():
    """Get all roles in the guild"""
    try:
        from flask import current_app

        bot = current_app.config.get("bot_instance")
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


# ============================================================================
# ANALYTICS ENDPOINTS (Admin Only)
# ============================================================================
# Note: Dekoratoren werden in init_admin_routes() angewendet


@admin_bp.route("/api/admin/analytics/export", methods=["GET"])
def get_analytics_export():
    """
    Export full analytics data for external analysis
    Query params:
        - days: Number of days to include (optional, default: all)
    """
    try:
        if analytics_aggregator is None:
            return jsonify({"error": "Analytics not enabled"}), 503

        # Get optional days parameter
        days = request.args.get("days", type=int)

        export_data = analytics_aggregator.get_export_data(days=days)

        return jsonify({"success": True, "data": export_data})
    except Exception as e:
        logger.error(f"Failed to export analytics: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/api/admin/analytics/stats", methods=["GET"])
def get_analytics_stats():
    """Get summary analytics statistics"""
    try:
        if analytics_aggregator is None:
            return jsonify({"error": "Analytics not enabled"}), 503

        stats = analytics_aggregator.get_summary_stats()

        return jsonify({"success": True, "stats": stats})
    except Exception as e:
        logger.error(f"Failed to get analytics stats: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/api/admin/analytics/cleanup", methods=["POST"])
def cleanup_analytics():
    """
    Clean up old analytics sessions
    Body: {"days_to_keep": 90}
    """
    try:
        if analytics_aggregator is None:
            return jsonify({"error": "Analytics not enabled"}), 503

        data = request.get_json() or {}
        days_to_keep = data.get("days_to_keep", 90)

        removed = analytics_aggregator.cleanup_old_sessions(days_to_keep=days_to_keep)

        return jsonify({"success": True, "removed_sessions": removed, "days_kept": days_to_keep})
    except Exception as e:
        logger.error(f"Failed to cleanup analytics: {e}")
        return jsonify({"error": str(e)}), 500
