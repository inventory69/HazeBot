"""
Meme-related endpoints (sources, generator, tests, HazeHub, upvotes).
"""

import asyncio
import json
import random
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from flask import Blueprint, current_app, jsonify, request

import Config
from Utils.EmbedUtils import set_pink_footer
from Utils.Logger import Logger as logger
from api.utils.auth import require_permission, token_required

memes_bp = Blueprint("memes", __name__)

UPVOTES_FILE = Path(__file__).parent.parent / Config.DATA_DIR / "meme_upvotes.json"
NEGATIVE_EMOJIS = {"👎", "😡", "😠", "❌", "🚫"}


def load_upvotes():
    if UPVOTES_FILE.exists():
        with open(UPVOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_upvotes(upvotes):
    UPVOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(UPVOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(upvotes, f, indent=2)


@memes_bp.route("/api/meme-sources", methods=["GET"])
@token_required
def get_meme_sources():
    try:
        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Start with start_with_api.py"}), 503

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

        return jsonify({"error": f"Failed to get sources: {e}", "details": traceback.format_exc()}), 500


@memes_bp.route("/api/meme-generator/templates", methods=["GET"])
@token_required
@require_permission("meme_generator")
def get_meme_templates():
    try:
        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Start with start_with_api.py"}), 503

        meme_gen_cog = bot.get_cog("MemeGenerator")
        if not meme_gen_cog:
            return jsonify({"error": "MemeGenerator cog not loaded"}), 503

        from Config import IMGFLIP_PASSWORD, IMGFLIP_USERNAME

        if not IMGFLIP_USERNAME or not IMGFLIP_PASSWORD:
            return (
                jsonify(
                    {
                        "error": "Imgflip credentials not configured",
                        "details": "Set IMGFLIP_USERNAME and IMGFLIP_PASSWORD",
                    }
                ),
                503,
            )

        loop = bot.loop
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

        return jsonify({"error": f"Failed to get templates: {e}", "details": traceback.format_exc()}), 500


@memes_bp.route("/api/meme-generator/templates/refresh", methods=["POST"])
@token_required
@require_permission("meme_generator")
def refresh_meme_templates():
    try:
        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Start with start_with_api.py"}), 503

        meme_gen_cog = bot.get_cog("MemeGenerator")
        if not meme_gen_cog:
            return jsonify({"error": "MemeGenerator cog not loaded"}), 503

        loop = bot.loop
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

        return jsonify({"error": f"Failed to refresh templates: {e}", "details": traceback.format_exc()}), 500


@memes_bp.route("/api/meme-generator/generate", methods=["POST"])
@token_required
@require_permission("meme_generator")
def generate_meme():
    try:
        data = request.get_json()
        template_id = data.get("template_id")
        texts = data.get("texts", [])
        if not template_id:
            return jsonify({"error": "template_id is required"}), 400

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Start with start_with_api.py"}), 503

        meme_gen_cog = bot.get_cog("MemeGenerator")
        if not meme_gen_cog:
            return jsonify({"error": "MemeGenerator cog not loaded"}), 503

        loop = bot.loop
        if len(texts) <= 2:
            text0 = texts[0] if texts else ""
            text1 = texts[1] if len(texts) > 1 else ""
            future = asyncio.run_coroutine_threadsafe(meme_gen_cog.create_meme(template_id, text0, text1), loop)
        else:
            text_params = {f"text{i}": text for i, text in enumerate(texts)}
            future = asyncio.run_coroutine_threadsafe(meme_gen_cog.create_meme_advanced(template_id, text_params), loop)

        meme_url = future.result(timeout=15)
        if not meme_url:
            return jsonify({"error": "Failed to generate meme"}), 500
        return jsonify({"success": True, "url": meme_url})
    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to generate meme: {e}", "details": traceback.format_exc()}), 500


@memes_bp.route("/api/meme-generator/post-to-discord", methods=["POST"])
@token_required
@require_permission("meme_generator")
def post_generated_meme_to_discord():
    try:
        data = request.get_json()
        meme_url = data.get("meme_url")
        template_name = data.get("template_name", "Custom Meme")
        texts = data.get("texts", [])
        if not meme_url:
            return jsonify({"error": "meme_url is required"}), 400

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Start with start_with_api.py"}), 503

        meme_channel_id = Config.MEME_CHANNEL_ID
        channel = bot.get_channel(meme_channel_id)
        if not channel:
            return jsonify({"error": f"Meme channel {meme_channel_id} not found"}), 404

        loop = bot.loop
        guild = bot.get_guild(Config.get_guild_id())
        member = guild.get_member(int(request.discord_id)) if guild and request.discord_id else None

        async def post_meme():
            import discord

            embed = discord.Embed(
                title=f"Custom Meme: {template_name}",
                color=Config.PINK,
                timestamp=datetime.now(),
            )
            embed.set_image(url=meme_url)
            labels = ["Top Text", "Bottom Text", "Middle Text", "Text 4", "Text 5"]
            for i, text in enumerate(texts):
                if text and text.strip():
                    label = labels[i] if i < len(labels) else f"Text {i + 1}"
                    embed.add_field(name=label, value=text[:1024], inline=True)

            embed.add_field(name="Source", value="Meme Generator", inline=False)
            if member:
                embed.add_field(name="Created by", value=member.mention, inline=False)
            else:
                embed.add_field(name="Created via", value="Admin Panel", inline=False)

            set_pink_footer(embed, bot=bot.user)
            if member:
                await channel.send(f"Custom meme created by {member.mention}!", embed=embed)
            else:
                await channel.send("New custom meme generated!", embed=embed)

        future = asyncio.run_coroutine_threadsafe(post_meme(), loop)
        future.result(timeout=30)
        return jsonify(
            {"success": True, "message": "Meme posted to Discord successfully", "channel_id": meme_channel_id}
        )
    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to post meme to Discord: {e}", "details": traceback.format_exc()}), 500


@memes_bp.route("/api/test/meme-from-source", methods=["GET"])
@token_required
def test_meme_from_source():
    try:
        source = request.args.get("source")
        if not source or not source.strip():
            return (
                jsonify(
                    {
                        "error": (
                            "Missing 'source' parameter. Use subreddit name or lemmy community "
                            "(instance@community)"
                        ),
                    }
                ),
                400,
            )

        source = source.strip()
        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Start with start_with_api.py"}), 503

        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        loop = bot.loop
        if "@" in source:
            lemmy_source = source.lower()
            if lemmy_source not in daily_meme_cog.meme_lemmy:
                available = list(daily_meme_cog.meme_lemmy)
                return (
                    jsonify(
                        {"error": f"'{source}' is not configured as a Lemmy community", "available_lemmy": available}
                    ),
                    400,
                )
            future = asyncio.run_coroutine_threadsafe(daily_meme_cog.fetch_lemmy_meme(lemmy_source), loop)
            memes = future.result(timeout=30)
            source_display = lemmy_source
            source_type = "lemmy"
        else:
            subreddit = source.lower().strip().replace("r/", "")
            if not subreddit:
                return jsonify({"error": "Empty subreddit name"}), 400
            if subreddit not in daily_meme_cog.meme_subreddits:
                available = list(daily_meme_cog.meme_subreddits)
                return (
                    jsonify({"error": f"r/{subreddit} is not configured", "available_subreddits": available}),
                    400,
                )
            future = asyncio.run_coroutine_threadsafe(daily_meme_cog.fetch_reddit_meme(subreddit), loop)
            memes = future.result(timeout=30)
            source_display = f"r/{subreddit}"
            source_type = "reddit"

        if not memes:
            return jsonify({"error": f"No memes found from {source_display}"}), 404

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

        return jsonify({"error": f"Failed to fetch meme: {e}", "details": traceback.format_exc()}), 500


@memes_bp.route("/api/test/random-meme", methods=["GET"])
@token_required
def test_random_meme():
    try:
        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Start with start_with_api.py"}), 503

        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        loop = bot.loop
        future = asyncio.run_coroutine_threadsafe(
            daily_meme_cog.get_daily_meme(allow_nsfw=False, max_sources=3, min_score=50, pool_size=25),
            loop,
        )
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
        return jsonify({"error": "No suitable memes found"}), 404
    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to get random meme: {e}", "details": traceback.format_exc()}), 500


@memes_bp.route("/api/proxy/image", methods=["GET"])
def proxy_image():
    try:
        image_url = request.args.get("url")
        if not image_url:
            return jsonify({"error": "Missing 'url' parameter"}), 400

        allowed_domains = {
            "i.redd.it",
            "i.imgur.com",
            "preview.redd.it",
            "external-preview.redd.it",
            "i.imgflip.com",
            "imgflip.com",
        }
        parsed_url = urlparse(image_url)
        if not any(domain in parsed_url.netloc for domain in allowed_domains):
            return jsonify({"error": "URL domain not allowed"}), 403

        response = requests.get(image_url, timeout=10, stream=True)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "image/jpeg")
        return current_app.response_class(
            response.content,
            mimetype=content_type,
            headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=86400"},
        )
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to fetch image: {e}"}), 502
    except Exception as e:
        return jsonify({"error": f"Proxy error: {e}"}), 500


@memes_bp.route("/api/test/daily-meme", methods=["POST"])
@token_required
def test_daily_meme():
    try:
        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Start with start_with_api.py"}), 503

        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        loop = bot.loop
        future = asyncio.run_coroutine_threadsafe(daily_meme_cog.daily_meme_task(), loop)
        future.result(timeout=30)
        return jsonify({"success": True, "message": "Daily meme posted successfully"})
    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to post daily meme: {e}", "details": traceback.format_exc()}), 500


@memes_bp.route("/api/test/send-meme", methods=["POST"])
@token_required
def send_meme_to_discord():
    try:
        data = request.get_json()
        if not data or "meme" not in data:
            return jsonify({"error": "Meme data required"}), 400

        meme_data = data["meme"]
        if "upvotes" not in meme_data and "score" in meme_data:
            meme_data["upvotes"] = meme_data["score"]

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available"}), 503

        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        meme_channel_id = Config.MEME_CHANNEL_ID
        channel = bot.get_channel(meme_channel_id)
        if not channel:
            return jsonify({"error": f"Meme channel {meme_channel_id} not found"}), 404

        loop = bot.loop

        async def post_meme():
            import discord

            embed = discord.Embed(
                title=meme_data["title"][:256],
                url=meme_data["permalink"],
                color=Config.PINK,
                timestamp=datetime.now(),
            )
            embed.set_image(url=meme_data["url"])
            embed.add_field(name="Upvotes", value=f"{meme_data['upvotes']:,}", inline=True)

            source_name = f"r/{meme_data['subreddit']}"
            if meme_data["subreddit"].startswith("lemmy:"):
                source_name = meme_data["subreddit"].replace("lemmy:", "")

            embed.add_field(name="Source", value=source_name, inline=True)
            embed.add_field(name="Author", value=f"u/{meme_data['author']}", inline=True)

            requester_id = (
                request.discord_id if hasattr(request, "discord_id") and request.discord_id != "unknown" else None
            )
            if requester_id:
                embed.add_field(name="Requested by", value=f"<@{requester_id}>", inline=True)

            if meme_data.get("nsfw"):
                embed.add_field(name="NSFW", value="NSFW Content", inline=False)

            set_pink_footer(embed, bot=bot.user)
            message_text = (
                f"Meme sent from Admin Panel by <@{requester_id}>"
                if requester_id
                else "Meme sent from Admin Panel"
            )
            await channel.send(message_text, embed=embed)

        future = asyncio.run_coroutine_threadsafe(post_meme(), loop)
        future.result(timeout=30)
        return jsonify({"success": True, "message": "Meme sent to Discord successfully", "channel_id": meme_channel_id})
    except Exception as e:
        import traceback

        return jsonify({"error": f"Failed to send meme to Discord: {e}", "details": traceback.format_exc()}), 500


@memes_bp.route("/api/memes/<message_id>/upvote", methods=["POST"])
@token_required
def toggle_upvote_meme(message_id):
    try:
        discord_id = request.discord_id
        if discord_id in ["legacy_user", "unknown"]:
            return jsonify({"error": "Discord authentication required"}), 401

        upvotes = load_upvotes()
        if message_id not in upvotes:
            upvotes[message_id] = []

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
                            if any(str(user.id) == str(discord_id) for user in users if not user.bot):
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
            return jsonify(
                {
                    "error": "User has already upvoted via Discord. Cannot upvote again.",
                    "has_discord_upvoted": True,
                }
            ), 400

        user_upvotes = upvotes[message_id]
        if discord_id in user_upvotes:
            user_upvotes.remove(discord_id)
            action = "removed"
        else:
            user_upvotes.append(discord_id)
            action = "added"

        save_upvotes(upvotes)
        upvote_count = len(user_upvotes)
        has_upvoted_now = discord_id in user_upvotes

        logger.info(f"Upvote {action} by {request.username} on meme {message_id} (total: {upvote_count})")
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
        return jsonify({"error": f"Failed to toggle upvote: {e}"}), 500


@memes_bp.route("/api/memes/<message_id>/reactions", methods=["GET"])
@token_required
def get_meme_reactions(message_id):
    try:
        discord_id = request.discord_id

        custom_upvotes = load_upvotes()
        user_upvotes = custom_upvotes.get(message_id, [])
        custom_count = len(user_upvotes)
        has_custom_upvoted = discord_id not in ["legacy_user", "unknown"] and discord_id in user_upvotes

        discord_count = 0
        has_discord_upvoted = False
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
                        total = 0
                        user_reacted = False
                        for reaction in message.reactions:
                            emoji_str = str(reaction.emoji)
                            if emoji_str in NEGATIVE_EMOJIS:
                                continue
                            users = [user async for user in reaction.users()]
                            non_bot_users = [user for user in users if not user.bot]
                            total += len(non_bot_users)
                            if discord_id not in ["legacy_user", "unknown"] and any(
                                str(user.id) == str(discord_id) for user in non_bot_users
                            ):
                                user_reacted = True
                        return total, user_reacted
                    except Exception:
                        return 0, False

                try:
                    discord_count, has_discord_upvoted = asyncio.run_coroutine_threadsafe(
                        fetch_discord_reactions_and_user(), bot.loop
                    ).result(timeout=5)
                except Exception:
                    pass

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
        return jsonify({"error": f"Failed to fetch reactions: {e}"}), 500
