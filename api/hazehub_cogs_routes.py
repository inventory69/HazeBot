"""
HazeHub, Cogs, and Content Routes Blueprint
Handles /api/hazehub/*, /api/cogs/*, /api/memes/*/upvote endpoints
"""

import asyncio
import traceback
from pathlib import Path

from flask import Blueprint, jsonify, request

# Will be initialized by init_hazehub_cogs_routes()
Config = None
logger = None
cache = None
token_required = None
require_permission = None
log_config_action = None
load_upvotes = None
save_upvotes = None
NEGATIVE_EMOJIS = []

# Create Blueprint
hazehub_cogs_bp = Blueprint("hazehub_cogs", __name__)


def init_hazehub_cogs_routes(app, config, log, cache_module, auth_module, helpers_module):
    """Initialize HazeHub and Cogs routes Blueprint with dependencies"""
    global Config, logger, cache, token_required, require_permission, log_config_action
    global load_upvotes, save_upvotes, NEGATIVE_EMOJIS

    Config = config
    logger = log
    cache = cache_module
    token_required = auth_module.token_required
    require_permission = auth_module.require_permission
    log_config_action = auth_module.log_config_action
    load_upvotes = helpers_module.load_upvotes
    save_upvotes = helpers_module.save_upvotes

    # Import negative emojis from main app if available
    try:
        import app as app_module

        NEGATIVE_EMOJIS = getattr(app_module, "NEGATIVE_EMOJIS", ["👎", "😡", "🤬", "💩"])
    except Exception:
        NEGATIVE_EMOJIS = ["👎", "😡", "🤬", "💩"]

    # Register blueprint WITHOUT decorators first
    app.register_blueprint(hazehub_cogs_bp)

    # NOW apply decorators to already-registered view functions
    vf = app.view_functions
    vf["hazehub_cogs.get_latest_memes"] = token_required(vf["hazehub_cogs.get_latest_memes"])
    vf["hazehub_cogs.get_latest_rankups"] = token_required(vf["hazehub_cogs.get_latest_rankups"])
    vf["hazehub_cogs.toggle_upvote_meme"] = token_required(vf["hazehub_cogs.toggle_upvote_meme"])
    vf["hazehub_cogs.get_meme_reactions"] = token_required(vf["hazehub_cogs.get_meme_reactions"])
    # Cog management routes moved to cog_routes.py - decorators applied there


# =====================================
# HazeHub Endpoints
# =====================================


@hazehub_cogs_bp.route("/api/hazehub/latest-memes", methods=["GET"])
def get_latest_memes():
    """Get latest memes posted in the meme channel (with cache)"""
    try:
        from flask import current_app

        limit = request.args.get("limit", 10, type=int)
        limit = min(limit, 50)  # Max 50 memes

        # Check cache first (60 second TTL)
        cache_key = f"hazehub:latest_memes:{limit}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return jsonify(cached_result)

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not available"}), 503

        # Get meme channel
        meme_channel_id = Config.MEME_CHANNEL_ID
        if not meme_channel_id:
            return jsonify({"error": "Meme channel not configured"}), 400

        # Load custom upvotes
        upvotes_file = Path(Config.DATA_DIR) / "hazehub_upvotes.json"
        custom_upvotes = load_upvotes(upvotes_file)

        async def fetch_memes():
            channel = bot.get_channel(meme_channel_id)
            if not channel:
                return None

            memes = []
            # Fetch more messages to account for non-meme messages
            async for message in channel.history(limit=min(limit * 10, 100)):
                # Only include messages with embeds (memes posted by bot)
                if message.embeds:
                    embed = message.embeds[0]

                    message_id_str = str(message.id)
                    meme_data = {
                        "message_id": message_id_str,
                        "timestamp": message.created_at.isoformat(),
                        "title": embed.title or "Untitled Meme",
                        "image_url": embed.image.url if embed.image else None,
                        "url": embed.url or None,  # Permalink to reddit/lemmy
                        "color": embed.color.value if embed.color else None,
                    }

                    # Get custom upvotes from our system
                    custom_count = len(custom_upvotes.get(message_id_str, []))

                    # Get Discord reactions count (all positive reactions)
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

                    # Extract requester from message content
                    requester = None
                    if message.content:
                        import re

                        # Pattern 1: "Meme sent from Admin Panel by @username"
                        match = re.search(r"Meme sent from Admin Panel by <@!?(\d+)>", message.content)
                        if not match:
                            # Pattern 2: "🎭 Meme requested by @username"
                            match = re.search(r"Meme requested by <@!?(\d+)>", message.content)

                        if match:
                            user_id = match.group(1)
                            try:
                                guild = bot.get_guild(Config.get_guild_id())
                                if guild:
                                    member = guild.get_member(int(user_id))
                                    if member:
                                        requester = member.display_name or member.name
                                    else:
                                        requester = f"User {user_id}"
                                else:
                                    requester = f"User {user_id}"
                            except (ValueError, AttributeError):
                                requester = f"User {user_id}"

                    # Parse fields for upvotes, source, author, creator
                    if embed.fields:
                        for field in embed.fields:
                            field_name = field.name.lower()

                            # Upvotes field: "👍 Upvotes"
                            if "upvote" in field_name or "👍" in field_name:
                                try:
                                    score_str = field.value.replace(",", "").strip()
                                    meme_data["score"] = int("".join(filter(str.isdigit, score_str)))
                                except (ValueError, AttributeError):
                                    meme_data["score"] = 0

                            # Source field: "📍 Source"
                            elif "source" in field_name or "📍" in field_name:
                                meme_data["source"] = field.value

                            # Author field: "👤 Author" OR "👤 Created by"
                            elif "author" in field_name or "created by" in field_name or "👤" in field_name:
                                author = field.value
                                if author.startswith("u/"):
                                    author = author[2:]
                                # For custom memes with mentions like <@123456>
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

                            # Requester field: "📤 Requested by"
                            elif "requested by" in field_name or "📤" in field_name:
                                field_requester = field.value
                                # Extract Discord username from mention
                                import re

                                mention_match = re.search(r"<@!?(\d+)>", field_requester)
                                if mention_match:
                                    user_id = mention_match.group(1)
                                    try:
                                        guild = bot.get_guild(Config.get_guild_id())
                                        if guild:
                                            member = guild.get_member(int(user_id))
                                            if member:
                                                field_requester = member.display_name or member.name
                                            else:
                                                field_requester = f"User {user_id}"
                                        else:
                                            field_requester = f"User {user_id}"
                                    except (ValueError, AttributeError):
                                        field_requester = f"User {user_id}"
                                # Prefer embed field over message content
                                requester = field_requester

                            # Daily Meme field: "📅 Daily Meme"
                            elif "daily meme" in field_name or "📅" in field_name:
                                meme_data["is_daily"] = True

                    # Add requester if found
                    if requester:
                        meme_data["requester"] = requester
                        logger.debug(f"✅ Set requester for meme {message_id_str}: {requester}")
                    else:
                        logger.debug(f"⚠️ No requester found for meme {message_id_str}")

                    # Set defaults
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
        memes = asyncio.run_coroutine_threadsafe(fetch_memes(), bot.loop).result(timeout=10)

        if memes is None:
            return jsonify({"error": "Meme channel not found"}), 404

        result = {"success": True, "memes": memes, "count": len(memes)}

        # Cache result for 60 seconds
        cache.set(cache_key, result, ttl=60)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error fetching latest memes: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch memes: {str(e)}"}), 500


@hazehub_cogs_bp.route("/api/hazehub/latest-rankups", methods=["GET"])
def get_latest_rankups():
    """Get latest rank-up announcements from RL channel (with cache)"""
    try:
        from flask import current_app

        limit = request.args.get("limit", 10, type=int)
        limit = min(limit, 50)  # Max 50 rank-ups

        # Check cache first (60 second TTL)
        cache_key = f"hazehub:latest_rankups:{limit}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return jsonify(cached_result)

        bot = current_app.config.get("bot_instance")
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
            async for message in channel.history(limit=100):  # Fetch more messages to find rank-ups
                # Check message content and embeds for rank-up keywords
                message_text = message.content.lower()

                # Check if it's a rank-up message
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

                # Only process rank-ups that have embeds
                if is_rankup and message.embeds:
                    import re

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
                        if embed.description:
                            # Extract user mention
                            user_match = re.search(r"<@!?(\d+)>", embed.description)
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

                            # Extract mode/playlist (e.g., "Your 2v2 rank")
                            mode_match = re.search(r"Your (\d+v\d+) rank", embed.description)
                            if mode_match:
                                rankup_data["mode"] = mode_match.group(1)

                            # Extract rank
                            rank_match = re.search(r"improved to (.+?)!", embed.description)
                            if rank_match:
                                rank_text = rank_match.group(1).strip()
                                # Remove Discord emoji codes
                                rank_text = re.sub(r"<:\w+:\d+>", "", rank_text).strip()
                                rank_text = re.sub(r":\w+:", "", rank_text).strip()
                                rankup_data["new_rank"] = rank_text if rank_text else "New Rank"
                            else:
                                rankup_data["new_rank"] = "New Rank"

                    # Extract user from message content if not found
                    if message.content and not rankup_data.get("user"):
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
        rankups = asyncio.run_coroutine_threadsafe(fetch_rankups(), bot.loop).result(timeout=10)

        if rankups is None:
            return jsonify({"error": "Rocket League channel not found"}), 404

        result = {"success": True, "rankups": rankups, "count": len(rankups)}

        # Cache result for 60 seconds
        cache.set(cache_key, result, ttl=60)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error fetching latest rank-ups: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch rank-ups: {str(e)}"}), 500


@hazehub_cogs_bp.route("/api/memes/<message_id>/upvote", methods=["POST"])
def toggle_upvote_meme(message_id):
    """Toggle upvote on a meme - custom system (not Discord reactions)"""
    try:
        from flask import current_app

        discord_id = request.discord_id
        if discord_id in ["legacy_user", "unknown"]:
            return jsonify({"error": "Discord authentication required"}), 401

        # Load current upvotes
        upvotes_file = Path(Config.DATA_DIR) / "hazehub_upvotes.json"
        upvotes = load_upvotes(upvotes_file)

        # Initialize message upvotes if not exists
        if message_id not in upvotes:
            upvotes[message_id] = []

        # Check if user has already upvoted via Discord
        has_discord_upvoted = False
        bot = current_app.config.get("bot_instance")
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

                try:
                    has_discord_upvoted = asyncio.run_coroutine_threadsafe(
                        fetch_discord_user_reacted(), bot.loop
                    ).result(timeout=5)
                except Exception:
                    pass

        if has_discord_upvoted:
            return (
                jsonify(
                    {
                        "error": "User has already upvoted via Discord. Cannot upvote again.",
                        "has_discord_upvoted": True,
                        "success": False,
                        "message_id": message_id,
                    }
                ),
                400,
            )

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
        save_upvotes(upvotes, upvotes_file)

        # Get current counts
        upvote_count = len(user_upvotes)
        has_upvoted_now = discord_id in user_upvotes

        return jsonify(
            {
                "success": True,
                "message_id": message_id,
                "action": action,
                "upvote_count": upvote_count,
                "has_upvoted": has_upvoted_now,
            }
        )

    except Exception as e:
        logger.error(f"Error toggling upvote: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to toggle upvote: {str(e)}"}), 500


@hazehub_cogs_bp.route("/api/memes/<message_id>/reactions", methods=["GET"])
def get_meme_reactions(message_id):
    """Get upvote counts for a meme (custom + Discord reactions combined)"""
    try:
        discord_id = request.discord_id

        # Load custom upvotes
        upvotes_file = Path(Config.DATA_DIR) / "hazehub_upvotes.json"
        custom_upvotes = load_upvotes(upvotes_file)
        user_upvotes = custom_upvotes.get(message_id, [])
        custom_count = len(user_upvotes)

        # Check if current user has custom upvoted
        has_custom_upvoted = False
        if discord_id not in ["legacy_user", "unknown"]:
            has_custom_upvoted = discord_id in user_upvotes

        # Get Discord reactions count and check if user has upvoted via Discord
        discord_count = 0
        has_discord_upvoted = False

        from flask import current_app

        bot = current_app.config.get("bot_instance")
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

                try:
                    discord_count, has_discord_upvoted = asyncio.run_coroutine_threadsafe(
                        fetch_discord_reactions_and_user(), bot.loop
                    ).result(timeout=5.0)
                except Exception as e:
                    logger.error(f"Error fetching Discord reactions: {e}")

        # Combine counts
        total_count = custom_count + discord_count
        has_upvoted = has_custom_upvoted or has_discord_upvoted

        return jsonify(
            {
                "success": True,
                "message_id": message_id,
                "upvotes": total_count,  # Flutter expects "upvotes", not "upvote_count"
                "upvote_count": total_count,  # Keep for backward compatibility
                "has_upvoted": has_upvoted,
                "has_discord_upvoted": has_discord_upvoted,  # Flutter needs this separately
                "breakdown": {
                    "custom": custom_count,
                    "discord": discord_count,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error getting meme reactions: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to get reactions: {str(e)}"}), 500


# ===== COG MANAGEMENT ENDPOINTS =====
