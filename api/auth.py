"""
Authentication and authorization for the Flask API
"""

import os
import threading
from datetime import datetime
from functools import wraps

import jwt
from flask import jsonify, request

from Utils.Logger import Logger as logger
from api.helpers import log_action, log_user_activity, update_app_usage

# Thread lock for JWT decode (prevents race conditions)
jwt_decode_lock = threading.Lock()

# Discord OAuth2 Configuration
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "https://api.haze.pro/api/discord/callback")
DISCORD_API_ENDPOINT = "https://discord.com/api/v10"

# Role-based permissions
ROLE_PERMISSIONS = {
    "admin": ["all"],
    "mod": ["all"],
    "lootling": ["meme_generator"],
}

# Will be initialized by init_auth()
Config = None
app_instance = None
active_sessions_dict = None
recent_activity_list = None
max_activity_log_value = None
app_usage_file_path = None
analytics_aggregator = None


def init_auth(
    config,
    app=None,
    active_sessions=None,
    recent_activity=None,
    max_activity_log=None,
    app_usage_file=None,
    analytics=None,
):
    """Initialize auth module with Config and app dependencies"""
    global Config, app_instance, active_sessions_dict, recent_activity_list, max_activity_log_value
    global app_usage_file_path, analytics_aggregator
    Config = config
    if app is not None:
        app_instance = app
        active_sessions_dict = active_sessions
        recent_activity_list = recent_activity
        max_activity_log_value = max_activity_log
        app_usage_file_path = app_usage_file
        analytics_aggregator = analytics


def create_token_required_decorator():
    """Create token_required decorator with initialized dependencies"""

    # The token_required function already returns a decorator when given all parameters
    # We just need to create a wrapper that binds those parameters
    def wrapper(f):
        return token_required(
            f,
            app_instance,
            Config,
            active_sessions_dict,
            recent_activity_list,
            max_activity_log_value,
            app_usage_file_path,
        )

    return wrapper


def get_user_role_from_discord(member_data, guild_id, Config):
    """Determine user role based on Discord guild roles"""
    role_ids = member_data.get("roles", [])
    # Ensure all role IDs are strings for comparison
    role_ids = [str(rid) for rid in role_ids]

    # Get role IDs from Config
    admin_role_id = str(Config.ADMIN_ROLE_ID)
    mod_role_id = str(Config.MODERATOR_ROLE_ID)

    # Debug logging
    logger.info(
        f"🔍 Discord Auth - Checking roles: user_roles={role_ids}, admin_id={admin_role_id}, mod_id={mod_role_id}"
    )

    # Check for admin/mod roles (mods get same permissions as admins for now)
    if admin_role_id in role_ids:
        logger.info("✅ User identified as ADMIN")
        return "admin"
    elif mod_role_id in role_ids:
        logger.info("✅ User identified as MOD (with admin permissions)")
        return "mod"
    else:
        logger.info("👤 User identified as LOOTLING")
        return "lootling"


def token_required(f, app, Config, active_sessions, recent_activity, max_activity_log, app_usage_file):
    """Simple authentication decorator"""

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

            # Generate a unique session ID
            # Priority: 1. X-Session-ID header (from Flutter app)
            #           2. session_id from JWT token
            #           3. Fallback: Hash of discord_id + token
            session_id_header = request.headers.get("X-Session-ID")

            if session_id_header and session_id_header != "Unknown":
                # Use session ID from Flutter app (preferred method)
                request.session_id = session_id_header
            elif "session_id" in data:
                # Use session ID from JWT token
                request.session_id = data["session_id"]
            else:
                # Fallback: Create session ID from user data
                import hashlib

                session_data = f"{data.get('discord_id', 'unknown')}_{token[:20]}"
                request.session_id = hashlib.sha256(session_data.encode()).hexdigest()[:32]

            # Update active session tracking
            # Get real client IP (handle proxy/forwarded requests)
            real_ip = (
                request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                or request.headers.get("X-Real-IP", "").strip()
                or request.remote_addr
            )

            # Better device detection with proper priority
            user_agent = request.headers.get("User-Agent", "Unknown")
            device_info = request.headers.get("X-Device-Info")
            platform_header = request.headers.get("X-Platform", "Unknown")
            app_version = request.headers.get("X-App-Version", "Unknown")
            
            if not device_info or device_info == "Unknown":
                # Priority 1: Use X-Platform header if present (sent by Flutter app)
                # This works for ALL Flutter builds: Web, Android, iOS, Desktop
                if platform_header and platform_header != "Unknown":
                    device_info = platform_header
                
                # Priority 2: Check for Flutter App identifiers in User-Agent
                elif "Chillventory" in user_agent or "Testventory" in user_agent:
                    # Flutter app with custom User-Agent
                    if "Android" in user_agent:
                        device_info = "Android"
                    elif "iPhone" in user_agent or "iPad" in user_agent:
                        device_info = "iOS"
                    elif "Windows" in user_agent:
                        device_info = "Windows Desktop"
                    elif "Linux" in user_agent:
                        device_info = "Linux Desktop"
                    elif "Macintosh" in user_agent:
                        device_info = "macOS Desktop"
                    else:
                        device_info = "Flutter App"
                
                # Priority 3: Detect Web Browser (Analytics Dashboard or external)
                elif "Mozilla" in user_agent and ("Chrome" in user_agent or "Firefox" in user_agent or "Safari" in user_agent or "Edge" in user_agent):
                    # Check if this is Analytics Dashboard (no app version header)
                    if app_version == "Unknown" and request.endpoint and "analytics" in request.endpoint.lower():
                        device_info = "Analytics Dashboard"
                    else:
                        device_info = "Web Browser"
                
                # Priority 4: API Client / Script
                elif "python-requests" in user_agent.lower() or "curl" in user_agent.lower() or "postman" in user_agent.lower():
                    device_info = "API Client"
                
                # Priority 5: Fallback
                else:
                    # Extract first part of User-Agent (e.g., "Dart/3.5" → "Dart")
                    device_info = user_agent.split("/")[0] if "/" in user_agent else "Unknown"
            
            # Determine endpoint and check if it's analytics-related (before session tracking)
            endpoint_name = request.endpoint or "unknown"
            referer = request.headers.get("Referer", "")
            
            is_analytics_request = (
                # Endpoint name checks
                endpoint_name.startswith("get_analytics") or
                endpoint_name.startswith("reset_analytics") or
                endpoint_name.startswith("get_error_analytics") or
                endpoint_name.startswith("get_feature") or
                # Path checks
                "/analytics/" in request.path.lower() or
                # Referer checks (login from analytics page)
                "/analytics/" in referer.lower() or
                "/login" in referer.lower() and "/analytics/" in referer.lower()
            )
            
            session_info = {
                "username": request.username,
                "discord_id": request.discord_id,
                "role": request.user_role,
                "permissions": request.user_permissions,
                "last_seen": Config.get_utc_now().isoformat(),
                "ip": real_ip,
                "user_agent": user_agent,
                "endpoint": endpoint_name,
                "app_version": request.headers.get("X-App-Version", "Unknown"),
                "platform": request.headers.get("X-Platform", "Unknown"),
                "device_info": device_info,
            }

            # Check if this is a new session (first time seeing this session_id)
            is_new_session = request.session_id not in active_sessions
            active_sessions[request.session_id] = session_info

            # Analytics: Start session tracking for new sessions (skip analytics dashboard)
            if is_new_session and analytics_aggregator is not None and not is_analytics_request:
                try:
                    analytics_aggregator.start_session(
                        session_id=request.session_id,
                        discord_id=request.discord_id,
                        username=request.username,
                        device_info=session_info["device_info"],
                        platform=session_info["platform"],
                        app_version=session_info["app_version"],
                        ip_address=real_ip,
                    )
                except Exception as e:
                    logger.error(f"Failed to start analytics session: {e}")

            # Analytics: Update session activity (skip high-frequency endpoints + analytics dashboard)
            if analytics_aggregator is not None and not is_analytics_request:
                # Endpoints to exclude from analytics (reduce noise)
                excluded_endpoints = [
                    'auth_routes.ping',           # Health checks
                    'auth_routes.verify_token',   # Token verification
                    'auth_routes.refresh_token',  # Token refresh
                    'admin_routes.active_sessions', # Live monitoring
                ]
                
                if endpoint_name not in excluded_endpoints:
                    try:
                        analytics_aggregator.update_session(
                            session_id=request.session_id, endpoint=endpoint_name
                        )
                    except Exception as e:
                        logger.error(f"Failed to update analytics session: {e}")

            # Update app usage tracking (persistent)
            update_app_usage(request.discord_id, app_usage_file, Config)

            # Log activity (filtering is done inside log_user_activity)
            log_user_activity(
                request.username,
                request.discord_id,
                request.method,
                endpoint_name,
                recent_activity,
                max_activity_log,
                Config,
                {"path": request.path},
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
