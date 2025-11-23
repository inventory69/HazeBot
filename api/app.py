"""
Flask API for HazeBot Configuration
Provides REST endpoints to read and update bot configuration
"""

import json
import logging
import os
import sys
import threading
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlencode

import jwt
import requests
from flask import Flask, jsonify, redirect, request
from flask_cors import CORS

# Add parent directory to path to import Config
sys.path.insert(0, str(Path(__file__).parent.parent))
import Config

# Import cache system
from api.cache import cache, clear_cache, get_cache_stats, invalidate_cache
from Utils.ConfigLoader import load_config_from_file
from Utils.Logger import Logger as logger

app = Flask(__name__)
CORS(app)  # Enable CORS for Flutter web

# Thread lock for JWT decode (prevents race conditions)
jwt_decode_lock = threading.Lock()

# Active sessions tracking
active_sessions = {}  # {session_id: {username, discord_id, roles, last_seen, ip, user_agent}}

# Recent activity tracking (last 100 interactions)
recent_activity = []  # List of {timestamp, username, discord_id, action, endpoint, details}
MAX_ACTIVITY_LOG = 100

# Upvotes storage path (uses DATA_DIR from Config for test/prod mode)
UPVOTES_FILE = Path(__file__).parent.parent / Config.DATA_DIR / "meme_upvotes.json"

# App usage tracking path (uses DATA_DIR from Config for test/prod mode)
APP_USAGE_FILE = Path(__file__).parent.parent / Config.DATA_DIR / "app_usage.json"
APP_USAGE_EXPIRY_DAYS = 30  # Remove badge after 30 days of inactivity

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


def load_upvotes():
    """Load upvotes from file"""
    if UPVOTES_FILE.exists():
        with open(UPVOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}  # {message_id: [discord_id1, discord_id2, ...]}


def save_upvotes(upvotes):
    """Save upvotes to file"""
    UPVOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(UPVOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(upvotes, f, indent=2)


def load_app_usage():
    """Load app usage data from file"""
    if APP_USAGE_FILE.exists():
        with open(APP_USAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}  # {discord_id: last_seen_timestamp}


def save_app_usage(app_usage):
    """Save app usage data to file"""
    APP_USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(APP_USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(app_usage, f, indent=2)


def update_app_usage(discord_id):
    """Update last seen timestamp for a user"""
    if discord_id and discord_id not in ["legacy_user", "unknown"]:
        app_usage = load_app_usage()
        app_usage[discord_id] = Config.get_utc_now().isoformat()
        save_app_usage(app_usage)


def get_active_app_users():
    """Get list of discord IDs who have used the app within the expiry period"""
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
                # Clean up old entries
                del app_usage[discord_id]
        except (ValueError, TypeError):
            # Invalid timestamp, remove it
            del app_usage[discord_id]

    # Save cleaned up data
    save_app_usage(app_usage)
    return active_users


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


# Helper function to log activity
def log_user_activity(username, discord_id, action, endpoint, details=None):
    """Log user activity for recent interactions tracking - only relevant endpoints"""
    global recent_activity

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
    if len(recent_activity) > MAX_ACTIVITY_LOG:
        recent_activity = recent_activity[-MAX_ACTIVITY_LOG:]


# Simple authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")

        if not token:
            logger.warning(f"❌ No Authorization header | Endpoint: {request.endpoint}")
            return jsonify({"error": "Token is missing"}), 401

        try:
            # Strip "Bearer " prefix if present
            if token.startswith("Bearer "):
                token = token[7:]

            # Validate token is not empty
            if not token or token.strip() == "":
                logger.warning(f"❌ Empty token | Endpoint: {request.endpoint}")
                return jsonify({"error": "Token is empty"}), 401

            # Validate JWT structure (must have header.payload.signature format)
            parts = token.split(".")
            if len(parts) != 3 or not all(parts):
                logger.warning(f"❌ Malformed token structure | Endpoint: {request.endpoint}")
                return jsonify({"error": "token_invalid"}), 401

            # Thread-safe JWT decode (prevents race conditions during parallel requests)
            with jwt_decode_lock:
                data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])

            # Check token expiry
            exp_timestamp = data.get("exp")
            if exp_timestamp:
                exp_date = datetime.utcfromtimestamp(exp_timestamp)
                time_until_expiry = exp_date - Config.get_utc_now().replace(tzinfo=None)
                if time_until_expiry.total_seconds() < 0:
                    logger.warning(f"❌ Token expired | User: {data.get('user')} | Expired: {exp_date}")
                    return jsonify({"error": "Token expired"}), 401

            # DEBUG: Log token validation success with auth_type
            auth_type = data.get("auth_type", "unknown")
            logger.debug(
                f"✅ Token validated | User: {data.get('user')} | Auth: {auth_type} | Endpoint: {request.endpoint}"
            )

            # Store username and permissions in request context
            request.username = data.get("user", "unknown")
            request.user_role = data.get("role", "admin")
            request.role_name = data.get("role_name")
            request.user_permissions = data.get("permissions", ["all"])
            request.discord_id = data.get("discord_id", "unknown")

            # Generate a unique session ID if not present in token
            # Use user-specific data to ensure uniqueness across different users
            if "session_id" in data:
                request.session_id = data["session_id"]
            else:
                # Fallback: Create session ID from user ID + discord ID + token hash
                import hashlib

                session_data = f"{data.get('user', 'unknown')}_{data.get('discord_id', 'unknown')}_{token}"
                request.session_id = hashlib.sha256(session_data.encode()).hexdigest()[:32]

            # Update active session tracking
            # Get real client IP (handle proxy/forwarded requests)
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

            # Update app usage tracking (persistent)
            update_app_usage(request.discord_id)

            # Log activity (filtering is done inside log_user_activity)
            endpoint_name = request.endpoint or "unknown"
            log_user_activity(
                request.username, request.discord_id, request.method, endpoint_name, {"path": request.path}
            )

        except jwt.ExpiredSignatureError:
            # Token is expired - this is EXPECTED during token refresh
            logger.debug(f"⏱️ Token expired | Endpoint: {request.endpoint}")
            return jsonify({"error": "token_expired"}), 401
        except (jwt.DecodeError, jwt.InvalidTokenError) as e:
            # PyJWT errors: DecodeError (malformed/corrupted payload), InvalidTokenError (wrong signature)
            # DecodeError can include JSON decode errors ("Expecting value: line 1 column 1")
            error_msg = str(e)

            # During token refresh, old tokens may fail decoding - treat as expired
            if "Expecting value" in error_msg or "JSON" in error_msg.lower():
                logger.debug(
                    f"⏱️ Token decode failed (likely during refresh): {error_msg} | Endpoint: {request.endpoint}"
                )
                return jsonify({"error": "token_expired"}), 401

            # Other token errors (wrong signature, etc.)
            logger.warning(f"❌ Token invalid: {error_msg} | Endpoint: {request.endpoint}")
            return jsonify({"error": "token_invalid"}), 401
        except Exception as e:
            # Catch-all for unexpected errors (should rarely happen)
            error_msg = str(e)

            # Check if it's a JSON decode error that escaped PyJWT exception handling
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
        import secrets

        session_id = secrets.token_hex(16)

        token = jwt.encode(
            {
                "user": username,
                "discord_id": "legacy_user",
                "exp": Config.get_utc_now().replace(tzinfo=None) + timedelta(days=7),  # 7 days instead of 24 hours
                "role": "admin",
                "permissions": ["all"],
                "auth_type": "legacy",
                "session_id": session_id,
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
    # Ensure all role IDs are strings for comparison
    role_ids = [str(rid) for rid in role_ids]

    # Get bot instance to fetch role IDs from Config
    bot = app.config.get("bot_instance")
    if not bot:
        return "lootling"

    # Get role IDs from Config
    admin_role_id = str(Config.ADMIN_ROLE_ID)
    mod_role_id = str(Config.MODERATOR_ROLE_ID)

    # Debug logging
    from Utils.Logger import Logger

    Logger.info(
        f"🔍 Discord Auth - Checking roles: user_roles={role_ids}, admin_id={admin_role_id}, mod_id={mod_role_id}"
    )

    # Check for admin/mod roles (mods get same permissions as admins for now)
    if admin_role_id in role_ids:
        Logger.info("✅ User identified as ADMIN")
        return "admin"
    elif mod_role_id in role_ids:
        Logger.info("✅ User identified as MOD (with admin permissions)")
        return "mod"
    else:
        Logger.info("👤 User identified as LOOTLING")
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
    prod_mode = os.getenv("PROD_MODE", "false").lower() == "true"
    guild_id = os.getenv("DISCORD_GUILD_ID") if prod_mode else os.getenv("DISCORD_TEST_GUILD_ID")

    member_response = requests.get(f"{DISCORD_API_ENDPOINT}/users/@me/guilds/{guild_id}/member", headers=user_headers)

    if member_response.status_code != 200:
        logger.error("❌ Discord member check failed:")
        logger.error(f"   Status: {member_response.status_code}")
        logger.error(f"   Response: {member_response.text[:500]}")  # Limit response length
        logger.error(f"   User: {user_data.get('username')}#{user_data.get('discriminator')}")
        logger.error(f"   User ID: {user_data.get('id')}")
        logger.error(f"   Guild ID: {guild_id}")
        logger.error(f"   API URL: {DISCORD_API_ENDPOINT}/users/@me/guilds/{guild_id}/member")

        # Fallback: Try to check via bot instead
        logger.info("🔄 Attempting fallback via bot instance...")
        bot = app.config.get("bot_instance")
        if bot:
            guild = bot.get_guild(int(guild_id))
            if guild:
                member = guild.get_member(int(user_data["id"]))
                if member:
                    logger.info("✅ User found in guild via bot, proceeding with authentication")
                    # Create member_data dict from bot member
                    member_data = {
                        "roles": [str(role.id) for role in member.roles],
                        "user": {
                            "id": str(member.id),
                            "username": member.name,
                        },
                    }
                else:
                    logger.error("❌ User not found in guild via bot either")
                    return jsonify({"error": "User is not a member of the guild"}), 403
            else:
                logger.error(f"❌ Guild {guild_id} not found via bot")
                return jsonify({"error": "Guild not found"}), 500
        else:
            logger.error("❌ Bot instance not available for fallback")
            return jsonify({"error": "User is not a member of the guild"}), 403
    else:
        member_data = member_response.json()

    # Determine role and permissions
    role = get_user_role_from_discord(member_data, guild_id)
    permissions = ROLE_PERMISSIONS.get(role, ["meme_generator"])

    # Get role name from Discord for display purposes
    role_name = None
    try:
        bot = app.config.get("bot_instance")
        if bot:
            guild = bot.get_guild(int(guild_id))
            if guild:
                member = guild.get_member(int(user_data["id"]))
                if member:
                    for discord_role in member.roles:
                        if discord_role.id == Config.ADMIN_ROLE_ID:
                            role_name = discord_role.name
                            break
                        elif discord_role.id == Config.MODERATOR_ROLE_ID:
                            role_name = discord_role.name
                            break
    except Exception:
        pass  # role_name is optional

    # Create JWT token
    import secrets

    session_id = secrets.token_hex(16)

    token = jwt.encode(
        {
            "user": user_data["username"],
            "discord_id": user_data["id"],
            "exp": Config.get_utc_now().replace(tzinfo=None) + timedelta(days=7),  # 7 days instead of 24 hours
            "role": role,
            "role_name": role_name,
            "permissions": permissions,
            "auth_type": "discord",
            "session_id": session_id,
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

        # Get avatar URL and role name from Discord if we have discord_id
        avatar_url = None
        role_name = data.get("role_name")  # Try to get from token first
        discord_id = data.get("discord_id")
        if discord_id and discord_id not in ["legacy_user", "unknown"]:
            try:
                bot = app.config.get("bot_instance")
                if bot:
                    guild = bot.get_guild(Config.GUILD_ID)
                    if guild:
                        member = guild.get_member(int(discord_id))
                        if member:
                            if member.avatar:
                                avatar_url = str(member.avatar.url)
                            # Get role name from Discord (fallback if not in token)
                            if not role_name:
                                for role in member.roles:
                                    if role.id == Config.ADMIN_ROLE_ID:
                                        role_name = role.name
                                        break
                                    elif role.id == Config.MODERATOR_ROLE_ID:
                                        role_name = role.name
                                        break
            except Exception:
                pass  # Avatar and role name are optional

        return jsonify(
            {
                "user": data.get("user"),
                "discord_id": data.get("discord_id"),
                "role": data.get("role", "admin"),
                "role_name": role_name,
                "permissions": data.get("permissions", ["all"]),
                "auth_type": data.get("auth_type", "legacy"),
                "avatar_url": avatar_url,
            }
        )
    except Exception:
        return jsonify({"error": "Invalid token"}), 401


@app.route("/api/auth/refresh", methods=["POST"])
@token_required
def refresh_token():
    """Refresh JWT token with new expiry date (keeps same session_id)"""
    try:
        # Build token payload (only include role_name if it exists and is not None)
        token_payload = {
            "user": request.username,
            "discord_id": request.discord_id,
            "exp": Config.get_utc_now().replace(tzinfo=None) + timedelta(days=7),  # 7 days
            "role": request.user_role,
            "permissions": request.user_permissions,
            "auth_type": "refreshed",
            "session_id": request.session_id,  # Keep same session
        }

        # Only add role_name if it exists and is not None
        if hasattr(request, "role_name") and request.role_name:
            token_payload["role_name"] = request.role_name

        # Create new token with extended expiry but keep same session_id
        new_token = jwt.encode(token_payload, app.config["SECRET_KEY"], algorithm="HS256")

        # Build response (include role_name if available)
        response_data = {
            "token": new_token,
            "user": request.username,
            "discord_id": request.discord_id,
            "role": request.user_role,
            "permissions": request.user_permissions,
        }

        if hasattr(request, "role_name") and request.role_name:
            response_data["role_name"] = request.role_name

        return jsonify(response_data)
    except Exception as e:
        logger.error(f"❌ Token refresh failed: {e}")
        return jsonify({"error": "Token refresh failed"}), 500


@app.route("/api/auth/logout", methods=["POST"])
@token_required
def logout():
    """Logout user and remove their active session"""
    try:
        # Remove session from active_sessions
        session_id = request.session_id
        if session_id in active_sessions:
            del active_sessions[session_id]
            logger.info(f"🚪 User logged out: {request.username} (Session: {session_id[:8]}...)")

        return jsonify({"message": "Logged out successfully"}), 200
    except Exception as e:
        logger.error(f"❌ Logout failed: {e}")
        return jsonify({"error": "Logout failed"}), 500


@app.route("/api/admin/active-sessions", methods=["GET"])
@token_required
@require_permission("all")
def get_active_sessions():
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

    # Format active sessions
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

    # Sort by last_seen (most recent first)
    sessions_list.sort(key=lambda x: x["last_seen"], reverse=True)

    # Get recent activity (already sorted by timestamp, most recent first)
    recent_activity_list = list(reversed(recent_activity[-50:]))  # Last 50 activities

    # Enrich activity with Discord user info
    bot = app.config.get("bot_instance")
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

    return jsonify(
        {
            "total_active": len(sessions_list),
            "sessions": sessions_list,
            "recent_activity": recent_activity_list,
            "checked_at": current_time.isoformat(),
        }
    )


@app.route("/api/admin/cache/stats", methods=["GET"])
@token_required
@require_permission("all")
def get_cache_stats_endpoint():
    """Get cache statistics (Admin only)"""
    stats = get_cache_stats()
    return jsonify(stats)


@app.route("/api/admin/cache/clear", methods=["POST"])
@token_required
@require_permission("all")
def clear_cache_endpoint():
    """Clear entire cache (Admin only)"""
    clear_cache()
    log_action(request.username, "clear_cache", {"status": "success"})
    return jsonify({"success": True, "message": "Cache cleared"})


@app.route("/api/admin/cache/invalidate", methods=["POST"])
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
    Config.GAMING_CHANNEL_ID = Config.CURRENT_IDS.get("GAMING_CHANNEL_ID")
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

        # Log the request
        logger.info(f"🔍 Fetching RL stats for {username} on {platform.upper()} (via API by {request.username})")

        # Use the bot's existing event loop
        loop = bot.loop

        # Fetch stats using the bot's function
        future = asyncio.run_coroutine_threadsafe(rl_cog.get_player_stats(platform.lower(), username), loop)

        # Wait for result with timeout
        stats = future.result(timeout=90)

        if not stats:
            logger.warning(f"❌ Player {username} not found on {platform.upper()}")
            return jsonify({"error": "Player not found or error fetching stats"}), 404

        # Log success with ranks
        ranks_str = ", ".join([f"{k}: {v}" for k, v in stats.get("tier_names", {}).items()])
        logger.info(f"✅ Fetched RL stats for {stats['username']}: [{ranks_str}]")

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

        return jsonify({"error": f"Failed to get stats: {str(e)}", "details": traceback.format_exc()}), 500


# User Rocket League Endpoints (for logged-in users to manage their own account)
@app.route("/api/user/rocket-league/link", methods=["POST"])
@token_required
def link_user_rl_account():
    """Link Rocket League account for the current user"""
    try:
        import asyncio
        from datetime import datetime, timezone

        from Cogs.RocketLeague import load_rl_accounts, save_rl_accounts

        discord_id = request.discord_id
        if discord_id == "legacy_user" or discord_id == "unknown":
            return jsonify({"error": "Discord ID not available"}), 400

        data = request.get_json()
        platform = data.get("platform", "").lower()
        username = data.get("username", "").strip()

        if not platform or not username:
            return jsonify({"error": "Platform and username are required"}), 400

        if platform not in ["steam", "epic", "psn", "xbl", "switch"]:
            return jsonify({"error": "Invalid platform. Use: steam, epic, psn, xbl, or switch"}), 400

        logger.info(f"🔗 User {request.username} attempting to link RL account: {username} on {platform.upper()}")

        # Check if user already has an account linked
        accounts = load_rl_accounts()
        if str(discord_id) in accounts:
            return jsonify({"error": "You already have a Rocket League account linked. Unlink it first."}), 400

        # Fetch stats to validate the account exists
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        rl_cog = bot.get_cog("RocketLeague")
        if not rl_cog:
            return jsonify({"error": "RocketLeague cog not loaded"}), 503

        loop = bot.loop
        future = asyncio.run_coroutine_threadsafe(rl_cog.get_player_stats(platform, username), loop)
        stats = future.result(timeout=30)

        if not stats:
            return jsonify({"error": "Player not found. Please check your platform and username."}), 404

        # Save the account with ORIGINAL input username (like the bot does)
        accounts[str(discord_id)] = {
            "platform": platform,
            "username": username,  # Use input username (not stats["username"]) - same as bot
            "ranks": stats.get("tier_names", {}),
            "rank_display": stats.get("rank_display", {}),
            "icon_urls": stats.get("icon_urls", {}),
            "last_fetched": datetime.now(timezone.utc).isoformat(),
        }
        save_rl_accounts(accounts)

        # Log success with display name from API but save input username
        ranks_str = ", ".join([f"{k}: {v}" for k, v in stats.get("tier_names", {}).items()])
        logger.info(
            f"✅ Successfully linked RL account for {request.username}: {username} "
            f"(displays as {stats['username']}) ({platform.upper()}) - [{ranks_str}]"
        )

        return jsonify(
            {
                "success": True,
                "message": f"Successfully linked Rocket League account: {stats['username']}",
                "account": {
                    "platform": platform,
                    "username": username,  # Return the saved username
                    "ranks": stats.get("tier_names", {}),
                },
            }
        )
    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to link account: {str(e)}", "details": traceback.format_exc()}), 500


@app.route("/api/user/rocket-league/unlink", methods=["DELETE"])
@token_required
def unlink_user_rl_account():
    """Unlink Rocket League account for the current user"""
    try:
        from Cogs.RocketLeague import load_rl_accounts, save_rl_accounts

        discord_id = request.discord_id
        if discord_id == "legacy_user" or discord_id == "unknown":
            return jsonify({"error": "Discord ID not available"}), 400

        accounts = load_rl_accounts()

        if str(discord_id) not in accounts:
            return jsonify({"error": "No Rocket League account linked"}), 404

        # Get username for response
        rl_username = accounts[str(discord_id)].get("username", "Unknown")
        rl_platform = accounts[str(discord_id)].get("platform", "Unknown")

        # Delete the account
        del accounts[str(discord_id)]
        save_rl_accounts(accounts)

        logger.info(f"🔓 User {request.username} unlinked RL account: {rl_username} ({rl_platform.upper()})")

        return jsonify(
            {
                "success": True,
                "message": f"Successfully unlinked Rocket League account: {rl_username}",
            }
        )
    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to unlink account: {str(e)}", "details": traceback.format_exc()}), 500


@app.route("/api/user/rocket-league/account", methods=["GET"])
@token_required
def get_user_rl_account():
    """Get current user's linked Rocket League account"""
    try:
        from Cogs.RocketLeague import load_rl_accounts

        discord_id = request.discord_id
        if discord_id == "legacy_user" or discord_id == "unknown":
            return jsonify({"error": "Discord ID not available"}), 400

        accounts = load_rl_accounts()

        if str(discord_id) not in accounts:
            return jsonify({"linked": False})

        account = accounts[str(discord_id)]
        return jsonify(
            {
                "linked": True,
                "account": {
                    "platform": account.get("platform"),
                    "username": account.get("username"),
                    "ranks": account.get("ranks", {}),
                    "rank_display": account.get("rank_display", {}),
                    "icon_urls": account.get("icon_urls", {}),
                    "last_fetched": account.get("last_fetched"),
                },
            }
        )
    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to fetch RL stats: {str(e)}", "details": traceback.format_exc()}), 500


@app.route("/api/user/rocket-league/post-stats", methods=["POST"])
@token_required
def post_user_rl_stats():
    """Post current user's RL stats to a Discord channel"""
    try:
        import asyncio

        discord_id = request.discord_id
        if discord_id == "legacy_user" or discord_id == "unknown":
            return jsonify({"error": "Discord ID not available"}), 400

        # Get RocketLeague cog
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        rl_cog = bot.get_cog("RocketLeague")
        if not rl_cog:
            return jsonify({"error": "Rocket League system not available"}), 503

        logger.info(f"📊 User {discord_id} posting RL stats to configured RL channel...")

        # Use the bot's existing event loop (same as /rlstats)
        loop = bot.loop
        future = asyncio.run_coroutine_threadsafe(rl_cog.post_stats_to_channel(int(discord_id)), loop)
        result = future.result(timeout=30)

        if result["success"]:
            logger.info(f"✅ RL stats posted successfully: {result['message']}")
            return jsonify(result), 200
        else:
            logger.warning(f"❌ Failed to post RL stats: {result['message']}")
            return jsonify(result), 400

    except Exception as e:
        import traceback

        logger.error(f"Error posting RL stats: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to post RL stats: {str(e)}", "details": traceback.format_exc()}), 500


@app.route("/api/user/preferences", methods=["PUT"])
@token_required
def update_user_preferences():
    """Update current user's notification preferences"""
    try:
        import asyncio

        discord_id = request.discord_id
        if discord_id == "legacy_user" or discord_id == "unknown":
            return jsonify({"error": "Discord ID not available"}), 400

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Get bot instance
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Get guild
        guild = bot.get_guild(Config.GUILD_ID)
        if not guild:
            return jsonify({"error": "Guild not found"}), 500

        # Get member
        member = guild.get_member(int(discord_id))
        if not member:
            return jsonify({"error": "Member not found in guild"}), 404

        # Handle changelog opt-in/out
        if "changelog_opt_in" in data:
            changelog_role = guild.get_role(Config.CHANGELOG_ROLE_ID)
            if changelog_role:
                if data["changelog_opt_in"]:
                    if changelog_role not in member.roles:
                        asyncio.run_coroutine_threadsafe(member.add_roles(changelog_role), bot.loop).result(timeout=5)
                else:
                    if changelog_role in member.roles:
                        asyncio.run_coroutine_threadsafe(member.remove_roles(changelog_role), bot.loop).result(
                            timeout=5
                        )

        # Handle meme opt-in/out
        if "meme_opt_in" in data:
            meme_role = guild.get_role(Config.MEME_ROLE_ID)
            if meme_role:
                if data["meme_opt_in"]:
                    if meme_role not in member.roles:
                        asyncio.run_coroutine_threadsafe(member.add_roles(meme_role), bot.loop).result(timeout=5)
                else:
                    if meme_role in member.roles:
                        asyncio.run_coroutine_threadsafe(member.remove_roles(meme_role), bot.loop).result(timeout=5)

        return jsonify({"message": "Preferences updated successfully"})
    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to update preferences: {str(e)}", "details": traceback.format_exc()}), 500


@app.route("/api/gaming/members", methods=["GET"])
@token_required
def get_gaming_members():
    """Get all server members with their presence/activity data + app usage status (with cache)"""
    try:
        # Check cache first (30 second TTL - users change status frequently)
        cache_key = "gaming:members"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return jsonify(cached_result)

        import discord

        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        guild = bot.get_guild(Config.GUILD_ID)
        if not guild:
            return jsonify({"error": "Guild not found"}), 500

        # Get list of users who have used the app within the last 30 days
        app_users = get_active_app_users()

        members_data = []
        for member in guild.members:
            if member.bot:
                continue  # Skip bots

            # Get member status and activity
            status = str(member.status) if member.status else "offline"
            activity_data = None

            if member.activities:
                # Filter out custom status (ActivityType.custom = 4)
                # Get first non-custom activity (game/streaming/etc)
                for activity in member.activities:
                    activity_type = activity.type

                    # Skip custom status activities
                    if activity_type == discord.ActivityType.custom:
                        continue

                    # Found a real activity (game, streaming, etc)
                    activity_type_str = str(activity_type).replace("ActivityType.", "").lower()

                    activity_data = {
                        "type": activity_type_str,
                        "name": activity.name,
                    }

                    # Add game-specific details
                    if hasattr(activity, "details") and activity.details:
                        activity_data["details"] = activity.details
                    if hasattr(activity, "state") and activity.state:
                        activity_data["state"] = activity.state
                    if hasattr(activity, "large_image_url") and activity.large_image_url:
                        activity_data["image_url"] = activity.large_image_url
                    elif hasattr(activity, "small_image_url") and activity.small_image_url:
                        activity_data["image_url"] = activity.small_image_url

                    # Found valid activity, stop searching
                    break

            # Check if user is using the app
            is_using_app = str(member.id) in app_users

            members_data.append(
                {
                    "id": str(member.id),
                    "username": member.name,
                    "display_name": member.display_name,
                    "avatar_url": str(member.display_avatar.url) if member.display_avatar else None,
                    "status": status,
                    "activity": activity_data,
                    "using_app": is_using_app,
                }
            )

        # Sort: online users first, then by username
        members_data.sort(key=lambda m: (m["status"] == "offline", m["display_name"].lower()))

        result = {"members": members_data, "total": len(members_data), "app_users_count": len(app_users)}

        # Cache result for 30 seconds (users change status frequently)
        cache.set(cache_key, result, ttl=30)

        return jsonify(result)

    except Exception as e:
        import traceback

        logger.error(f"Error fetching gaming members: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch members: {str(e)}"}), 500


@app.route("/api/gaming/request", methods=["POST"])
@token_required
def post_game_request():
    """Post a game request to the gaming channel"""
    try:
        import asyncio

        import discord

        discord_id = request.discord_id
        if discord_id == "legacy_user" or discord_id == "unknown":
            return jsonify({"error": "Discord ID not available"}), 400

        data = request.get_json()
        if not data or "target_user_id" not in data or "game_name" not in data:
            return jsonify({"error": "Missing required fields: target_user_id, game_name"}), 400

        target_user_id = data["target_user_id"]
        game_name = data["game_name"]
        message_text = data.get("message", "")

        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        guild = bot.get_guild(Config.GUILD_ID)
        if not guild:
            return jsonify({"error": "Guild not found"}), 500

        # Get gaming channel
        gaming_channel_id = Config.GAMING_CHANNEL_ID
        if not gaming_channel_id:
            return jsonify({"error": "Gaming channel not configured"}), 500

        channel = guild.get_channel(gaming_channel_id)
        if not channel:
            return jsonify({"error": "Gaming channel not found"}), 404

        # Get users
        requester = guild.get_member(int(discord_id))
        target = guild.get_member(int(target_user_id))

        if not requester:
            return jsonify({"error": "Requester not found in guild"}), 404
        if not target:
            return jsonify({"error": "Target user not found in guild"}), 404

        # Create embed
        embed = discord.Embed(
            title="🎮 Game Request",
            description=f"{requester.mention} wants to play **{game_name}** with {target.mention}!",
            color=discord.Color.green(),
            timestamp=Config.get_utc_now(),
        )

        if message_text:
            embed.add_field(name="Message", value=message_text, inline=False)

        embed.set_thumbnail(url=requester.display_avatar.url)
        embed.set_footer(text="Respond with the buttons below")

        # Send message with buttons using persistent GameRequestView from GamingHub cog
        async def send_request():
            # Import the persistent view from GamingHub cog
            from Cogs.GamingHub import GameRequestView

            view = GameRequestView(int(discord_id), int(target_user_id), game_name, Config.get_local_now().timestamp())
            msg = await channel.send(content=f"🎮 {target.mention}", embed=embed, view=view)

            # Save to persistent storage
            gaming_hub_cog = bot.get_cog("GamingHub")
            if gaming_hub_cog:
                gaming_hub_cog.save_game_request(channel.id, msg.id, int(discord_id), int(target_user_id), game_name)
            else:
                logger.warning("GamingHub cog not loaded, game request view will not persist")

            return msg

        loop = bot.loop
        future = asyncio.run_coroutine_threadsafe(send_request(), loop)
        message = future.result(timeout=10)

        logger.info(f"🎮 Game request posted: {requester.name} -> {target.name} for {game_name}")

        return jsonify(
            {
                "success": True,
                "message": "Game request posted successfully",
                "message_id": str(message.id),
                "channel_id": str(channel.id),
            }
        )

    except Exception as e:
        import traceback

        logger.error(f"Error posting game request: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to post game request: {str(e)}"}), 500


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

        # Get available cogs from bot instance
        available_cogs = []
        bot = app.config.get("bot_instance")
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
        from Config import IMGFLIP_PASSWORD, IMGFLIP_USERNAME

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

        # Get Discord user from JWT token
        discord_id = request.discord_id
        guild = bot.get_guild(Config.get_guild_id())
        member = None
        if guild and discord_id:
            member = guild.get_member(int(discord_id))

        # Post the meme to Discord
        async def post_meme():
            from datetime import datetime

            import discord

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

            # Add source field for custom memes
            embed.add_field(name="📍 Source", value="Meme Generator", inline=False)

            # Add creator field
            if member:
                embed.add_field(name="👤 Created by", value=member.mention, inline=False)
            else:
                embed.add_field(name="🖥️ Created via", value="Admin Panel", inline=False)

            set_pink_footer(embed, bot=bot.user)

            # Send with mention if we have member
            if member:
                await channel.send(f"🎨 Custom meme created by {member.mention}!", embed=embed)
            else:
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
        allowed_domains = [
            "i.redd.it",
            "i.imgur.com",
            "preview.redd.it",
            "external-preview.redd.it",
            "i.imgflip.com",
            "imgflip.com",
        ]
        from urllib.parse import urlparse

        parsed_url = urlparse(image_url)
        if not any(domain in parsed_url.netloc for domain in allowed_domains):
            return jsonify({"error": "URL domain not allowed"}), 403

        # Fetch the image
        response = requests.get(image_url, timeout=10, stream=True)
        response.raise_for_status()

        # Get content type
        content_type = response.headers.get("Content-Type", "image/jpeg")

        # Return the image with proper CORS headers
        return app.response_class(
            response.content,
            mimetype=content_type,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
            },
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
            from datetime import datetime

            import discord

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

            # Get requester Discord ID from token
            requester_id = (
                request.discord_id if hasattr(request, "discord_id") and request.discord_id != "unknown" else None
            )

            # Send with custom message including requester mention
            if requester_id:
                message_text = f"🎭 Meme sent from Admin Panel by <@{requester_id}>"
            else:
                message_text = "🎭 Meme sent from Admin Panel"

            await channel.send(message_text, embed=embed)

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


# =====================================
# HazeHub Endpoints
# =====================================


@app.route("/api/hazehub/latest-memes", methods=["GET"])
@token_required
def get_latest_memes():
    """Get latest memes posted in the meme channel (with cache)"""
    try:
        limit = request.args.get("limit", 10, type=int)
        limit = min(limit, 50)  # Max 50 memes

        # Check cache first (60 second TTL)
        cache_key = f"hazehub:latest_memes:{limit}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return jsonify(cached_result)

        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not available"}), 503

        # Get meme channel
        meme_channel_id = Config.MEME_CHANNEL_ID
        if not meme_channel_id:
            return jsonify({"error": "Meme channel not configured"}), 400

        # Load custom upvotes
        custom_upvotes = load_upvotes()

        async def fetch_memes():
            channel = bot.get_channel(meme_channel_id)
            if not channel:
                return None

            memes = []
            async for message in channel.history(limit=limit * 2):  # Fetch more to ensure we have enough memes
                # Only include messages with embeds (memes posted by bot)
                if message.embeds:
                    embed = message.embeds[0]

                    # Meme structure based on DailyMeme.post_meme():
                    # - title: embed.title
                    # - url/permalink: embed.url
                    # - image: embed.image.url
                    # - Fields: "👍 Upvotes", "📍 Source", "👤 Author"

                    message_id_str = str(message.id)
                    meme_data = {
                        "message_id": message_id_str,
                        "timestamp": message.created_at.isoformat(),
                        "title": embed.title or "Untitled Meme",
                        "image_url": embed.image.url if embed.image else None,
                        "url": embed.url or None,  # This is the permalink to reddit/lemmy
                        "color": embed.color.value if embed.color else None,
                    }

                    # Get custom upvotes from our system
                    custom_count = len(custom_upvotes.get(message_id_str, []))

                    # Get Discord reactions count (all positive reactions)
                    # Count all reactions EXCEPT negative ones
                    # reaction.count includes all users (including bots)
                    # We check if bot reacted (reaction.me = True means bot reacted)
                    discord_count = 0
                    for reaction in message.reactions:
                        emoji_str = str(reaction.emoji)

                        # Skip negative emojis
                        if emoji_str in NEGATIVE_EMOJIS:
                            continue

                        # Count this reaction (subtract 1 if bot reacted)
                        count = reaction.count
                        if reaction.me:
                            count = max(0, count - 1)
                        discord_count += count

                    # Combine both counts
                    total_upvotes = custom_count + discord_count
                    meme_data["upvotes"] = total_upvotes
                    meme_data["custom_upvotes"] = custom_count
                    meme_data["discord_upvotes"] = discord_count

                    # Parse fields for upvotes, source, author, creator
                    if embed.fields:
                        for field in embed.fields:
                            field_name = field.name.lower()

                            # Upvotes field: "👍 Upvotes"
                            if "upvote" in field_name or "👍" in field_name:
                                try:
                                    # Remove commas and convert to int
                                    score_str = field.value.replace(",", "").strip()
                                    meme_data["score"] = int("".join(filter(str.isdigit, score_str)))
                                except (ValueError, AttributeError):
                                    meme_data["score"] = 0

                            # Source field: "📍 Source" (e.g., "r/memes" or "lemmy.world/c/memes")
                            elif "source" in field_name or "📍" in field_name:
                                meme_data["source"] = field.value

                            # Author field: "👤 Author" (e.g., "u/username") OR "👤 Created by" for custom memes
                            elif "author" in field_name or "created by" in field_name or "👤" in field_name:
                                # Remove "u/" prefix if present
                                author = field.value
                                if author.startswith("u/"):
                                    author = author[2:]
                                # For custom memes with mentions like <@123456>, extract Discord username
                                import re

                                mention_match = re.search(r"<@!?(\d+)>", author)
                                if mention_match:
                                    user_id = mention_match.group(1)
                                    try:
                                        guild = bot.get_guild(Config.get_guild_id())
                                        if guild:
                                            member = guild.get_member(int(user_id))
                                            if member:
                                                author = member.display_name or member.name
                                                meme_data["is_custom"] = True
                                            else:
                                                author = f"User {user_id}"
                                        else:
                                            author = f"User {user_id}"
                                    except (ValueError, AttributeError):
                                        author = f"User {user_id}"
                                meme_data["author"] = author

                    # Set defaults if not found
                    if "score" not in meme_data:
                        meme_data["score"] = 0
                    if "author" not in meme_data:
                        meme_data["author"] = "Unknown"
                    if "source" not in meme_data:
                        # For custom memes, set source to "Meme Generator"
                        if meme_data.get("is_custom"):
                            meme_data["source"] = "Meme Generator"
                        else:
                            meme_data["source"] = "Unknown"

                    memes.append(meme_data)

                    # Stop if we have enough
                    if len(memes) >= limit:
                        break

            return memes

        # Run async function
        import asyncio

        memes = asyncio.run_coroutine_threadsafe(fetch_memes(), bot.loop).result(timeout=10)

        if memes is None:
            return jsonify({"error": "Meme channel not found"}), 404

        result = {"success": True, "memes": memes, "count": len(memes)}

        # Cache result for 60 seconds
        cache.set(cache_key, result, ttl=60)

        return jsonify(result)

    except Exception as e:
        import traceback

        logger.error(f"Error fetching latest memes: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch memes: {str(e)}"}), 500


@app.route("/api/hazehub/latest-rankups", methods=["GET"])
@token_required
def get_latest_rankups():
    """Get latest rank-up announcements from RL channel (with cache)"""
    try:
        limit = request.args.get("limit", 10, type=int)
        limit = min(limit, 50)  # Max 50 rank-ups

        # Check cache first (60 second TTL)
        cache_key = f"hazehub:latest_rankups:{limit}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return jsonify(cached_result)

        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not available"}), 503

        # Get RL channel
        rl_channel_id = Config.RL_CHANNEL_ID
        if not rl_channel_id:
            return jsonify({"error": "Rocket League channel not configured"}), 400

        async def fetch_rankups():
            channel = bot.get_channel(rl_channel_id)
            if not channel:
                return None

            rankups = []
            checked_count = 0
            async for message in channel.history(limit=100):  # Fetch more messages to find rank-ups
                checked_count += 1

                # Check message content and embeds for rank-up keywords
                message_text = message.content.lower()

                # Check if it's a rank-up message by looking at content
                is_rankup = any(
                    keyword in message_text
                    for keyword in [
                        "rank promotion",
                        "🚀 rank promotion",
                        "promotion notification",
                        "rank has improved",
                    ]
                )

                # Also check embeds
                if not is_rankup and message.embeds:
                    embed = message.embeds[0]
                    title = (embed.title or "").lower()
                    description = (embed.description or "").lower()

                    is_rankup = any(
                        keyword in title or keyword in description
                        for keyword in ["rank promotion", "promotion", "rank has improved", "congratulations"]
                    )

                # Only process rank-ups that have embeds (real rank-up messages)
                if is_rankup and message.embeds:
                    import re

                    # Build rankup data
                    rankup_data = {
                        "message_id": str(message.id),
                        "timestamp": message.created_at.isoformat(),
                    }

                    if message.embeds:
                        embed = message.embeds[0]
                        rankup_data["title"] = embed.title or ""
                        rankup_data["description"] = embed.description or ""
                        rankup_data["thumbnail"] = embed.thumbnail.url if embed.thumbnail else None
                        rankup_data["image_url"] = embed.image.url if embed.image else None
                        rankup_data["color"] = embed.color.value if embed.color else None

                        # Parse from description
                        # Format: "Congratulations {user}! Your {playlist} rank has improved to {emoji} {rank}!"
                        if embed.description:
                            # Extract user mention (e.g., <@283733417575710721>)
                            user_match = re.search(r"<@!?(\d+)>", embed.description)
                            if user_match:
                                user_id = user_match.group(1)
                                # Try to get member object to get username
                                try:
                                    guild = bot.get_guild(Config.get_guild_id())
                                    if guild:
                                        member = guild.get_member(int(user_id))
                                        if member:
                                            rankup_data["user"] = member.display_name or member.name
                                        else:
                                            rankup_data["user"] = f"User {user_id}"
                                    else:
                                        rankup_data["user"] = f"User {user_id}"
                                except (ValueError, AttributeError):
                                    rankup_data["user"] = f"User {user_id}"

                            # Extract mode/playlist (e.g., "Your 2v2 rank" or "Your 4v4 rank")
                            mode_match = re.search(r"Your (\d+v\d+) rank", embed.description)
                            if mode_match:
                                rankup_data["mode"] = mode_match.group(1)

                            # Extract rank - Format: "improved to {emoji} {rank}!"
                            # Emoji can be custom Discord emoji like <:c2:id> or unicode, followed by rank name
                            # Match everything after "improved to" until "!"
                            rank_match = re.search(r"improved to (.+?)!", embed.description)
                            if rank_match:
                                rank_text = rank_match.group(1).strip()

                                # Remove Discord emoji codes (e.g., <:c2:123456789>)
                                rank_text = re.sub(r"<:\w+:\d+>", "", rank_text).strip()
                                # Remove emoji text codes (e.g., :c2:, :p2:)
                                rank_text = re.sub(r":\w+:", "", rank_text).strip()

                                rankup_data["new_rank"] = rank_text
                                # Fallback: Set a default value
                                rankup_data["new_rank"] = "New Rank"

                    # Extract user from message content if not found in embed
                    if message.content and not rankup_data.get("user"):
                        # Format: "<@283733417575710721> 🚀 Rank Promotion Notification!"
                        user_match = re.search(r"<@!?(\d+)>", message.content)
                        if user_match:
                            user_id = user_match.group(1)
                            try:
                                guild = bot.get_guild(Config.get_guild_id())
                                if guild:
                                    member = guild.get_member(int(user_id))
                                    if member:
                                        rankup_data["user"] = member.display_name or member.name
                                    else:
                                        rankup_data["user"] = f"User {user_id}"
                                else:
                                    rankup_data["user"] = f"User {user_id}"
                            except (ValueError, AttributeError):
                                rankup_data["user"] = f"User {user_id}"

                    rankups.append(rankup_data)

                    # Stop if we have enough
                    if len(rankups) >= limit:
                        break

            return rankups

        # Run async function
        import asyncio

        rankups = asyncio.run_coroutine_threadsafe(fetch_rankups(), bot.loop).result(timeout=10)

        if rankups is None:
            return jsonify({"error": "Rocket League channel not found"}), 404

        result = {"success": True, "rankups": rankups, "count": len(rankups)}

        # Cache result for 60 seconds
        cache.set(cache_key, result, ttl=60)

        return jsonify(result)

    except Exception as e:
        import traceback

        logger.error(f"Error fetching latest rank-ups: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch rank-ups: {str(e)}"}), 500


@app.route("/api/memes/<message_id>/upvote", methods=["POST"])
@token_required
def toggle_upvote_meme(message_id):
    """Toggle upvote on a meme - custom system (not Discord reactions)"""
    try:
        discord_id = request.discord_id
        if discord_id in ["legacy_user", "unknown"]:
            return jsonify({"error": "Discord authentication required"}), 401

        # Load current upvotes
        upvotes = load_upvotes()

        # Initialize message upvotes if not exists
        if message_id not in upvotes:
            upvotes[message_id] = []

        # Check if user has already upvoted via Discord
        # (reuse logic from get_meme_reactions)
        has_discord_upvoted = False
        bot = app.config.get("bot_instance")
        if bot:
            meme_channel_id = Config.MEME_CHANNEL_ID
            if meme_channel_id:

                async def fetch_discord_user_reacted():
                    channel = bot.get_channel(meme_channel_id)
                    if not channel:
                        return False
                    try:
                        message = await channel.fetch_message(int(message_id))
                        for reaction in message.reactions:
                            emoji_str = str(reaction.emoji)
                            if emoji_str in NEGATIVE_EMOJIS:
                                continue
                            users = [user async for user in reaction.users()]
                            non_bot_users = [user for user in users if not user.bot]
                            if any(str(user.id) == str(discord_id) for user in non_bot_users):
                                return True
                        return False
                    except Exception:
                        return False

                import asyncio

                try:
                    has_discord_upvoted = asyncio.run_coroutine_threadsafe(
                        fetch_discord_user_reacted(), bot.loop
                    ).result(timeout=5)
                except Exception:
                    pass

        if has_discord_upvoted:
            return jsonify(
                {
                    "error": "User has already upvoted via Discord. Cannot upvote again.",
                    "has_discord_upvoted": True,
                    "success": False,
                    "message_id": message_id,
                }
            ), 400

        # Check if user has already upvoted (custom)
        user_upvotes = upvotes[message_id]
        has_upvoted = discord_id in user_upvotes

        # Toggle the upvote
        if has_upvoted:
            # Remove upvote
            user_upvotes.remove(discord_id)
            action = "removed"
        else:
            # Add upvote
            user_upvotes.append(discord_id)
            action = "added"

        # Save updated upvotes
        save_upvotes(upvotes)

        # Get current counts
        upvote_count = len(user_upvotes)
        has_upvoted_now = discord_id in user_upvotes

        logger.info(
            f"{'➖' if action == 'removed' else '➕'} Upvote {action} by {request.username} "
            f"on meme {message_id} (total: {upvote_count})"
        )

        return jsonify(
            {
                "success": True,
                "upvotes": upvote_count,
                "has_upvoted": has_upvoted_now,
                "action": action,
                "message_id": message_id,
            }
        )

    except Exception as e:
        import traceback

        logger.error(f"Error toggling upvote: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to toggle upvote: {str(e)}"}), 500


@app.route("/api/memes/<message_id>/reactions", methods=["GET"])
@token_required
def get_meme_reactions(message_id):
    """Get upvote counts for a meme (custom + Discord reactions combined)"""
    try:
        discord_id = request.discord_id

        # Load custom upvotes
        custom_upvotes = load_upvotes()
        user_upvotes = custom_upvotes.get(message_id, [])
        custom_count = len(user_upvotes)

        # Check if current user has custom upvoted
        has_custom_upvoted = False
        if discord_id not in ["legacy_user", "unknown"]:
            has_custom_upvoted = discord_id in user_upvotes

        # Get Discord reactions count and check if user has upvoted via Discord
        discord_count = 0
        has_discord_upvoted = False
        bot = app.config.get("bot_instance")
        if bot:
            meme_channel_id = Config.MEME_CHANNEL_ID
            if meme_channel_id:

                async def fetch_discord_reactions_and_user():
                    channel = bot.get_channel(meme_channel_id)
                    if not channel:
                        return 0, False

                    try:
                        message = await channel.fetch_message(int(message_id))
                        # Count all positive reactions (exclude negative emojis and bots)
                        total_count = 0
                        user_reacted = False
                        for reaction in message.reactions:
                            emoji_str = str(reaction.emoji)

                            # Skip negative emojis
                            if emoji_str in NEGATIVE_EMOJIS:
                                continue

                            # Count reactions from non-bot users
                            users = [user async for user in reaction.users()]
                            non_bot_users = [user for user in users if not user.bot]
                            total_count += len(non_bot_users)
                            # Check if current user has reacted
                            if discord_id not in ["legacy_user", "unknown"]:
                                if any(str(user.id) == str(discord_id) for user in non_bot_users):
                                    user_reacted = True

                        return total_count, user_reacted
                    except Exception:
                        return 0, False

                import asyncio

                try:
                    discord_count, has_discord_upvoted = asyncio.run_coroutine_threadsafe(
                        fetch_discord_reactions_and_user(), bot.loop
                    ).result(timeout=5)
                except Exception:
                    pass  # Silently fail, use custom count only

        # Combine both counts
        total_upvotes = custom_count + discord_count

        return jsonify(
            {
                "success": True,
                "message_id": message_id,
                "upvotes": total_upvotes,
                "custom_upvotes": custom_count,
                "discord_upvotes": discord_count,
                "has_upvoted": has_custom_upvoted,
                "has_discord_upvoted": has_discord_upvoted,
            }
        )

    except Exception as e:
        import traceback

        logger.error(f"Error fetching reactions: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch reactions: {str(e)}"}), 500


# ===== COG MANAGEMENT ENDPOINTS =====


@app.route("/api/cogs", methods=["GET"])
@token_required
@require_permission("all")
@log_config_action("cogs_list")
def get_cogs():
    """Get list of all cogs with their status"""
    try:
        # Get bot instance
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Get cog manager instance
        cog_manager = bot.get_cog("CogManager")
        if not cog_manager:
            return jsonify({"error": "CogManager not available"}), 503

        # Cog descriptions and metadata
        cog_metadata = {
            "APIServer": {
                "description": "Manages the Flask REST API server for the admin panel",
                "icon": "api",
                "category": "core",
                "features": [
                    "Waitress WSGI Server",
                    "JWT Token Auth",
                    "CORS Support",
                    "Hot Reload via Cog System",
                    "Port Binding Retry (8×3s)",
                    "Graceful Shutdown",
                    "/apistatus Command",
                    "/apirestart Command",
                ],
            },
            "CogManager": {
                "description": "Dynamic cog loading, unloading, and reloading system",
                "icon": "settings",
                "category": "core",
                "features": [
                    "/load Command",
                    "/unload Command",
                    "/reload Command",
                    "/listcogs Command",
                    "/logs <cog> Command",
                    "Interactive Dropdown Selection",
                    "Disabled Cogs State File",
                    "Log Censoring (URLs/Secrets)",
                ],
            },
            "Changelog": {
                "description": "Manages changelog notifications and version updates",
                "icon": "update",
                "category": "notifications",
                "features": [
                    "/changelog Command",
                    "GPT-4.1-nano Title Generation",
                    "Discord Markdown Formatting",
                    "Changelog Role Ping",
                    "Opt-in Button",
                    "Persistent Views",
                    "/update_changelog_view Command",
                ],
            },
            "DailyMeme": {
                "description": "Automated daily meme posting from Reddit and Lemmy",
                "icon": "image",
                "category": "content",
                "features": [
                    "Reddit Top Posts",
                    "Lemmy Community Support",
                    "Daily Scheduled Post (10 AM)",
                    "/testmeme Command",
                    "/memesubreddits Management",
                    "/lemmycommunities Management",
                    "/memesources Enable/Disable",
                    "/dailyconfig Command",
                ],
            },
            "DiscordLogging": {
                "description": "Logs bot events and errors to a Discord channel",
                "icon": "analytics",
                "category": "monitoring",
                "features": [
                    "INFO/WARNING/ERROR Levels",
                    "Cog Color-coded Embeds",
                    "Emoji Prefixes per Cog",
                    "/togglediscordlogs Command",
                    "/testdiscordlog Command",
                    "Auto-disable on Errors",
                    "Rate Limiting (1 msg/2s)",
                ],
            },
            "GamingHub": {
                "description": "Community gaming features with presence tracking",
                "icon": "sports_esports",
                "category": "community",
                "features": [
                    "Online/Idle/DND/Offline Status",
                    "Current Game Detection",
                    "Game Request Posts",
                    "Accept/Decline/Maybe Buttons",
                    "DM Notifications to Requester",
                    "Auto-fill Current Game",
                    "Member Filter (All/Online/Playing)",
                    "Persistent Views Restore",
                ],
            },
            "Leaderboard": {
                "description": "Server activity leaderboard and statistics",
                "icon": "leaderboard",
                "category": "community",
                "features": [
                    "/leaderboard Command",
                    "Message Count Tracking",
                    "Image Share Tracking",
                    "Meme Requests Count",
                    "Memes Generated Count",
                    "Resolved Tickets Count",
                    "Rocket League Rank Display",
                    "Interactive Dropdown",
                ],
            },
            "MemeGenerator": {
                "description": "Create custom memes with Imgflip templates",
                "icon": "create",
                "category": "content",
                "features": [
                    "/creatememe Command",
                    "100+ Imgflip Templates",
                    "Interactive Template Selector",
                    "Dynamic Text Input Modal",
                    "1-5 Text Boxes per Template",
                    "Imgflip API Integration",
                    "Author Tracking in Embed",
                    "/refreshtemplates Command",
                ],
            },
            "ModPerks": {
                "description": "Moderator utilities and management tools",
                "icon": "shield",
                "category": "moderation",
                "features": [
                    "/mod Command",
                    "/modpanel Interactive View",
                    "/modoverview Stats Display",
                    "/moddetails Member Stats",
                    "/optins Management",
                    "Permission-based Access",
                    "Admin/Mod Role Checks",
                ],
            },
            "Preferences": {
                "description": "User preference management for notifications",
                "icon": "tune",
                "category": "user",
                "features": [
                    "/preferences Command",
                    "Changelog Role Toggle",
                    "Daily Meme Role Toggle",
                    "Interactive Buttons",
                    "Role Add/Remove",
                    "JSON Preference Storage",
                    "Persistent State",
                ],
            },
            "Presence": {
                "description": "Bot status and activity rotation system",
                "icon": "visibility",
                "category": "core",
                "features": [
                    "Playing Activity",
                    "Watching Activity",
                    "Listening Activity",
                    "Custom Status Messages",
                    "Server Count Display",
                    "Member Count Display",
                    "Hourly Rotation (3600s)",
                ],
            },
            "Profile": {
                "description": "User profile viewing and statistics",
                "icon": "person",
                "category": "user",
                "features": [
                    "/profile Command",
                    "Discord Join Date",
                    "Server Join Date",
                    "Role List",
                    "Rocket League Ranks",
                    "Activity Stats",
                    "Avatar Thumbnail",
                ],
            },
            "RocketLeague": {
                "description": "Rocket League rank tracking with automatic updates",
                "icon": "rocket_launch",
                "category": "gaming",
                "features": [
                    "/rocket Hub Command",
                    "/setrlaccount (Epic/Steam)",
                    "/rlstats View Stats",
                    "/unlinkrlaccount Command",
                    "1v1/2v2/3v3/4v4 Support",
                    "Division Tracking (I-IV)",
                    "Auto Rank Check (3h)",
                    "Promotion Embeds + Congrats",
                    "FlareSolverr Cloudflare Bypass",
                    "/restorecongratsview Admin",
                ],
            },
            "RoleInfo": {
                "description": "Server role information and descriptions",
                "icon": "badge",
                "category": "info",
                "features": [
                    "/roleinfo Command",
                    "Role Descriptions",
                    "Permission List",
                    "Member Count",
                    "Role Color Display",
                    "Role ID Display",
                    "Formatted Embed",
                ],
            },
            "ServerGuide": {
                "description": "Interactive server guide with quick access buttons",
                "icon": "menu_book",
                "category": "info",
                "features": [
                    "/server-guide Command",
                    "Help Button",
                    "Ticket Button",
                    "Profile Button",
                    "Rocket League Hub",
                    "Warframe Hub",
                    "Preferences Button",
                    "Interactive Embeds",
                ],
            },
            "SupportButtons": {
                "description": "Persistent support buttons for common actions",
                "icon": "support_agent",
                "category": "support",
                "features": [
                    "/create-button Command",
                    "Ticket Buttons",
                    "Slash Command Buttons",
                    "Prefix Command Buttons",
                    "Custom Labels/Emojis",
                    "Persistent Views",
                    "JSON Persistence",
                ],
            },
            "TicketSystem": {
                "description": "Support ticket system with transcripts",
                "icon": "confirmation_number",
                "category": "support",
                "features": [
                    "/ticket Command",
                    "Support Categories",
                    "Claim/Close/Reopen",
                    "Add/Remove Users",
                    "Transcript Generation",
                    "Email Transcripts",
                    "Numbered Tickets",
                    "JSON Persistence",
                ],
            },
            "TodoList": {
                "description": "Server-wide todo list management",
                "icon": "checklist",
                "category": "productivity",
                "features": [
                    "/todo-update Command",
                    "Interactive View",
                    "Add/Complete/Delete",
                    "Priority Levels",
                    "Persistent Storage",
                    "Formatted Display",
                    "JSON Persistence",
                ],
            },
            "Utility": {
                "description": "General utility commands and helper functions",
                "icon": "build",
                "category": "utility",
                "features": [
                    "/help Command",
                    "/status Command",
                    "/clear Command",
                    "/say Command",
                    "/sync Command",
                    "Embed Utils",
                    "Admin Tools",
                ],
            },
            "Warframe": {
                "description": "Warframe market integration and game status",
                "icon": "videogame_asset",
                "category": "gaming",
                "features": [
                    "/warframe Hub",
                    "Game Status",
                    "Market Search",
                    "Invasions Display",
                    "Sortie Info",
                    "Price Statistics",
                    "Top Orders",
                    "Warframe.market API",
                ],
            },
            "Welcome": {
                "description": "Welcome system with rule acceptance and roles",
                "icon": "waving_hand",
                "category": "community",
                "features": [
                    "Interest Selection",
                    "Rules Acceptance",
                    "Member Role Grant",
                    "Random Greetings",
                    "Server Guide Link",
                    "Persistent Views",
                    "Event Listeners",
                ],
            },
        }

        # Get all cog files and their class names
        all_cogs = cog_manager.get_all_cog_files()

        # Get loaded cogs
        loaded_cogs = list(bot.cogs.keys())

        # Get disabled cogs
        disabled_cogs = cog_manager.get_disabled_cogs()

        # Build response
        cogs_list = []
        for file_name, class_name in all_cogs.items():
            status = "loaded" if class_name in loaded_cogs else "unloaded"
            if file_name in disabled_cogs:
                status = "disabled"

            # Use file_name as key for metadata lookup
            metadata = cog_metadata.get(
                file_name,
                {
                    "description": f"Discord bot module: {class_name}",
                    "icon": "extension",
                    "category": "other",
                    "features": [],
                },
            )

            cogs_list.append(
                {
                    "name": class_name,
                    "file_name": file_name,
                    "status": status,
                    "description": metadata["description"],
                    "icon": metadata["icon"],
                    "category": metadata["category"],
                    "features": metadata["features"],
                    "can_load": status in ["unloaded", "disabled"],
                    "can_unload": status == "loaded" and class_name != "CogManager",
                    "can_reload": status == "loaded" and class_name != "CogManager",
                    "can_view_logs": status == "loaded",
                }
            )

        # Sort by category, then by name
        category_order = [
            "core",
            "community",
            "content",
            "gaming",
            "moderation",
            "support",
            "user",
            "info",
            "productivity",
            "utility",
            "notifications",
            "monitoring",
            "other",
        ]
        cogs_list.sort(
            key=lambda c: (category_order.index(c["category"]) if c["category"] in category_order else 999, c["name"])
        )

        return jsonify(
            {
                "success": True,
                "cogs": cogs_list,
                "total": len(cogs_list),
                "loaded_count": len([c for c in cogs_list if c["status"] == "loaded"]),
                "disabled_count": len([c for c in cogs_list if c["status"] == "disabled"]),
            }
        )

    except Exception as e:
        logger.error(f"Error getting cogs list: {e}")
        return jsonify({"error": f"Failed to get cogs list: {str(e)}"}), 500


@app.route("/api/cogs/<cog_name>/load", methods=["POST"])
@token_required
@require_permission("all")
def load_cog(cog_name):
    """Load a cog"""
    try:
        # Get bot instance
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Get cog manager instance
        cog_manager = bot.get_cog("CogManager")
        if not cog_manager:
            return jsonify({"error": "CogManager not available"}), 503

        # Find the file name for this cog
        all_cogs = cog_manager.get_all_cog_files()
        file_name = None

        # Try to match by class name first, then by file name
        for fname, cname in all_cogs.items():
            if cname == cog_name or fname == cog_name:
                file_name = fname
                break

        if not file_name:
            return jsonify({"error": f"Cog '{cog_name}' not found"}), 404

        # Check if already loaded
        loaded_cogs = list(bot.cogs.keys())
        class_name = all_cogs.get(file_name, file_name)
        if class_name in loaded_cogs:
            return jsonify({"error": f"Cog '{cog_name}' is already loaded"}), 400

        # Load the cog
        import asyncio

        success, message = asyncio.run_coroutine_threadsafe(cog_manager.load_cog_api(file_name), bot.loop).result(
            timeout=10
        )

        if success:
            return jsonify(
                {
                    "success": True,
                    "message": message,
                    "cog": {"name": class_name, "file_name": file_name, "status": "loaded"},
                }
            )
        else:
            return jsonify({"error": message}), 500

    except Exception as e:
        logger.error(f"Error loading cog {cog_name}: {e}")
        return jsonify({"error": f"Failed to load cog: {str(e)}"}), 500


@app.route("/api/cogs/<cog_name>/unload", methods=["POST"])
@token_required
@require_permission("all")
def unload_cog(cog_name):
    """Unload a cog"""
    try:
        # Get bot instance
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Get cog manager instance
        cog_manager = bot.get_cog("CogManager")
        if not cog_manager:
            return jsonify({"error": "CogManager not available"}), 503

        # Check if trying to unload critical cogs
        if cog_name.lower() == "cogmanager":
            return jsonify({"error": "Cannot unload CogManager"}), 400

        # Check if trying to unload APIServer
        if cog_name.lower() == "apiserver":
            return jsonify({"error": "APIServer cannot be unloaded. Use reload instead."}), 403

        # Find the file name for this cog
        all_cogs = cog_manager.get_all_cog_files()
        file_name = None
        class_name = cog_name

        # Try to match by class name first, then by file name
        for fname, cname in all_cogs.items():
            if cname == cog_name or fname == cog_name:
                file_name = fname
                class_name = cname
                break

        if not file_name:
            return jsonify({"error": f"Cog '{cog_name}' not found"}), 404

        # Check if loaded
        loaded_cogs = list(bot.cogs.keys())
        if class_name not in loaded_cogs:
            return jsonify({"error": f"Cog '{cog_name}' is not loaded"}), 400

        # Unload the cog
        import asyncio

        success, message = asyncio.run_coroutine_threadsafe(cog_manager.unload_cog_api(class_name), bot.loop).result(
            timeout=10
        )

        if success:
            return jsonify(
                {
                    "success": True,
                    "message": message,
                    "cog": {"name": class_name, "file_name": file_name, "status": "unloaded"},
                }
            )
        else:
            return jsonify({"error": message}), 500

    except Exception as e:
        logger.error(f"Error unloading cog {cog_name}: {e}")
        return jsonify({"error": f"Failed to unload cog: {str(e)}"}), 500


@app.route("/api/cogs/<cog_name>/reload", methods=["POST"])
@token_required
@require_permission("all")
def reload_cog(cog_name):
    """Reload a cog"""
    try:
        # Get bot instance
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Get cog manager instance
        cog_manager = bot.get_cog("CogManager")
        if not cog_manager:
            return jsonify({"error": "CogManager not available"}), 503

        # Check if trying to reload CogManager
        if cog_name.lower() == "cogmanager":
            return jsonify({"error": "Cannot reload CogManager"}), 400

        # Find the file name for this cog
        all_cogs = cog_manager.get_all_cog_files()
        file_name = None
        class_name = cog_name

        # Try to match by class name first, then by file name
        for fname, cname in all_cogs.items():
            if cname == cog_name or fname == cog_name:
                file_name = fname
                class_name = cname
                break

        if not file_name:
            return jsonify({"error": f"Cog '{cog_name}' not found"}), 404

        # Check if loaded
        loaded_cogs = list(bot.cogs.keys())
        if class_name not in loaded_cogs:
            return jsonify({"error": f"Cog '{cog_name}' is not loaded"}), 400

        # Reload the cog using the API method
        import asyncio

        # Longer timeout for APIServer and other slow-loading cogs
        timeout = 35 if class_name == "APIServer" else 15

        try:
            success, message = asyncio.run_coroutine_threadsafe(
                cog_manager.reload_cog_api(class_name), bot.loop
            ).result(timeout=timeout)

            if success:
                return jsonify(
                    {
                        "success": True,
                        "message": message,
                        "cog": {"name": class_name, "file_name": file_name, "status": "loaded"},
                    }
                )
            else:
                return jsonify({"error": message}), 500

        except asyncio.TimeoutError:
            # For APIServer, timeout might occur during reload (expected)
            # Wait a bit more and check if it's actually loaded
            if class_name == "APIServer":
                import time

                time.sleep(3)
                # Check if APIServer is now loaded
                if "APIServer" in bot.cogs:
                    return jsonify(
                        {
                            "success": True,
                            "message": f"Cog '{class_name}' reloaded successfully (delayed)",
                            "cog": {"name": class_name, "file_name": file_name, "status": "loaded"},
                        }
                    )
            raise

    except Exception as e:
        # Don't log expected errors for APIServer reload
        if not (class_name == "APIServer" and ("timeout" in str(e).lower() or "file descriptor" in str(e).lower())):
            logger.error(f"Error reloading cog {cog_name}: {e}")
        return jsonify({"error": f"Failed to reload cog: {str(e)}"}), 500


@app.route("/api/cogs/<cog_name>/logs", methods=["GET"])
@token_required
@require_permission("all")
def get_cog_logs(cog_name):
    """Get logs for a specific cog"""
    try:
        # Get bot instance
        bot = app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Get cog manager instance
        cog_manager = bot.get_cog("CogManager")
        if not cog_manager:
            return jsonify({"error": "CogManager not available"}), 503

        # Find the actual cog name
        all_cogs = cog_manager.get_all_cog_files()
        actual_cog_name = cog_name

        # Try to match by class name first, then by file name
        for fname, cname in all_cogs.items():
            if cname == cog_name or fname == cog_name:
                actual_cog_name = cname
                break

        # Get logs using the cog manager's method
        import asyncio

        # Create a mock context for the log retrieval
        class MockContext:
            pass

        mock_ctx = MockContext()

        # Get the logs by calling the internal method
        try:
            # We'll extract the log reading logic from _show_cog_logs
            import os

            # Read log file - use absolute path
            log_file = os.path.join(os.getcwd(), "Logs", "HazeBot.log")

            if not os.path.exists(log_file):
                # Try alternative paths
                alternative_paths = [
                    "Logs/HazeBot.log",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)), "Logs", "HazeBot.log"),
                    "/home/liq/gitProjects/HazeBot/Logs/HazeBot.log",
                ]

                for alt_path in alternative_paths:
                    if os.path.exists(alt_path):
                        log_file = alt_path
                        break
                else:
                    return jsonify({"error": "Log file not found"}), 404

            # Read last 1000 lines
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                lines = lines[-1000:]

            # Filter logs for this cog
            cog_filter = actual_cog_name.lower()
            filtered_logs = [line for line in lines if cog_filter in line.lower()]

            # Format logs for API response
            logs = []
            for log_line in filtered_logs[-50:]:  # Last 50 entries
                parts = log_line.strip().split(None, 3)
                if len(parts) >= 4:
                    timestamp = parts[0]
                    time = parts[1]
                    level = parts[2]
                    message = parts[3] if len(parts) > 3 else ""

                    # Censor sensitive data
                    message = cog_manager._censor_sensitive_data(message)

                    logs.append({"timestamp": timestamp, "time": time, "level": level, "message": message})

            # Count log levels
            info_count = sum(1 for log in logs if log["level"] == "INFO")
            warning_count = sum(1 for log in logs if log["level"] == "WARNING")
            error_count = sum(1 for log in logs if log["level"] == "ERROR")
            debug_count = sum(1 for log in logs if log["level"] == "DEBUG")

            return jsonify(
                {
                    "success": True,
                    "cog_name": actual_cog_name,
                    "logs": logs,
                    "total_entries": len(filtered_logs),
                    "returned_entries": len(logs),
                    "statistics": {
                        "info": info_count,
                        "warning": warning_count,
                        "error": error_count,
                        "debug": debug_count,
                    },
                    "log_file": log_file,
                }
            )

        except Exception as e:
            logger.error(f"Error reading logs for {cog_name}: {e}")
            return jsonify({"error": f"Failed to read logs: {str(e)}"}), 500

    except Exception as e:
        logger.error(f"Error getting cog logs for {cog_name}: {e}")
        return jsonify({"error": f"Failed to get cog logs: {str(e)}"}), 500


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
