"""
Authentication and user management routes
"""

import os
import secrets
from datetime import timedelta

import jwt
import requests
from flask import Blueprint, jsonify, redirect, request
from urllib.parse import urlencode

from api.auth import (
    DISCORD_API_ENDPOINT,
    DISCORD_CLIENT_ID,
    DISCORD_CLIENT_SECRET,
    DISCORD_REDIRECT_URI,
    ROLE_PERMISSIONS,
    get_user_role_from_discord,
    token_required,
)
from api.helpers import log_action
from Utils.Logger import Logger as logger

auth_routes = Blueprint("auth_routes", __name__)


def init_auth_routes(app, Config, active_sessions, recent_activity, max_activity_log, app_usage_file):
    """Initialize auth routes with dependencies"""

    # Create token_required decorator with dependencies
    def token_required_wrapper(f):
        return token_required(f, app, Config, active_sessions, recent_activity, max_activity_log, app_usage_file)

    @auth_routes.route("/api/health", methods=["GET"])
    def health():
        """
        Enhanced health check endpoint with detailed system status
        
        Query Parameters:
            detailed (str): Set to 'true' for detailed health checks
            
        Returns:
            200: System is healthy
            503: System is degraded or unhealthy
        """
        from datetime import datetime
        import psutil
        import os
        
        health_status = {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "service": "HazeBot API",
            "version": os.getenv("API_VERSION", "1.0.0"),
            "environment": os.getenv("ENVIRONMENT", "production")
        }
        
        # Detailed checks (optional - nur bei ?detailed=true)
        if request.args.get("detailed") == "true":
            checks = {}
            
            # Memory Check
            try:
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                checks["memory"] = {
                    "status": "ok" if memory_percent < 90 else "warning",
                    "usage_percent": round(memory_percent, 2),
                    "available_gb": round(memory.available / (1024**3), 2)
                }
                if memory_percent >= 95:
                    health_status["status"] = "degraded"
            except Exception as e:
                checks["memory"] = {"status": "error", "message": str(e)}
                health_status["status"] = "degraded"
            
            # CPU Check
            try:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                checks["cpu"] = {
                    "status": "ok" if cpu_percent < 80 else "warning",
                    "usage_percent": round(cpu_percent, 2)
                }
            except Exception as e:
                checks["cpu"] = {"status": "error", "message": str(e)}
            
            # Disk Check
            try:
                disk = psutil.disk_usage('/')
                disk_percent = disk.percent
                checks["disk"] = {
                    "status": "ok" if disk_percent < 85 else "warning",
                    "usage_percent": round(disk_percent, 2),
                    "free_gb": round(disk.free / (1024**3), 2)
                }
                if disk_percent >= 95:
                    health_status["status"] = "degraded"
            except Exception as e:
                checks["disk"] = {"status": "error", "message": str(e)}
            
            # Cache Check
            try:
                from api.cache import cache
                # Prüfe ob Cache erreichbar ist
                test_key = "_health_check_test"
                cache.set(test_key, "ok", ttl=5)
                cache_test = cache.get(test_key)
                checks["cache"] = {
                    "status": "ok" if cache_test == "ok" else "warning",
                    "type": "redis" if hasattr(cache, 'cache') else "simple"
                }
                cache.delete(test_key)
            except Exception as e:
                checks["cache"] = {"status": "error", "message": str(e)}
                health_status["status"] = "degraded"
            
            # Active Sessions Check
            try:
                session_count = len(active_sessions) if active_sessions else 0
                checks["sessions"] = {
                    "status": "ok",
                    "active_count": session_count
                }
            except Exception as e:
                checks["sessions"] = {"status": "error", "message": str(e)}
            
            # Database/Analytics Check (wenn verfügbar)
            try:
                from api.app import analytics
                if analytics:
                    checks["analytics"] = {"status": "ok", "enabled": True}
                else:
                    checks["analytics"] = {"status": "warning", "enabled": False}
            except Exception as e:
                checks["analytics"] = {"status": "info", "message": "not_initialized"}
            
            # Error Tracker Check
            try:
                from api.app import error_tracker
                if error_tracker:
                    checks["error_tracker"] = {"status": "ok", "enabled": True}
                else:
                    checks["error_tracker"] = {"status": "warning", "enabled": False}
            except Exception as e:
                checks["error_tracker"] = {"status": "info", "message": "not_initialized"}
            
            health_status["checks"] = checks
            
            # Gesamtstatus berechnen
            error_count = sum(1 for check in checks.values() if isinstance(check, dict) and check.get("status") == "error")
            if error_count > 2:
                health_status["status"] = "unhealthy"
        
        # HTTP Status Code basierend auf Status
        status_code = 200
        if health_status["status"] == "degraded":
            status_code = 503
        elif health_status["status"] == "unhealthy":
            status_code = 503
        
        return jsonify(health_status), status_code

    @auth_routes.route("/api/auth/login", methods=["POST"])
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

    @auth_routes.route("/api/discord/auth", methods=["GET"])
    def discord_auth():
        """Initiate Discord OAuth2 flow"""
        # Get state parameter from query (to track which frontend initiated OAuth)
        frontend_source = request.args.get("state", "")
        
        # Fallback: Detect from Referer header if state is empty
        if not frontend_source:
            referer = request.headers.get("Referer", "")
            if "/login" in referer or "/analytics" in referer:
                frontend_source = "analytics"
                logger.info(f"🔍 Detected Analytics from Referer: {referer}")
            elif "admin.haze.pro" in referer:
                frontend_source = "web"
                logger.info(f"🔍 Detected Flutter Web from Referer: {referer}")
        
        params = {
            "client_id": DISCORD_CLIENT_ID,
            "redirect_uri": DISCORD_REDIRECT_URI,
            "response_type": "code",
            "scope": "identify guilds.members.read",
        }
        
        # Pass state parameter through Discord OAuth flow
        if frontend_source:
            params["state"] = frontend_source

        auth_url = f"{DISCORD_API_ENDPOINT}/oauth2/authorize?{urlencode(params)}"
        logger.info(f"🔐 Generated OAuth URL for source='{frontend_source}'")
        
        return jsonify({"auth_url": auth_url})

    @auth_routes.route("/api/discord/callback", methods=["GET"])
    def discord_callback():
        """Handle Discord OAuth2 callback with multi-layer source detection"""
        # Layer 1: State parameter from Discord (most reliable when present)
        state = request.args.get("state", "")
        
        # Layer 2: Referer header detection (robust fallback)
        referer = request.headers.get("Referer", "")
        referer_hint = ""
        if "discord.com" in referer:
            # Discord redirected us - this is the common case
            # We can't detect from Discord's referer, so rely on state
            referer_hint = ""
        elif "/login" in referer or "/analytics" in referer or "api.haze.pro/login" in referer:
            referer_hint = "analytics"
        elif "admin.haze.pro" in referer:
            referer_hint = "web"
        
        # Determine frontend source with fallback chain
        frontend_source = state or referer_hint or "web"
        
        # Debug logging
        logger.info(f"🔍 OAuth callback - state: '{state}' | referer: '{referer}' | hint: '{referer_hint}' | using: '{frontend_source}'")
        
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

        member_response = requests.get(
            f"{DISCORD_API_ENDPOINT}/users/@me/guilds/{guild_id}/member", headers=user_headers
        )

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
        role = get_user_role_from_discord(member_data, guild_id, Config)
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

        # Multi-frontend routing based on frontend_source (already extracted at callback start)
        logger.info(f"🎯 Routing user to frontend based on source: '{frontend_source}'")

        if frontend_source == "mobile":
            # Mobile Apps (Android/iOS) → Deep Link
            logger.info(f"📱 Redirecting to Mobile Deep Link")
            return redirect(f"hazebot://oauth?token={token}")
        elif frontend_source == "analytics":
            # Analytics Dashboard → Relative path on api.haze.pro
            logger.info(f"📊 Redirecting to Analytics Dashboard")
            return redirect(f"https://api.haze.pro/analytics/analytics_dashboard.html?token={token}")
        else:
            # Flutter Web App (default) → admin.haze.pro
            frontend_url = os.getenv("DISCORD_OAUTH_FRONTEND_URL", "https://admin.haze.pro")
            logger.info(f"🌐 Redirecting to Flutter Web App: {frontend_url}")
            return redirect(f"{frontend_url}?token={token}")

    @auth_routes.route("/api/auth/me", methods=["GET"])
    @token_required_wrapper
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

    @auth_routes.route("/api/auth/refresh", methods=["POST"])
    @token_required_wrapper
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

    @auth_routes.route("/api/auth/logout", methods=["POST"])
    @token_required_wrapper
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

    @auth_routes.route("/api/ping", methods=["GET"])
    @token_required_wrapper
    def ping():
        """Simple ping endpoint to test session tracking (no permission required)"""
        from datetime import datetime

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

    @auth_routes.route("/api/auth/monitoring-token", methods=["POST"])
    def generate_monitoring_token():
        """
        Generate a long-lived JWT token for monitoring services (Uptime Kuma)
        
        Security: Requires admin credentials via Basic Auth or API_MONITORING_SECRET
        
        Request Body (JSON):
            secret (str): Monitoring secret from API_MONITORING_SECRET env var
        
        Returns:
            token (str): Long-lived JWT token (90 days) with monitoring permissions
            expires (str): Expiration timestamp
        """
        # Check for monitoring secret
        monitoring_secret = os.getenv("API_MONITORING_SECRET")
        
        if not monitoring_secret:
            logger.error("❌ API_MONITORING_SECRET not configured")
            return jsonify({"error": "Monitoring token generation not configured"}), 500
        
        # Verify secret from request
        data = request.get_json() or {}
        provided_secret = data.get("secret")
        
        if not provided_secret or provided_secret != monitoring_secret:
            logger.warning(f"❌ Invalid monitoring secret attempt from {request.remote_addr}")
            return jsonify({"error": "Invalid monitoring secret"}), 401
        
        # Generate long-lived token for monitoring
        from datetime import datetime
        expiry_date = Config.get_utc_now().replace(tzinfo=None) + timedelta(days=90)  # 90 days
        
        monitoring_token = jwt.encode(
            {
                "user": "uptime_kuma_monitor",
                "discord_id": "monitoring_service",
                "exp": expiry_date,
                "role": "monitoring",
                "permissions": ["health_check", "ping", "analytics_read", "tickets_read"],
                "auth_type": "monitoring",
                "session_id": "monitoring_" + secrets.token_hex(8),
            },
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        
        logger.info(f"✅ Generated monitoring token (expires: {expiry_date.isoformat()})")
        
        return jsonify({
            "token": monitoring_token,
            "expires": expiry_date.isoformat(),
            "expires_in_days": 90,
            "permissions": ["health_check", "ping", "analytics_read", "tickets_read"],
            "note": "Store this token securely. Use it in Authorization header as 'Bearer <token>'"
        }), 200

    @auth_routes.route("/api/auth/verify-token", methods=["GET"])
    def verify_token():
        """
        JWT verification endpoint for NGINX auth_request
        Returns 200 if token is valid, 401 if invalid/missing
        This endpoint is called by NGINX to verify JWT tokens before proxying to Analytics
        """
        token = request.headers.get("Authorization")

        if not token:
            logger.debug("❌ Analytics auth: No Authorization header")
            return "", 401

        try:
            # Strip "Bearer " prefix if present
            if token.startswith("Bearer "):
                token = token[7:]

            # Validate token is not empty
            if not token or token.strip() == "":
                logger.debug("❌ Analytics auth: Empty token")
                return "", 401

            # Validate JWT structure
            parts = token.split(".")
            if len(parts) != 3 or not all(parts):
                logger.debug("❌ Analytics auth: Malformed token structure")
                return "", 401

            # Decode and verify JWT
            data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])

            # Check token expiry
            from datetime import datetime

            exp_timestamp = data.get("exp")
            if exp_timestamp:
                exp_date = datetime.utcfromtimestamp(exp_timestamp)
                time_until_expiry = exp_date - Config.get_utc_now().replace(tzinfo=None)
                if time_until_expiry.total_seconds() < 0:
                    logger.debug(f"❌ Analytics auth: Token expired | User: {data.get('user')} | Expired: {exp_date}")
                    return "", 401

            # Verify user has admin/mod permissions
            user_role = data.get("role", "lootling")
            permissions = data.get("permissions", [])

            if user_role not in ["admin", "mod"] and "all" not in permissions:
                logger.warning(
                    f"❌ Analytics auth: Insufficient permissions | User: {data.get('user')} | Role: {user_role}"
                )
                return "", 403  # Forbidden

            # Token is valid and user has permissions
            logger.debug(f"✅ Analytics auth: Token valid | User: {data.get('user')} | Role: {user_role}")
            return "", 200

        except jwt.ExpiredSignatureError:
            logger.debug("❌ Analytics auth: Token expired")
            return "", 401
        except (jwt.DecodeError, jwt.InvalidTokenError) as e:
            logger.debug(f"❌ Analytics auth: Invalid token - {str(e)}")
            return "", 401
        except Exception as e:
            logger.error(f"❌ Analytics auth: Unexpected error - {str(e)}")
            return "", 401

    return auth_routes
