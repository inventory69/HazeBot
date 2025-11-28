"""
Admin and health endpoints blueprint.
"""

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

import Config
from api.cache import clear_cache, get_cache_stats, invalidate_cache
from api.utils.audit import log_action
from api.utils.auth import active_sessions, recent_activity, require_permission, token_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@admin_bp.route("/api/admin/active-sessions", methods=["GET"])
@token_required
@require_permission("all")
def get_active_sessions():
    """Get all active API sessions + recent activity (Admin/Mod only)"""
    current_time = Config.get_utc_now()
    expired_sessions = []

    for session_id, session_data in list(active_sessions.items()):
        try:
            last_seen = datetime.fromisoformat(session_data["last_seen"])
            if (current_time - last_seen).total_seconds() > 1800:  # 30 minutes
                expired_sessions.append(session_id)
        except Exception:
            expired_sessions.append(session_id)

    for session_id in expired_sessions:
        del active_sessions[session_id]

    sessions_list = []
    for session_id, session_data in active_sessions.items():
        try:
            last_seen = datetime.fromisoformat(session_data["last_seen"])
            seconds_ago = int((current_time - last_seen).total_seconds())

            sessions_list.append(
                {
                    "session_id": session_id,
                    "username": session_data.get("username", "Unknown"),
                    "discord_id": session_data.get("discord_id", "Unknown"),
                    "role": session_data.get("role", "unknown"),
                    "permissions": session_data.get("permissions", []),
                    "last_seen": session_data["last_seen"],
                    "seconds_ago": seconds_ago,
                    "ip": session_data.get("ip", "Unknown"),
                    "user_agent": session_data.get("user_agent", "Unknown"),
                    "last_endpoint": session_data.get("endpoint", "unknown"),
                }
            )
        except Exception:
            continue

    sessions_list.sort(key=lambda x: x["last_seen"], reverse=True)

    recent_activity_list = list(reversed(recent_activity[-50:]))  # Last 50 activities

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
                pass

    return jsonify(
        {
            "total_active": len(sessions_list),
            "sessions": sessions_list,
            "recent_activity": recent_activity_list,
            "checked_at": current_time.isoformat(),
        }
    )


@admin_bp.route("/api/admin/cache/stats", methods=["GET"])
@token_required
@require_permission("all")
def get_cache_stats_endpoint():
    """Get cache statistics (Admin only)"""
    stats = get_cache_stats()
    return jsonify(stats)


@admin_bp.route("/api/admin/cache/clear", methods=["POST"])
@token_required
@require_permission("all")
def clear_cache_endpoint():
    """Clear entire cache (Admin only)"""
    clear_cache()
    log_action(request.username, "clear_cache", {"status": "success"})
    return jsonify({"success": True, "message": "Cache cleared"})


@admin_bp.route("/api/admin/cache/invalidate", methods=["POST"])
@token_required
@require_permission("all")
def invalidate_cache_endpoint():
    """Invalidate cache entries by pattern (Admin only)"""
    data = request.get_json()
    pattern = data.get("pattern")

    if not pattern:
        return jsonify({"error": "Pattern is required"}), 400

    count = invalidate_cache(pattern)
    log_action(request.username, "invalidate_cache", {"pattern": pattern, "count": count})

    return jsonify({"success": True, "invalidated": count, "pattern": pattern})
