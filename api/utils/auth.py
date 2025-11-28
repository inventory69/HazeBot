"""
Authentication helpers and shared state for the HazeBot API.
"""

import json
import sys
import threading
from datetime import datetime
from functools import wraps
from pathlib import Path

import jwt
from flask import current_app, jsonify, request

# Ensure we can import the root-level Config module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import Config  # noqa: E402
from Utils.Logger import Logger as logger  # noqa: E402

# Thread lock for JWT decode (prevents race conditions)
jwt_decode_lock = threading.Lock()

# Active sessions tracking
active_sessions = {}  # {session_id: {username, discord_id, roles, last_seen, ip, user_agent}}

# Recent activity tracking (last 100 interactions)
recent_activity = []  # List of {timestamp, username, discord_id, action, endpoint, details}
MAX_ACTIVITY_LOG = 100

# App usage tracking path (uses DATA_DIR from Config for test/prod mode)
APP_USAGE_FILE = Path(__file__).parent.parent.parent / Config.DATA_DIR / "app_usage.json"
APP_USAGE_EXPIRY_DAYS = 30  # Remove badge after 30 days of inactivity


def load_app_usage():
    """Load app usage data from file."""
    if APP_USAGE_FILE.exists():
        with open(APP_USAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_app_usage(app_usage):
    """Persist app usage data to disk."""
    APP_USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(APP_USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(app_usage, f, indent=2)


def update_app_usage(discord_id):
    """Update last seen timestamp for a user."""
    if discord_id and discord_id not in ["legacy_user", "unknown"]:
        app_usage = load_app_usage()
        app_usage[discord_id] = Config.get_utc_now().isoformat()
        save_app_usage(app_usage)


def get_active_app_users():
    """Return discord IDs that have used the app recently."""
    app_usage = load_app_usage()
    current_time = Config.get_utc_now()
    active_users = set()

    for discord_id, last_seen_str in list(app_usage.items()):
        try:
            last_seen = datetime.fromisoformat(last_seen_str)
            days_inactive = (current_time - last_seen).days
            if days_inactive <= APP_USAGE_EXPIRY_DAYS:
                active_users.add(discord_id)
            else:
                del app_usage[discord_id]
        except (ValueError, TypeError):
            del app_usage[discord_id]

    save_app_usage(app_usage)
    return active_users


def log_user_activity(username, discord_id, action, endpoint, details=None):
    """Track recent activity for monitoring."""
    global recent_activity
    now = Config.get_utc_now()

    for entry in recent_activity:
        try:
            entry_time = datetime.fromisoformat(entry["timestamp"])
            if (now - entry_time).total_seconds() <= 300 and (
                entry.get("username") == username
                and entry.get("discord_id") == discord_id
                and entry.get("action") == action
                and entry.get("endpoint") == endpoint
            ):
                return
        except (ValueError, TypeError):
            continue

    activity_entry = {
        "timestamp": now.isoformat(),
        "username": username,
        "discord_id": discord_id,
        "action": action,
        "endpoint": endpoint,
        "details": details or {},
    }

    recent_activity.append(activity_entry)
    if len(recent_activity) > MAX_ACTIVITY_LOG:
        recent_activity = recent_activity[-MAX_ACTIVITY_LOG:]


def token_required(f):
    """JWT auth decorator."""

    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            logger.warning(f"❌ No Authorization header | Endpoint: {request.endpoint}")
            return jsonify({"error": "Token is missing"}), 401

        try:
            if token.startswith("Bearer "):
                token = token[7:]
            if not token.strip():
                logger.warning(f"❌ Empty token | Endpoint: {request.endpoint}")
                return jsonify({"error": "Token is empty"}), 401

            parts = token.split(".")
            if len(parts) != 3 or not all(parts):
                logger.warning(f"❌ Malformed token structure | Endpoint: {request.endpoint}")
                return jsonify({"error": "token_invalid"}), 401

            with jwt_decode_lock:
                data = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])

            exp_timestamp = data.get("exp")
            if exp_timestamp:
                exp_date = datetime.utcfromtimestamp(exp_timestamp)
                time_until_expiry = exp_date - Config.get_utc_now().replace(tzinfo=None)
                if time_until_expiry.total_seconds() < 0:
                    logger.warning(f"❌ Token expired | User: {data.get('user')} | Expired: {exp_date}")
                    return jsonify({"error": "Token expired"}), 401

            logger.debug(
                f"?o. Token validated | User: {data.get('user')} | "
                f"Auth: {data.get('auth_type', 'unknown')} | Endpoint: {request.endpoint}"
            )
            request.username = data.get("user", "unknown")
            request.user_role = data.get("role", "admin")
            request.role_name = data.get("role_name")
            request.user_permissions = data.get("permissions", ["all"])
            request.discord_id = data.get("discord_id", "unknown")

            if "session_id" in data:
                request.session_id = data["session_id"]
            else:
                import hashlib

                session_data = f"{data.get('user', 'unknown')}_{data.get('discord_id', 'unknown')}_{token}"
                request.session_id = hashlib.sha256(session_data.encode()).hexdigest()[:32]

            real_ip = (
                request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                or request.headers.get("X-Real-IP", "").strip()
                or request.remote_addr
            )

            session_info = {
                "username": request.username,
                "discord_id": request.discord_id,
                "role": request.user_role,
                "permissions": request.user_permissions,
                "last_seen": Config.get_utc_now().isoformat(),
                "ip": real_ip,
                "user_agent": request.headers.get("User-Agent", "Unknown"),
                "endpoint": request.endpoint or "unknown",
            }
            active_sessions[request.session_id] = session_info

            update_app_usage(request.discord_id)
            endpoint_name = request.endpoint or "unknown"
            log_user_activity(
                request.username, request.discord_id, request.method, endpoint_name, {"path": request.path}
            )

        except jwt.ExpiredSignatureError:
            logger.debug(f"⏱️ Token expired | Endpoint: {request.endpoint}")
            return jsonify({"error": "token_expired"}), 401
        except (jwt.DecodeError, jwt.InvalidTokenError) as e:
            error_msg = str(e)
            if "Expecting value" in error_msg or "JSON" in error_msg.lower():
                logger.debug(
                    f"⏱️ Token decode failed (likely during refresh): {error_msg} | Endpoint: {request.endpoint}"
                )
                return jsonify({"error": "token_expired"}), 401
            logger.warning(f"❌ Token invalid: {error_msg} | Endpoint: {request.endpoint}")
            return jsonify({"error": "token_invalid"}), 401
        except Exception as e:
            error_msg = str(e)
            if "Expecting value" in error_msg or "JSONDecodeError" in str(type(e)):
                logger.debug(
                    f"⏱️ Unexpected JSON decode error (treating as expired): {error_msg} | Endpoint: {request.endpoint}"
                )
                return jsonify({"error": "token_expired"}), 401
            logger.error(
                f"❌ Token validation error: {error_msg} | Type: {type(e).__name__} | Endpoint: {request.endpoint}"
            )
            return jsonify({"error": "token_validation_failed"}), 401

        return f(*args, **kwargs)

    return decorated


def require_permission(permission):
    """Decorator to check if user has required permission."""

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user_permissions = getattr(request, "user_permissions", [])
            if "all" in user_permissions:
                return f(*args, **kwargs)
            if permission not in user_permissions:
                return jsonify({"error": "Insufficient permissions"}), 403
            return f(*args, **kwargs)

        return wrapper

    return decorator
