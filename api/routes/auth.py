"""
Authentication and Discord OAuth routes (Blueprint).
"""

import os
import secrets
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode

import jwt
import requests
from flask import Blueprint, current_app, jsonify, redirect, request

# Ensure we can import the root-level Config module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import Config  # noqa: E402
from Utils.Logger import Logger as logger  # noqa: E402
from api.utils.audit import log_action
from api.utils.auth import active_sessions, token_required

auth_bp = Blueprint("auth", __name__)

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
    role_ids = [str(rid) for rid in role_ids]

    bot = current_app.config.get("bot_instance")
    if not bot:
        return "lootling"

    admin_role_id = str(Config.ADMIN_ROLE_ID)
    mod_role_id = str(Config.MODERATOR_ROLE_ID)

    logger.info(
        f"🔎 Discord Auth - Checking roles: user_roles={role_ids}, admin_id={admin_role_id}, mod_id={mod_role_id}"
    )

    if admin_role_id in role_ids:
        logger.info("✅ User identified as ADMIN")
        return "admin"
    if mod_role_id in role_ids:
        logger.info("✅ User identified as MOD (with admin permissions)")
        return "mod"
    logger.info("ℹ️ User identified as LOOTLING")
    return "lootling"


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    """Simple authentication endpoint"""
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    valid_users = {os.getenv("API_ADMIN_USER", "admin"): os.getenv("API_ADMIN_PASS", "changeme")}

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
                "exp": Config.get_utc_now().replace(tzinfo=None) + timedelta(days=7),
                "role": "admin",
                "permissions": ["all"],
                "auth_type": "legacy",
                "session_id": session_id,
            },
            current_app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        return jsonify({"token": token, "user": username, "role": "admin", "permissions": ["all"]})

    return jsonify({"error": "Invalid credentials"}), 401


@auth_bp.route("/api/discord/auth", methods=["GET"])
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


@auth_bp.route("/api/discord/callback", methods=["GET"])
def discord_callback():
    """Handle Discord OAuth2 callback"""
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "No authorization code provided"}), 400

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
    user_headers = {"Authorization": f"Bearer {access_token}"}
    user_response = requests.get(f"{DISCORD_API_ENDPOINT}/users/@me", headers=user_headers)
    if user_response.status_code != 200:
        return jsonify({"error": "Failed to get user info"}), 400

    user_data = user_response.json()

    prod_mode = os.getenv("PROD_MODE", "false").lower() == "true"
    guild_id = os.getenv("DISCORD_GUILD_ID") if prod_mode else os.getenv("DISCORD_TEST_GUILD_ID")

    member_response = requests.get(f"{DISCORD_API_ENDPOINT}/users/@me/guilds/{guild_id}/member", headers=user_headers)

    if member_response.status_code != 200:
        logger.error("❌ Discord member check failed:")
        logger.error(f"   Status: {member_response.status_code}")
        logger.error(f"   Response: {member_response.text[:500]}")
        logger.error(f"   User: {user_data.get('username')}#{user_data.get('discriminator')}")
        logger.error(f"   User ID: {user_data.get('id')}")
        logger.error(f"   Guild ID: {guild_id}")
        logger.error(f"   API URL: {DISCORD_API_ENDPOINT}/users/@me/guilds/{guild_id}/member")

        logger.info("ℹ️ Attempting fallback via bot instance...")
        bot = current_app.config.get("bot_instance")
        if bot:
            guild = bot.get_guild(int(guild_id))
            if guild:
                member = guild.get_member(int(user_data["id"]))
                if member:
                    logger.info("✅ User found in guild via bot, proceeding with authentication")
                    member_data = {
                        "roles": [str(role.id) for role in member.roles],
                        "user": {"id": str(member.id), "username": member.name},
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

    role = get_user_role_from_discord(member_data, guild_id)
    permissions = ROLE_PERMISSIONS.get(role, ["meme_generator"])

    role_name = None
    try:
        bot = current_app.config.get("bot_instance")
        if bot:
            guild = bot.get_guild(int(guild_id))
            if guild:
                member = guild.get_member(int(user_data["id"]))
                if member:
                    for discord_role in member.roles:
                        if discord_role.id == Config.ADMIN_ROLE_ID:
                            role_name = discord_role.name
                            break
                        if discord_role.id == Config.MODERATOR_ROLE_ID:
                            role_name = discord_role.name
                            break
    except Exception:
        pass

    session_id = secrets.token_hex(16)
    token = jwt.encode(
        {
            "user": user_data["username"],
            "discord_id": user_data["id"],
            "exp": Config.get_utc_now().replace(tzinfo=None) + timedelta(days=7),
            "role": role,
            "role_name": role_name,
            "permissions": permissions,
            "auth_type": "discord",
            "session_id": session_id,
        },
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )

    log_action(user_data["username"], "discord_oauth_login", {"role": role, "permissions": permissions})

    state = request.args.get("state", "")
    is_mobile_app = state == "mobile"

    if is_mobile_app:
        return redirect(f"hazebot://oauth?token={token}")

    frontend_url = "https://test-hazebot-admin.hzwd.xyz"
    return redirect(f"{frontend_url}?token={token}")


@auth_bp.route("/api/auth/me", methods=["GET"])
@token_required
def get_current_user():
    """Get current user info from JWT token"""
    token = request.headers.get("Authorization")
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        data = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])

        avatar_url = None
        role_name = data.get("role_name")
        discord_id = data.get("discord_id")
        if discord_id and discord_id not in ["legacy_user", "unknown"]:
            try:
                bot = current_app.config.get("bot_instance")
                if bot:
                    guild = bot.get_guild(Config.GUILD_ID)
                    if guild:
                        member = guild.get_member(int(discord_id))
                        if member:
                            if member.avatar:
                                avatar_url = str(member.avatar.url)
                            if not role_name:
                                for role in member.roles:
                                    if role.id == Config.ADMIN_ROLE_ID:
                                        role_name = role.name
                                        break
                                    if role.id == Config.MODERATOR_ROLE_ID:
                                        role_name = role.name
                                        break
            except Exception:
                pass

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


@auth_bp.route("/api/auth/refresh", methods=["POST"])
@token_required
def refresh_token():
    """Refresh JWT token with new expiry date (keeps same session_id)"""
    try:
        token_payload = {
            "user": request.username,
            "discord_id": request.discord_id,
            "exp": Config.get_utc_now().replace(tzinfo=None) + timedelta(days=7),
            "role": request.user_role,
            "permissions": request.user_permissions,
            "auth_type": "refreshed",
            "session_id": request.session_id,
        }

        if hasattr(request, "role_name") and request.role_name:
            token_payload["role_name"] = request.role_name

        new_token = jwt.encode(token_payload, current_app.config["SECRET_KEY"], algorithm="HS256")

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


@auth_bp.route("/api/auth/logout", methods=["POST"])
@token_required
def logout():
    """Logout user and remove their active session"""
    try:
        session_id = request.session_id
        if session_id in active_sessions:
            del active_sessions[session_id]
            logger.info(f"✅ User logged out: {request.username} (Session: {session_id[:8]}...)")

        return jsonify({"message": "Logged out successfully"}), 200
    except Exception as e:
        logger.error(f"❌ Logout failed: {e}")
        return jsonify({"error": "Logout failed"}), 500
