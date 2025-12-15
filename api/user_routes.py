"""
User Routes Blueprint
Handles all /api/user/* and /api/gaming/* endpoints for user-specific functions
"""

import asyncio
import sqlite3
import traceback
from pathlib import Path

from flask import Blueprint, jsonify, request

# Constants
APP_USAGE_EXPIRY_DAYS = 30  # Remove badge after 30 days of inactivity

# Will be initialized by init_user_routes()
Config = None
logger = None
cache = None
get_active_app_users = None
update_app_usage = None
token_required = None

# Create Blueprint
user_bp = Blueprint("user", __name__)


def init_user_routes(app, config, log, cache_module, helpers_module, auth_module):
    """
    Initialize user routes Blueprint with dependencies

    Args:
        app: Flask app instance
        config: Config module
        log: Logger instance
        cache_module: Cache module
        helpers_module: Module containing get_active_app_users, update_app_usage
        auth_module: Module containing token_required decorator
    """
    global Config, logger, cache, get_active_app_users, update_app_usage, token_required

    Config = config
    logger = log
    cache = cache_module
    get_active_app_users = helpers_module.get_active_app_users
    update_app_usage = helpers_module.update_app_usage
    token_required = auth_module.token_required

    # Register blueprint WITHOUT decorators first
    app.register_blueprint(user_bp)

    # NOW apply decorators to already-registered view functions
    vf = app.view_functions
    vf["user.get_user_profile"] = token_required(vf["user.get_user_profile"])
    vf["user.update_user_preferences"] = token_required(vf["user.update_user_preferences"])
    vf["user.get_gaming_members"] = token_required(vf["user.get_gaming_members"])
    vf["user.post_game_request"] = token_required(vf["user.post_game_request"])


# ===== USER PROFILE =====


@user_bp.route("/api/user/profile", methods=["GET"])
def get_user_profile():
    """Get current user's profile information (no special permissions required)"""
    try:
        from flask import current_app

        bot = current_app.config.get("bot_instance")
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
                mod_data = asyncio.run(mod_data_sync)
            else:
                mod_data = mod_data_sync

            if str(discord_id) in mod_data.get("warnings", {}):
                warnings_count = len(mod_data["warnings"][str(discord_id)])
        except Exception:
            # Warnings are optional
            pass

        # Get resolved tickets (for admins/mods)
        resolved_tickets = 0
        if any(role.id in [Config.ADMIN_ROLE_ID, Config.MODERATOR_ROLE_ID] for role in member.roles):
            try:
                from Cogs.TicketSystem import load_tickets

                tickets_sync = load_tickets()
                if hasattr(tickets_sync, "__await__"):
                    tickets = asyncio.run(tickets_sync)
                else:
                    tickets = tickets_sync

                for ticket in tickets:
                    if ticket["status"] == "Closed" and (
                        ticket.get("claimed_by") == int(discord_id)
                        or ticket.get("assigned_to") == int(discord_id)
                        or ticket.get("closed_by") == int(discord_id)
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

        # Get XP/Level data
        xp_data = None
        try:
            db_path = Path(Config.DATA_DIR) / "user_levels.db"
            if db_path.exists():
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT total_xp, current_level, last_xp_gain FROM user_xp WHERE user_id = ?",
                    (str(discord_id),)
                )
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    total_xp = row["total_xp"]
                    level = row["current_level"]
                    last_xp_gain = row["last_xp_gain"]
                    
                    # Calculate XP needed for next level
                    xp_for_next_level = Config.calculate_xp_for_next_level(level)
                    
                    # Calculate XP required to reach current level (total XP for all previous levels)
                    xp_for_current_level = Config.calculate_total_xp_for_level(level)
                    
                    # Calculate XP within current level (progress towards next level)
                    xp_in_current_level = total_xp - xp_for_current_level
                    
                    # Determine tier using Config helper
                    tier_info = Config.get_level_tier(level)
                    
                    xp_data = {
                        "total_xp": total_xp,
                        "level": level,
                        "tier": tier_info["name"],
                        "tier_color": tier_info["color"],
                        "xp_for_next_level": xp_for_next_level,
                        "xp_in_current_level": xp_in_current_level,
                        "last_xp_gain": last_xp_gain,
                    }
        except Exception as e:
            logger.error(f"Error fetching XP data: {e}")
            pass

        # Build profile response
        profile_data = {
            "discord_id": str(discord_id),
            "username": member.name,
            "display_name": member.display_name,
            "discriminator": member.discriminator,
            "avatar_url": str(member.display_avatar.url) if member.display_avatar else None,
            "role": user_role,
            "role_name": user_role_name,
            "opt_in_roles": opt_in_roles,
            "rl_rank": rl_rank,
            "notifications": {
                "changelog_opt_in": has_changelog,
                "meme_opt_in": has_meme,
            },
            "custom_stats": {
                "warnings": warnings_count,
                "resolved_tickets": resolved_tickets,
            },
            "activity": activity,
            "joined_at": member.joined_at.isoformat() if member.joined_at else None,
            "created_at": member.created_at.isoformat() if member.created_at else None,
        }
        
        # Add XP data if available
        if xp_data:
            profile_data["xp"] = xp_data
        
        return jsonify(
            {
                "success": True,
                "profile": profile_data,
            }
        )

    except Exception as e:
        logger.error(f"Error fetching user profile: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch profile: {str(e)}"}), 500


# ===== USER PREFERENCES =====


@user_bp.route("/api/user/preferences", methods=["PUT"])
def update_user_preferences():
    """Update current user's notification preferences"""
    try:
        from flask import current_app

        discord_id = request.discord_id
        if discord_id == "legacy_user" or discord_id == "unknown":
            return jsonify({"error": "Discord ID not available"}), 400

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Get bot instance
        bot = current_app.config.get("bot_instance")
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
        return jsonify({"error": f"Failed to update preferences: {str(e)}", "details": traceback.format_exc()}), 500


# ===== GAMING HUB =====


@user_bp.route("/api/gaming/members", methods=["GET"])
def get_gaming_members():
    """Get all server members with their presence/activity data + app usage status (with cache)"""
    try:
        # Check cache first (30 second TTL - users change status frequently)
        cache_key = "gaming:members"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return jsonify(cached_result)

        import discord
        from flask import current_app

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        guild = bot.get_guild(Config.GUILD_ID)
        if not guild:
            return jsonify({"error": "Guild not found"}), 500

        # Get list of users who have used the app within the last 30 days
        app_usage_file = Path(Config.DATA_DIR) / "app_usage.json"
        app_users = get_active_app_users(app_usage_file, APP_USAGE_EXPIRY_DAYS, Config)

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
        logger.error(f"Error fetching gaming members: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch members: {str(e)}"}), 500


@user_bp.route("/api/gaming/request", methods=["POST"])
def post_game_request():
    """Post a game request to the gaming channel"""
    try:
        import discord
        from flask import current_app

        discord_id = request.discord_id
        if discord_id == "legacy_user" or discord_id == "unknown":
            return jsonify({"error": "Discord ID not available"}), 400

        data = request.get_json()
        if not data or "target_user_id" not in data or "game_name" not in data:
            return jsonify({"error": "Missing required fields: target_user_id, game_name"}), 400

        target_user_id = data["target_user_id"]
        game_name = data["game_name"]
        message_text = data.get("message", "")

        bot = current_app.config.get("bot_instance")
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

        # Award XP for game request (8 XP)
        from api.level_helpers import award_xp_from_api
        award_xp_from_api(bot, discord_id, requester.name, "game_request")

        return jsonify(
            {
                "success": True,
                "message": "Game request posted successfully",
                "message_id": str(message.id),
                "channel_id": str(channel.id),
            }
        )

    except Exception as e:
        logger.error(f"Error posting game request: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to post game request: {str(e)}"}), 500
