"""
Rocket League related API routes (admin and user endpoints).
"""

import asyncio
import traceback
from datetime import datetime, timezone
from typing import Any, Dict

from flask import Blueprint, current_app, jsonify, request

from Utils.Logger import Logger as logger
from api.utils.auth import require_permission, token_required

rl_bp = Blueprint("rocket_league", __name__)


def _get_bot():
    return current_app.config.get("bot_instance")


@rl_bp.route("/api/rocket-league/accounts", methods=["GET"])
@token_required
@require_permission("all")
def get_rl_accounts():
    """Get all linked Rocket League accounts"""
    try:
        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        rl_cog = bot.get_cog("RocketLeague")
        if not rl_cog:
            return jsonify({"error": "RocketLeague cog not loaded"}), 503

        from Cogs.RocketLeague import load_rl_accounts

        accounts = load_rl_accounts()

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
@token_required
@require_permission("all")
def delete_rl_account(user_id):
    """Delete/unlink a Rocket League account (admin function)"""
    try:
        from Cogs.RocketLeague import load_rl_accounts, save_rl_accounts

        accounts = load_rl_accounts()

        if user_id not in accounts:
            return jsonify({"error": "Account not found"}), 404

        rl_username = accounts[user_id].get("username", "Unknown")

        del accounts[user_id]
        save_rl_accounts(accounts)

        return jsonify(
            {"success": True, "message": f"Successfully unlinked account for user {user_id} (RL: {rl_username})"}
        )
    except Exception as e:
        return jsonify({"error": f"Failed to delete RL account: {str(e)}", "details": traceback.format_exc()}), 500


@rl_bp.route("/api/rocket-league/check-ranks", methods=["POST"])
@token_required
@require_permission("all")
def trigger_rank_check():
    """Manually trigger rank check for all linked accounts"""
    try:
        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        rl_cog = bot.get_cog("RocketLeague")
        if not rl_cog:
            return jsonify({"error": "RocketLeague cog not loaded"}), 503

        loop = bot.loop
        future = asyncio.run_coroutine_threadsafe(rl_cog._check_and_update_ranks(force=True), loop)
        future.result(timeout=120)

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
@token_required
@require_permission("all")
def get_rl_stats(platform, username):
    """Get Rocket League stats for a specific player"""
    try:
        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        rl_cog = bot.get_cog("RocketLeague")
        if not rl_cog:
            return jsonify({"error": "RocketLeague cog not loaded"}), 503

        if platform.lower() not in ["steam", "epic", "psn", "xbl", "switch"]:
            return jsonify({"error": "Invalid platform. Use: steam, epic, psn, xbl, or switch"}), 400

        logger.info(f"🔎 Fetching RL stats for {username} on {platform.upper()} (via API by {request.username})")

        loop = bot.loop
        future = asyncio.run_coroutine_threadsafe(rl_cog.get_player_stats(platform.lower(), username), loop)
        stats = future.result(timeout=90)

        if not stats:
            logger.warning(f"❌ Player {username} not found on {platform.upper()}")
            return jsonify({"error": "Player not found or error fetching stats"}), 404

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
        return jsonify({"error": f"Failed to get stats: {str(e)}", "details": traceback.format_exc()}), 500


@rl_bp.route("/api/user/rocket-league/link", methods=["POST"])
@token_required
def link_user_rl_account():
    """Link Rocket League account for the current user"""
    try:
        from Cogs.RocketLeague import load_rl_accounts, save_rl_accounts

        discord_id = request.discord_id
        if discord_id in ("legacy_user", "unknown"):
            return jsonify({"error": "Discord ID not available"}), 400

        data: Dict[str, Any] = request.get_json() or {}
        platform = data.get("platform", "").lower()
        username = data.get("username", "").strip()

        if not platform or not username:
            return jsonify({"error": "Platform and username are required"}), 400

        if platform not in ["steam", "epic", "psn", "xbl", "switch"]:
            return jsonify({"error": "Invalid platform. Use: steam, epic, psn, xbl, or switch"}), 400

        logger.info(f"🔎 User {request.username} linking RL account: {username} on {platform.upper()}")

        accounts = load_rl_accounts()
        if str(discord_id) in accounts:
            return jsonify({"error": "You already have a Rocket League account linked. Unlink it first."}), 400

        bot = _get_bot()
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

        accounts[str(discord_id)] = {
            "platform": platform,
            "username": username,
            "ranks": stats.get("tier_names", {}),
            "rank_display": stats.get("rank_display", {}),
            "icon_urls": stats.get("icon_urls", {}),
            "last_fetched": datetime.now(timezone.utc).isoformat(),
        }
        save_rl_accounts(accounts)

        ranks_str = ", ".join([f"{k}: {v}" for k, v in stats.get("tier_names", {}).items()])
        logger.info(
            f"✅ Linked RL account for {request.username}: {username} (shows as {stats['username']}) "
            f"({platform.upper()}) - [{ranks_str}]"
        )

        return jsonify(
            {
                "success": True,
                "message": f"Successfully linked Rocket League account: {stats['username']}",
                "account": {"platform": platform, "username": username, "ranks": stats.get("tier_names", {})},
            }
        )
    except Exception as e:
        return jsonify({"error": f"Failed to link account: {str(e)}", "details": traceback.format_exc()}), 500


@rl_bp.route("/api/user/rocket-league/unlink", methods=["DELETE"])
@token_required
def unlink_user_rl_account():
    """Unlink Rocket League account for the current user"""
    try:
        from Cogs.RocketLeague import load_rl_accounts, save_rl_accounts

        discord_id = request.discord_id
        if discord_id in ("legacy_user", "unknown"):
            return jsonify({"error": "Discord ID not available"}), 400

        accounts = load_rl_accounts()

        if str(discord_id) not in accounts:
            return jsonify({"error": "No Rocket League account linked"}), 404

        rl_username = accounts[str(discord_id)].get("username", "Unknown")
        rl_platform = accounts[str(discord_id)].get("platform", "Unknown")

        del accounts[str(discord_id)]
        save_rl_accounts(accounts)

        logger.info(f"✅ User {request.username} unlinked RL account: {rl_username} ({rl_platform.upper()})")

        return jsonify({"success": True, "message": f"Successfully unlinked Rocket League account: {rl_username}"})
    except Exception as e:
        return jsonify({"error": f"Failed to unlink account: {str(e)}", "details": traceback.format_exc()}), 500


@rl_bp.route("/api/user/rocket-league/account", methods=["GET"])
@token_required
def get_user_rl_account():
    """Get current user's linked Rocket League account"""
    try:
        from Cogs.RocketLeague import load_rl_accounts

        discord_id = request.discord_id
        if discord_id in ("legacy_user", "unknown"):
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
@token_required
def post_user_rl_stats():
    """Post current user's RL stats to a Discord channel"""
    try:
        discord_id = request.discord_id
        if discord_id in ("legacy_user", "unknown"):
            return jsonify({"error": "Discord ID not available"}), 400

        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        rl_cog = bot.get_cog("RocketLeague")
        if not rl_cog:
            return jsonify({"error": "Rocket League system not available"}), 503

        logger.info(f"🔎 User {discord_id} posting RL stats to configured RL channel...")

        loop = bot.loop
        future = asyncio.run_coroutine_threadsafe(rl_cog.post_stats_to_channel(int(discord_id)), loop)
        result = future.result(timeout=30)

        if result.get("success"):
            logger.info(f"✅ RL stats posted successfully: {result.get('message')}")
            return jsonify(result), 200

        logger.warning(f"❌ Failed to post RL stats: {result.get('message')}")
        return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error posting RL stats: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to post RL stats: {str(e)}", "details": traceback.format_exc()}), 500
