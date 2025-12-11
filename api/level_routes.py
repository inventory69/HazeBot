"""
Level System API Routes
========================
Provides endpoints for XP/Level data access in the Admin Panel

Endpoints:
- GET /api/levels/user/<discord_id> - Get user level data
- GET /api/levels/leaderboard - Get XP leaderboard
- GET /api/levels/history/<discord_id> - Get user's level-up history
"""

import logging
import sqlite3
import traceback
from pathlib import Path

from flask import Blueprint, jsonify, request

import Config

logger = logging.getLogger(__name__)

level_bp = Blueprint("levels", __name__)

# Global references (set by init function)
token_required = None


def init_level_routes(app, config, log, auth_module):
    """Initialize level routes Blueprint with dependencies"""
    global Config, logger, token_required

    Config = config
    logger = log
    token_required = auth_module.token_required

    # Register blueprint WITHOUT decorators first
    app.register_blueprint(level_bp)

    # NOW apply decorators to already-registered view functions
    vf = app.view_functions
    vf["levels.get_user_level"] = token_required(vf["levels.get_user_level"])
    vf["levels.get_leaderboard"] = token_required(vf["levels.get_leaderboard"])
    vf["levels.get_level_history"] = token_required(vf["levels.get_level_history"])

    logger.info("✅ Level routes registered")


@level_bp.route("/api/levels/user/<discord_id>", methods=["GET"])
def get_user_level(discord_id):
    """Get user's level data"""
    try:
        from flask import current_app

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        level_cog = bot.get_cog("LevelSystem")
        if not level_cog:
            return jsonify({"error": "LevelSystem not loaded"}), 503

        # Get user data from database
        db_path = Path(Config.DATA_DIR) / "user_levels.db"
        if not db_path.exists():
            return jsonify({"error": "Level database not found"}), 404

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM user_xp WHERE user_id = ?", (discord_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return jsonify({"error": "User not found in level system"}), 404

        user_data = dict(row)
        conn.close()

        # Calculate next level XP
        from Config import calculate_xp_for_next_level, get_level_tier

        next_level_xp = calculate_xp_for_next_level(user_data["current_level"])
        tier_info = get_level_tier(user_data["current_level"])

        # Get Discord username
        guild = bot.get_guild(Config.GUILD_ID)
        discord_username = user_data["username"]
        if guild:
            member = guild.get_member(int(discord_id))
            if member:
                discord_username = member.name

        return jsonify(
            {
                "success": True,
                "user": {
                    "user_id": user_data["user_id"],
                    "username": discord_username,
                    "total_xp": user_data["total_xp"],
                    "current_level": user_data["current_level"],
                    "next_level_xp": next_level_xp,
                    "tier": {
                        "name": tier_info["name"],
                        "color": tier_info["color"],
                        "description": tier_info["description"],
                        "min_level": tier_info["min_level"],
                    },
                    "activity": {
                        "memes_generated": user_data["memes_generated"],
                        "memes_fetched": user_data["memes_fetched"],
                        "messages_sent": user_data["messages_sent"],
                        "images_sent": user_data["images_sent"],
                        "tickets_created": user_data["tickets_created"],
                        "tickets_resolved": user_data["tickets_resolved"],
                        "tickets_claimed": user_data["tickets_claimed"],
                        "game_request": user_data["game_request"],
                    },
                    "last_xp_gain": user_data["last_xp_gain"],
                    "created_at": user_data["created_at"],
                    "updated_at": user_data["updated_at"],
                },
            }
        ), 200

    except Exception as e:
        logger.error(f"Error getting user level: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to get user level: {str(e)}"}), 500


@level_bp.route("/api/levels/leaderboard", methods=["GET"])
def get_leaderboard():
    """Get XP leaderboard"""
    try:
        from flask import current_app

        # Get limit from query params (default: 10, max: 100)
        limit = request.args.get("limit", 10, type=int)
        limit = min(max(1, limit), 100)  # Clamp between 1 and 100

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Get leaderboard from database
        db_path = Path(Config.DATA_DIR) / "user_levels.db"
        if not db_path.exists():
            return jsonify({"error": "Level database not found"}), 404

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT user_id, username, total_xp, current_level, updated_at
            FROM user_xp
            ORDER BY total_xp DESC, current_level DESC
            LIMIT ?
        """,
            (limit,),
        )

        rows = cursor.fetchall()
        conn.close()

        # Get Discord usernames and build leaderboard
        from Config import get_level_tier

        guild = bot.get_guild(Config.GUILD_ID)
        leaderboard = []

        for rank, row in enumerate(rows, start=1):
            user_dict = dict(row)

            # Try to get current Discord username
            discord_username = user_dict["username"]
            if guild:
                member = guild.get_member(int(user_dict["user_id"]))
                if member:
                    discord_username = member.name

            tier_info = get_level_tier(user_dict["current_level"])

            leaderboard.append(
                {
                    "rank": rank,
                    "user_id": user_dict["user_id"],
                    "username": discord_username,
                    "total_xp": user_dict["total_xp"],
                    "current_level": user_dict["current_level"],
                    "tier_name": tier_info["name"],
                    "tier_color": tier_info["color"],
                    "updated_at": user_dict["updated_at"],
                }
            )

        return jsonify({"success": True, "leaderboard": leaderboard, "count": len(leaderboard)}), 200

    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to get leaderboard: {str(e)}"}), 500


@level_bp.route("/api/levels/history/<discord_id>", methods=["GET"])
def get_level_history(discord_id):
    """Get user's level-up history"""
    try:
        from flask import current_app

        # Get limit from query params (default: 20, max: 100)
        limit = request.args.get("limit", 20, type=int)
        limit = min(max(1, limit), 100)  # Clamp between 1 and 100

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Get history from database
        db_path = Path(Config.DATA_DIR) / "user_levels.db"
        if not db_path.exists():
            return jsonify({"error": "Level database not found"}), 404

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute("SELECT username FROM user_xp WHERE user_id = ?", (discord_id,))
        user_row = cursor.fetchone()

        if not user_row:
            conn.close()
            return jsonify({"error": "User not found in level system"}), 404

        # Get level history
        cursor.execute(
            """
            SELECT id, old_level, new_level, total_xp, timestamp
            FROM level_history
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (discord_id, limit),
        )

        rows = cursor.fetchall()
        conn.close()

        # Build history list
        from Config import get_level_tier

        history = []
        for row in rows:
            history_dict = dict(row)
            old_tier = get_level_tier(history_dict["old_level"])
            new_tier = get_level_tier(history_dict["new_level"])

            history.append(
                {
                    "id": history_dict["id"],
                    "old_level": history_dict["old_level"],
                    "new_level": history_dict["new_level"],
                    "old_tier": old_tier["name"],
                    "new_tier": new_tier["name"],
                    "total_xp": history_dict["total_xp"],
                    "timestamp": history_dict["timestamp"],
                    "is_milestone": history_dict["new_level"] % 5 == 0,
                }
            )

        # Get current Discord username
        guild = bot.get_guild(Config.GUILD_ID)
        discord_username = user_row["username"]
        if guild:
            member = guild.get_member(int(discord_id))
            if member:
                discord_username = member.name

        return (
            jsonify(
                {
                    "success": True,
                    "user_id": discord_id,
                    "username": discord_username,
                    "history": history,
                    "count": len(history),
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Error getting level history: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to get level history: {str(e)}"}), 500
