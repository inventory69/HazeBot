"""
Gaming-related API routes.
"""

import asyncio
import traceback

import discord
from flask import Blueprint, current_app, jsonify, request

import Config
from api.cache import cache
from api.utils.auth import get_active_app_users, token_required
from Utils.Logger import Logger as logger

gaming_bp = Blueprint("gaming", __name__)


def _get_bot():
    return current_app.config.get("bot_instance")


@gaming_bp.route("/api/gaming/members", methods=["GET"])
@token_required
def get_gaming_members():
    """Get all server members with their presence/activity data + app usage status (with cache)."""
    try:
        cache_key = "gaming:members"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return jsonify(cached_result)

        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        guild = bot.get_guild(Config.GUILD_ID)
        if not guild:
            return jsonify({"error": "Guild not found"}), 500

        app_users = get_active_app_users()

        members_data = []
        for member in guild.members:
            if member.bot:
                continue

            status = str(member.status) if member.status else "offline"
            activity_data = None

            if member.activities:
                for activity in member.activities:
                    activity_type = activity.type
                    if activity_type == discord.ActivityType.custom:
                        continue

                    activity_type_str = str(activity_type).replace("ActivityType.", "").lower()
                    activity_data = {
                        "type": activity_type_str,
                        "name": activity.name,
                    }

                    if hasattr(activity, "details") and activity.details:
                        activity_data["details"] = activity.details
                    if hasattr(activity, "state") and activity.state:
                        activity_data["state"] = activity.state
                    if hasattr(activity, "large_image_url") and activity.large_image_url:
                        activity_data["image_url"] = activity.large_image_url
                    elif hasattr(activity, "small_image_url") and activity.small_image_url:
                        activity_data["image_url"] = activity.small_image_url
                    break

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

        members_data.sort(key=lambda m: (m["status"] == "offline", m["display_name"].lower()))

        result = {"members": members_data, "total": len(members_data), "app_users_count": len(app_users)}
        cache.set(cache_key, result, ttl=30)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error fetching gaming members: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch members: {str(e)}"}), 500


@gaming_bp.route("/api/gaming/request", methods=["POST"])
@token_required
def post_game_request():
    """Post a game request to the gaming channel."""
    try:
        discord_id = request.discord_id
        if discord_id in ("legacy_user", "unknown"):
            return jsonify({"error": "Discord ID not available"}), 400

        data = request.get_json()
        if not data or "target_user_id" not in data or "game_name" not in data:
            return jsonify({"error": "Missing required fields: target_user_id, game_name"}), 400

        target_user_id = data["target_user_id"]
        game_name = data["game_name"]
        message_text = data.get("message", "")

        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        guild = bot.get_guild(Config.GUILD_ID)
        if not guild:
            return jsonify({"error": "Guild not found"}), 500

        gaming_channel = guild.get_channel(Config.GAMING_CHANNEL_ID)
        if not gaming_channel:
            return jsonify({"error": "Gaming channel not found"}), 500

        target_member = guild.get_member(int(target_user_id))
        if not target_member:
            return jsonify({"error": "Target user not found"}), 404

        current_member = guild.get_member(int(discord_id))
        if not current_member:
            return jsonify({"error": "Current user not found in guild"}), 404

        target_game = None
        if target_member.activities:
            for activity in target_member.activities:
                if activity.type == discord.ActivityType.custom:
                    continue
                target_game = activity.name
                break

        description = (
            f"🎮 {current_member.mention} wants to play **{game_name}** with {target_member.mention}!"
        )
        if target_game:
            description += f"\n🕹️ {target_member.display_name} is currently playing **{target_game}**"
        if message_text:
            description += f"\n💬 Message: {message_text}"

        async def send_request():
            from Cogs.GamingHub import GameRequestView

            embed = discord.Embed(
                title="🎮 Game Request",
                description=description,
                color=discord.Color.green(),
                timestamp=Config.get_utc_now(),
            )
            embed.add_field(name="Requested by", value=current_member.mention, inline=True)
            embed.add_field(name="Target", value=target_member.mention, inline=True)
            embed.add_field(name="Game", value=game_name, inline=False)
            if target_game:
                embed.add_field(name="Target currently playing", value=target_game, inline=False)
            if message_text:
                embed.add_field(name="Message", value=message_text, inline=False)

            embed.set_thumbnail(url=current_member.display_avatar.url)
            embed.set_footer(text="Respond with the buttons below")

            view = GameRequestView(
                int(discord_id), int(target_user_id), game_name, Config.get_local_now().timestamp()
            )
            msg = await gaming_channel.send(content=f"🎮 {target_member.mention}", embed=embed, view=view)

            gaming_hub_cog = bot.get_cog("GamingHub")
            if gaming_hub_cog:
                gaming_hub_cog.save_game_request(
                    gaming_channel.id,
                    msg.id,
                    int(discord_id),
                    int(target_user_id),
                    game_name,
                )
            else:
                logger.warning("GamingHub cog not loaded, game request view will not persist")

            return msg

        loop = bot.loop
        future = asyncio.run_coroutine_threadsafe(send_request(), loop)
        message = future.result(timeout=10)

        logger.info(f"🎮 Game request posted: {current_member.name} -> {target_member.name} for {game_name}")

        return jsonify(
            {
                "success": True,
                "message": "Game request posted successfully",
                "message_id": str(message.id),
                "channel_id": str(gaming_channel.id),
            }
        )

    except Exception as e:
        return jsonify({"error": f"Failed to post game request: {str(e)}", "details": traceback.format_exc()}), 500
