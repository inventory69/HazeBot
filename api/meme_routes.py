"""
Meme Routes Blueprint
Handles all /api/meme* and /api/daily-meme* endpoints for meme generation and management
"""

import asyncio
import traceback

import requests
from flask import Blueprint, jsonify, request

# Will be initialized by init_meme_routes()
Config = None
logger = None
token_required = None
require_permission = None
log_config_action = None

# Create Blueprint
meme_bp = Blueprint("meme", __name__)


def init_meme_routes(app, config, log, auth_module):
    """
    Initialize meme routes Blueprint with dependencies

    Args:
        app: Flask app instance
        config: Config module
        log: Logger instance
        auth_module: Module containing decorators
    """
    global Config, logger, token_required, require_permission, log_config_action

    Config = config
    logger = log
    token_required = auth_module.token_required
    require_permission = auth_module.require_permission
    log_config_action = auth_module.log_config_action

    # Apply decorators BEFORE blueprint registration
    import sys

    module = sys.modules[__name__]

    module.get_meme_sources = token_required(module.get_meme_sources)
    module.get_meme_templates = token_required(module.get_meme_templates)
    module.refresh_meme_templates = token_required(require_permission("all")(module.refresh_meme_templates))
    module.test_meme_from_source = token_required(module.test_meme_from_source)
    module.test_random_meme = token_required(module.test_random_meme)
    module.test_daily_meme = token_required(module.test_daily_meme)
    module.send_meme_to_discord = token_required(module.send_meme_to_discord)
    module.generate_meme = token_required(module.generate_meme)
    module.post_generated_meme_to_discord = token_required(module.post_generated_meme_to_discord)
    module.get_daily_meme_config = token_required(module.get_daily_meme_config)
    module.update_daily_meme_config = token_required(
        require_permission("all")(log_config_action("daily_meme")(module.update_daily_meme_config))
    )
    module.reset_daily_meme_config = token_required(
        require_permission("all")(log_config_action("daily_meme")(module.reset_daily_meme_config))
    )

    # Register blueprint AFTER decorators are applied
    app.register_blueprint(meme_bp)


# ===== MEME SOURCES =====


@meme_bp.route("/api/meme-sources", methods=["GET"])
def get_meme_sources():
    """Get available meme sources (subreddits and Lemmy communities)"""
    try:
        from flask import current_app

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Make sure to start with start_with_api.py"}), 503

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
        return jsonify({"error": f"Failed to get sources: {str(e)}", "details": traceback.format_exc()}), 500


# ===== MEME GENERATOR =====


@meme_bp.route("/api/meme-generator/templates", methods=["GET"])
def get_meme_templates():
    """Get available meme templates from Imgflip"""
    try:
        from flask import current_app

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Make sure to start with start_with_api.py"}), 503

        meme_gen_cog = bot.get_cog("MemeGenerator")
        if not meme_gen_cog:
            return jsonify({"error": "MemeGenerator cog not loaded"}), 503

        # Check if credentials are configured
        from Config import IMGFLIP_PASSWORD, IMGFLIP_USERNAME

        if not IMGFLIP_USERNAME or not IMGFLIP_PASSWORD:
            return (
                jsonify(
                    {
                        "error": "Imgflip credentials not configured",
                        "details": "Bot administrator needs to configure IMGFLIP_USERNAME and IMGFLIP_PASSWORD",
                    }
                ),
                503,
            )

        loop = bot.loop

        # Ensure templates are loaded
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
        return jsonify({"error": f"Failed to get templates: {str(e)}", "details": traceback.format_exc()}), 500


@meme_bp.route("/api/meme-generator/templates/refresh", methods=["POST"])
def refresh_meme_templates():
    """Force refresh meme templates from Imgflip API"""
    try:
        from flask import current_app

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Make sure to start with start_with_api.py"}), 503

        meme_gen_cog = bot.get_cog("MemeGenerator")
        if not meme_gen_cog:
            return jsonify({"error": "MemeGenerator cog not loaded"}), 503

        loop = bot.loop

        # Force fetch new templates
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
        return jsonify({"error": f"Failed to refresh templates: {str(e)}", "details": traceback.format_exc()}), 500


@meme_bp.route("/api/meme-generator/generate", methods=["POST"])
def generate_meme():
    """Generate a meme using Imgflip API"""
    try:
        from flask import current_app

        data = request.get_json()
        template_id = data.get("template_id")
        texts = data.get("texts", [])  # List of text strings

        if not template_id:
            return jsonify({"error": "template_id is required"}), 400

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Make sure to start with start_with_api.py"}), 503

        meme_gen_cog = bot.get_cog("MemeGenerator")
        if not meme_gen_cog:
            return jsonify({"error": "MemeGenerator cog not loaded"}), 503

        loop = bot.loop

        # Generate meme based on text count
        if len(texts) <= 2:
            # Simple meme with top/bottom text
            text0 = texts[0] if len(texts) > 0 else ""
            text1 = texts[1] if len(texts) > 1 else ""
            future = asyncio.run_coroutine_threadsafe(meme_gen_cog.create_meme(template_id, text0, text1), loop)
        else:
            # Advanced meme with multiple text boxes
            text_params = {f"text{i}": text for i, text in enumerate(texts)}
            future = asyncio.run_coroutine_threadsafe(meme_gen_cog.create_meme_advanced(template_id, text_params), loop)

        meme_url = future.result(timeout=15)

        if not meme_url:
            return jsonify({"error": "Failed to generate meme"}), 500

        return jsonify({"success": True, "url": meme_url})

    except Exception as e:
        return jsonify({"error": f"Failed to generate meme: {str(e)}", "details": traceback.format_exc()}), 500


@meme_bp.route("/api/meme-generator/post-to-discord", methods=["POST"])
def post_generated_meme_to_discord():
    """Post a generated meme to Discord"""
    try:
        from datetime import datetime

        import discord
        from flask import current_app

        from Utils.EmbedUtils import set_pink_footer

        data = request.get_json()
        meme_url = data.get("meme_url")
        template_name = data.get("template_name", "Custom Meme")
        texts = data.get("texts", [])

        if not meme_url:
            return jsonify({"error": "meme_url is required"}), 400

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Make sure to start with start_with_api.py"}), 503

        # Get meme channel
        meme_channel_id = Config.MEME_CHANNEL_ID
        channel = bot.get_channel(meme_channel_id)
        if not channel:
            return jsonify({"error": f"Meme channel {meme_channel_id} not found"}), 404

        loop = bot.loop

        # Get Discord user from JWT token
        discord_id = request.discord_id
        guild = bot.get_guild(Config.get_guild_id())
        member = None
        if guild and discord_id:
            member = guild.get_member(int(discord_id))

        # Post the meme to Discord
        async def post_meme():
            embed = discord.Embed(
                title=f"🎨 Custom Meme: {template_name}",
                color=Config.PINK,
                timestamp=datetime.now(),
            )
            embed.set_image(url=meme_url)

            # Add text fields if provided
            labels = ["🔝 Top Text", "🔽 Bottom Text", "⏺️ Middle Text", "📝 Text 4", "📝 Text 5"]
            for i, text in enumerate(texts):
                if text and text.strip():
                    label = labels[i] if i < len(labels) else f"📝 Text {i + 1}"
                    embed.add_field(name=label, value=text[:1024], inline=True)

            # Add source field for custom memes
            embed.add_field(name="📍 Source", value="Meme Generator", inline=False)

            # Add creator field
            if member:
                embed.add_field(name="👤 Created by", value=member.mention, inline=False)
            else:
                embed.add_field(name="🖥️ Created via", value="Admin Panel", inline=False)

            set_pink_footer(embed, bot=bot.user)

            # Send with mention if we have member
            if member:
                await channel.send(f"🎨 Custom meme created by {member.mention}!", embed=embed)
            else:
                await channel.send("🎨 New custom meme generated!", embed=embed)

        future = asyncio.run_coroutine_threadsafe(post_meme(), loop)
        future.result(timeout=30)

        return jsonify(
            {
                "success": True,
                "message": "Meme posted to Discord successfully",
                "channel_id": meme_channel_id,
            }
        )

    except Exception as e:
        return jsonify({"error": f"Failed to post meme to Discord: {str(e)}", "details": traceback.format_exc()}), 500


# ===== DAILY MEME CONFIG =====


@meme_bp.route("/api/daily-meme/config", methods=["GET"])
def get_daily_meme_config():
    """Get daily meme configuration"""
    try:
        from flask import current_app

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        # Merge config with available sources
        config_with_sources = {
            **daily_meme_cog.daily_config,
            "available_subreddits": daily_meme_cog.meme_subreddits,
            "available_lemmy": daily_meme_cog.meme_lemmy,
        }

        # Convert Discord IDs to strings to prevent precision loss in Flutter Web
        if "channel_id" in config_with_sources and config_with_sources["channel_id"]:
            config_with_sources["channel_id"] = str(config_with_sources["channel_id"])
        if "role_id" in config_with_sources and config_with_sources["role_id"]:
            config_with_sources["role_id"] = str(config_with_sources["role_id"])

        return jsonify(config_with_sources)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@meme_bp.route("/api/daily-meme/config", methods=["POST"])
def update_daily_meme_config():
    """Update daily meme configuration"""
    try:
        from flask import current_app

        data = request.json

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        # Extract meme sources if provided
        if "subreddits" in data:
            daily_meme_cog.meme_subreddits = data.pop("subreddits")
            daily_meme_cog.save_subreddits()

        if "lemmy_communities" in data:
            daily_meme_cog.meme_lemmy = data.pop("lemmy_communities")
            daily_meme_cog.save_lemmy_communities()

        # Update configuration
        daily_meme_cog.daily_config.update(data)
        daily_meme_cog.save_daily_config()

        # Restart task if needed
        daily_meme_cog.restart_daily_task()

        # Convert Discord IDs to strings for response
        response_config = daily_meme_cog.daily_config.copy()
        if "channel_id" in response_config and response_config["channel_id"]:
            response_config["channel_id"] = str(response_config["channel_id"])
        if "role_id" in response_config and response_config["role_id"]:
            response_config["role_id"] = str(response_config["role_id"])

        return jsonify({"success": True, "message": "Daily meme configuration updated", "config": response_config})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@meme_bp.route("/api/daily-meme/config/reset", methods=["POST"])
def reset_daily_meme_config():
    """Reset daily meme configuration to defaults"""
    try:
        from flask import current_app

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        # Reset to defaults
        daily_meme_cog.daily_config = {
            "enabled": True,
            "hour": 12,
            "minute": 0,
            "channel_id": Config.MEME_CHANNEL_ID,
            "role_id": Config.MEME_ROLE_ID,
            "allow_nsfw": True,
            "min_score": 100,
            "max_sources": 5,
            "pool_size": 50,
            "use_subreddits": None,  # None = use all
            "use_lemmy": None,  # None = use all
        }
        daily_meme_cog.save_daily_config()
        daily_meme_cog.restart_daily_task()

        # Convert Discord IDs to strings for response
        response_config = daily_meme_cog.daily_config.copy()
        if "channel_id" in response_config and response_config["channel_id"]:
            response_config["channel_id"] = str(response_config["channel_id"])
        if "role_id" in response_config and response_config["role_id"]:
            response_config["role_id"] = str(response_config["role_id"])

        return jsonify(
            {
                "success": True,
                "message": "Daily meme configuration reset to defaults",
                "config": response_config,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@meme_bp.route("/api/proxy/image", methods=["GET"])
def proxy_image():
    """Proxy external images to bypass CORS restrictions"""
    try:
        from urllib.parse import urlparse
        from flask import current_app

        # Get the image URL from query parameter
        image_url = request.args.get("url")
        if not image_url:
            return jsonify({"error": "Missing 'url' parameter"}), 400

        # Validate URL is from allowed domains (security measure)
        allowed_domains = [
            "i.redd.it",
            "i.imgur.com",
            "preview.redd.it",
            "external-preview.redd.it",
            "i.imgflip.com",
            "imgflip.com",
        ]

        parsed_url = urlparse(image_url)
        if not any(domain in parsed_url.netloc for domain in allowed_domains):
            return jsonify({"error": "URL domain not allowed"}), 403

        # Fetch the image
        response = requests.get(image_url, timeout=10, stream=True)
        response.raise_for_status()

        # Get content type
        content_type = response.headers.get("Content-Type", "image/jpeg")

        # Return the image with proper CORS headers
        return current_app.response_class(
            response.content,
            mimetype=content_type,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
            },
        )

    except requests.exceptions.Timeout:
        return jsonify({"error": "Image request timed out"}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Error proxying image: {e}")
        return jsonify({"error": "Failed to fetch image"}), 502
    except Exception as e:
        logger.error(f"Unexpected error in proxy_image: {e}")
        return jsonify({"error": "Internal server error"}), 500


@meme_bp.route("/api/test/meme-from-source", methods=["GET"])
def test_meme_from_source():
    """Get a meme from a specific source (subreddit or Lemmy community)"""
    try:
        import random
        from flask import current_app

        # Get source parameter
        source = request.args.get("source")
        if not source or not source.strip():
            return jsonify(
                {"error": "Missing 'source' parameter. Use subreddit name or lemmy community (instance@community)"}
            ), 400

        source = source.strip()

        # Get bot instance
        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Make sure to start with start_with_api.py"}), 503

        # Get DailyMeme cog
        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        # Use the bot's existing event loop
        loop = bot.loop

        # Determine if it's Lemmy or Reddit
        if "@" in source:
            # Lemmy community
            lemmy_source = source.lower()
            if lemmy_source not in daily_meme_cog.meme_lemmy:
                available = list(daily_meme_cog.meme_lemmy)
                return jsonify(
                    {
                        "error": f"'{source}' is not configured as a Lemmy community",
                        "available_lemmy": available,
                    }
                ), 400

            # Fetch from Lemmy
            future = asyncio.run_coroutine_threadsafe(
                daily_meme_cog.fetch_lemmy_meme(lemmy_source),
                loop,
            )
            memes = future.result(timeout=30)
            source_display = lemmy_source
            source_type = "lemmy"

        else:
            # Reddit subreddit - normalize the input
            subreddit = source.lower().strip().replace("r/", "")

            if not subreddit:
                return jsonify({"error": "Empty subreddit name"}), 400

            if subreddit not in daily_meme_cog.meme_subreddits:
                available = list(daily_meme_cog.meme_subreddits)
                return jsonify(
                    {
                        "error": f"r/{subreddit} is not configured",
                        "available_subreddits": available,
                    }
                ), 400

            # Fetch from Reddit
            future = asyncio.run_coroutine_threadsafe(
                daily_meme_cog.fetch_reddit_meme(subreddit),
                loop,
            )
            memes = future.result(timeout=30)
            source_display = f"r/{subreddit}"
            source_type = "reddit"

        if not memes:
            return jsonify({"error": f"No memes found from {source_display}"}), 404

        # Pick random meme
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
        return jsonify({"error": f"Failed to fetch meme: {str(e)}", "details": traceback.format_exc()}), 500


@meme_bp.route("/api/test/random-meme", methods=["GET"])
def test_random_meme():
    """Get a random meme from configured sources using the actual bot function"""
    try:
        from flask import current_app

        # Get bot instance
        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Make sure to start with start_with_api.py"}), 503

        # Get DailyMeme cog
        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        # Use the bot's existing event loop instead of creating a new one
        loop = bot.loop

        # Create a future and schedule it on the bot's loop
        future = asyncio.run_coroutine_threadsafe(
            daily_meme_cog.get_daily_meme(
                allow_nsfw=False,  # Don't allow NSFW for admin panel
                max_sources=3,  # Fetch from 3 sources for speed
                min_score=50,  # Lower threshold for testing
                pool_size=25,  # Smaller pool for speed
            ),
            loop,
        )

        # Wait for result with timeout
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
        else:
            return jsonify({"error": "No suitable memes found"}), 404

    except Exception as e:
        return jsonify({"error": f"Failed to get random meme: {str(e)}", "details": traceback.format_exc()}), 500


@meme_bp.route("/api/test/daily-meme", methods=["POST"])
def test_daily_meme():
    """Test daily meme posting using the actual bot function"""
    try:
        from flask import current_app

        # Get bot instance
        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available. Make sure to start with start_with_api.py"}), 503

        # Get DailyMeme cog
        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        # Use the bot's existing event loop
        loop = bot.loop

        # Call the actual daily meme task function
        future = asyncio.run_coroutine_threadsafe(daily_meme_cog.daily_meme_task(), loop)

        # Wait for result with timeout
        future.result(timeout=30)

        return jsonify(
            {
                "success": True,
                "message": "Daily meme posted successfully",
                "note": "Check your Discord meme channel to see the posted meme",
            }
        )

    except Exception as e:
        return jsonify({"error": f"Failed to post daily meme: {str(e)}", "details": traceback.format_exc()}), 500


@meme_bp.route("/api/test/send-meme", methods=["POST"])
def send_meme_to_discord():
    """Send a specific meme to Discord"""
    try:
        from datetime import datetime
        from flask import current_app
        import discord
        from Utils.EmbedUtils import set_pink_footer

        # Get meme data from request
        data = request.get_json()
        if not data or "meme" not in data:
            return jsonify({"error": "Meme data required"}), 400

        meme_data = data["meme"]

        # Ensure meme_data has the correct structure expected by post_meme
        # The bot expects: url, title, subreddit, upvotes, author, permalink, nsfw
        if "upvotes" not in meme_data and "score" in meme_data:
            meme_data["upvotes"] = meme_data["score"]

        # Get bot instance
        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot instance not available"}), 503

        # Get DailyMeme cog
        daily_meme_cog = bot.get_cog("DailyMeme")
        if not daily_meme_cog:
            return jsonify({"error": "DailyMeme cog not loaded"}), 503

        # Get meme channel
        meme_channel_id = Config.MEME_CHANNEL_ID
        channel = bot.get_channel(meme_channel_id)
        if not channel:
            return jsonify({"error": f"Meme channel {meme_channel_id} not found"}), 404

        # Use the bot's existing event loop
        loop = bot.loop

        # Post the meme to Discord with custom message
        async def post_meme():
            # Create embed manually (same as post_meme but with custom message)
            embed = discord.Embed(
                title=meme_data["title"][:256],
                url=meme_data["permalink"],
                color=Config.PINK,
                timestamp=datetime.now(),
            )
            embed.set_image(url=meme_data["url"])
            embed.add_field(name="👍 Upvotes", value=f"{meme_data['upvotes']:,}", inline=True)

            # Display source appropriately
            source_name = f"r/{meme_data['subreddit']}"
            if meme_data["subreddit"].startswith("lemmy:"):
                source_name = meme_data["subreddit"].replace("lemmy:", "")

            embed.add_field(name="📍 Source", value=source_name, inline=True)
            embed.add_field(name="👤 Author", value=f"u/{meme_data['author']}", inline=True)

            # Get requester Discord ID from token
            requester_id = (
                request.discord_id if hasattr(request, "discord_id") and request.discord_id != "unknown" else None
            )

            # Add requester field to embed if available
            if requester_id:
                embed.add_field(name="📤 Requested by", value=f"<@{requester_id}>", inline=True)

            if meme_data.get("nsfw"):
                embed.add_field(name="⚠️", value="NSFW Content", inline=False)

            set_pink_footer(embed, bot=bot.user)

            # Send with custom message including requester mention
            if requester_id:
                message_text = f"🎭 Meme sent from Admin Panel by <@{requester_id}>"
            else:
                message_text = "🎭 Meme sent from Admin Panel"

            await channel.send(message_text, embed=embed)

        future = asyncio.run_coroutine_threadsafe(post_meme(), loop)
        future.result(timeout=30)

        return jsonify({"success": True, "message": "Meme sent to Discord successfully", "channel_id": meme_channel_id})

    except Exception as e:
        return jsonify({"error": f"Failed to send meme to Discord: {str(e)}", "details": traceback.format_exc()}), 500
