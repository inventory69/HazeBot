"""
Rocket League Routes Blueprint
Handles all /api/rocket-league/* and /api/user/rocket-league/* endpoints
"""

import asyncio
import traceback
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

# Will be initialized by init_rocket_league_routes()
Config = None
logger = None
token_required = None
require_permission = None

# Create Blueprint
rl_bp = Blueprint("rocket_league", __name__)


def init_rocket_league_routes(app, config, log, auth_module):
    """Initialize Rocket League routes Blueprint with dependencies"""
    global Config, logger, token_required, require_permission

    Config = config
    logger = log
    token_required = auth_module.token_required
    require_permission = auth_module.require_permission

    # Register blueprint WITHOUT decorators first
    # (Blueprint routes are already defined with @rl_bp.route decorators)
    app.register_blueprint(rl_bp)

    # NOW apply decorators to the already-registered view functions
    # We need to modify Flask's view_functions dict directly
    vf = app.view_functions
    vf["rocket_league.get_rl_accounts"] = token_required(require_permission("all")(vf["rocket_league.get_rl_accounts"]))
    vf["rocket_league.delete_rl_account"] = token_required(
        require_permission("all")(vf["rocket_league.delete_rl_account"])
    )
    vf["rocket_league.trigger_rank_check"] = token_required(
        require_permission("all")(vf["rocket_league.trigger_rank_check"])
    )
    vf["rocket_league.get_rl_stats"] = token_required(vf["rocket_league.get_rl_stats"])
    vf["rocket_league.link_user_rl_account"] = token_required(vf["rocket_league.link_user_rl_account"])
    vf["rocket_league.unlink_user_rl_account"] = token_required(vf["rocket_league.unlink_user_rl_account"])
    vf["rocket_league.get_user_rl_account"] = token_required(vf["rocket_league.get_user_rl_account"])
    vf["rocket_league.post_user_rl_stats"] = token_required(vf["rocket_league.post_user_rl_stats"])


# ===== ADMIN RL ENDPOINTS =====


@rl_bp.route("/api/rocket-league/accounts", methods=["GET"])
def get_rl_accounts():
    """Get all linked Rocket League accounts"""
    try:
        from flask import current_app

        from Cogs.RocketLeague import load_rl_accounts

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        rl_cog = bot.get_cog("RocketLeague")
        if not rl_cog:
            return jsonify({"error": "RocketLeague cog not loaded"}), 503

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
        return jsonify({"error": f"Failed to get RL accounts: {str(e)}", "details": traceback.format_exc()}), 500


@rl_bp.route("/api/rocket-league/accounts/<user_id>", methods=["DELETE"])
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
        return jsonify({"error": f"Failed to delete RL account: {str(e)}", "details": traceback.format_exc()}), 500


@rl_bp.route("/api/rocket-league/check-ranks", methods=["POST"])
def trigger_rank_check():
    """Manually trigger rank check for all linked accounts"""
    try:
        from flask import current_app

        bot = current_app.config.get("bot_instance")
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
        return jsonify({"error": f"Failed to check ranks: {str(e)}", "details": traceback.format_exc()}), 500


@rl_bp.route("/api/rocket-league/stats/<platform>/<username>", methods=["GET"])
def get_rl_stats(platform, username):
    """Get Rocket League stats for a specific player"""
    try:
        from flask import current_app

        bot = current_app.config.get("bot_instance")
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

        # XP Reward for viewing RL stats via API
        try:
            from api.level_helpers import award_xp_from_api
            discord_id = request.discord_id if hasattr(request, 'discord_id') else None
            username = request.username if hasattr(request, 'username') else 'Unknown'
            if discord_id and discord_id not in ["legacy_user", "unknown"]:
                award_xp_from_api(
                    bot=bot,
                    user_id=str(discord_id),
                    username=username,
                    xp_type="rl_stats_checked",
                    amount=5
                )
                logger.info(f"⭐ User {username} gained 5 XP for checking RL stats via API")
        except Exception as e:
            logger.error(f"❌ Failed to add XP for RL stats check via API: {e}")

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
        return jsonify({"error": f"Failed to get stats: {str(e)}", "details": traceback.format_exc()}), 500


# ===== USER RL ENDPOINTS =====


@rl_bp.route("/api/user/rocket-league/link", methods=["POST"])
def link_user_rl_account():
    """Link Rocket League account for the current user"""
    try:
        from flask import current_app

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
        bot = current_app.config.get("bot_instance")
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

        # XP Reward for linking RL account via API
        try:
            from api.level_helpers import award_xp_from_api
            award_xp_from_api(
                bot=bot,
                user_id=str(discord_id),
                username=request.username,
                xp_type="rl_account_linked",
                amount=20
            )
            logger.info(f"⭐ User {request.username} gained 20 XP for linking RL account via API")
        except Exception as e:
            logger.error(f"❌ Failed to add XP for RL account linking via API: {e}")

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
        return jsonify({"error": f"Failed to link account: {str(e)}", "details": traceback.format_exc()}), 500


@rl_bp.route("/api/user/rocket-league/unlink", methods=["DELETE"])
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
        return jsonify({"error": f"Failed to unlink account: {str(e)}", "details": traceback.format_exc()}), 500


@rl_bp.route("/api/user/rocket-league/account", methods=["GET"])
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
        return jsonify({"error": f"Failed to fetch RL stats: {str(e)}", "details": traceback.format_exc()}), 500


@rl_bp.route("/api/user/rocket-league/post-stats", methods=["POST"])
def post_user_rl_stats():
    """Post current user's RL stats to a Discord channel"""
    try:
        from flask import current_app

        discord_id = request.discord_id
        if discord_id == "legacy_user" or discord_id == "unknown":
            return jsonify({"error": "Discord ID not available"}), 400

        # Get RocketLeague cog
        bot = current_app.config.get("bot_instance")
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
        logger.error(f"Error posting RL stats: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to post RL stats: {str(e)}", "details": traceback.format_exc()}), 500
