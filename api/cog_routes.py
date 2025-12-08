"""
Cog Management Routes Blueprint
Handles all /api/cogs/* endpoints for bot cog management
"""

import asyncio
import os
import time

from flask import Blueprint, jsonify

# Will be initialized by init_cog_routes()
logger = None
token_required = None
require_permission = None

# Create Blueprint
cog_bp = Blueprint("cogs", __name__)


def init_cog_routes(app, log, auth_module):
    """
    Initialize cog routes Blueprint with dependencies

    Args:
        app: Flask app instance
        log: Logger instance
        auth_module: Module containing decorators (token_required, require_permission)
    """
    global logger, token_required, require_permission

    logger = log
    token_required = auth_module.token_required
    require_permission = auth_module.require_permission

    # Register blueprint WITHOUT decorators first
    app.register_blueprint(cog_bp)

    # NOW apply decorators to already-registered view functions
    vf = app.view_functions
    vf["cogs.get_cogs"] = token_required(require_permission("all")(vf["cogs.get_cogs"]))
    vf["cogs.load_cog"] = token_required(require_permission("all")(vf["cogs.load_cog"]))
    vf["cogs.unload_cog"] = token_required(require_permission("all")(vf["cogs.unload_cog"]))
    vf["cogs.reload_cog"] = token_required(require_permission("all")(vf["cogs.reload_cog"]))
    vf["cogs.get_cog_logs"] = token_required(require_permission("all")(vf["cogs.get_cog_logs"]))


# Cog metadata (features, descriptions, icons)
COG_METADATA = {
    "APIServer": {
        "description": "Manages the Flask REST API server for the admin panel",
        "icon": "api",
        "category": "core",
        "features": [
            "Waitress WSGI Server",
            "JWT Token Auth",
            "CORS Support",
            "Hot Reload via Cog System",
            "Port Binding Retry (8×3s)",
            "Graceful Shutdown",
            "/apistatus Command",
            "/apirestart Command",
        ],
    },
    "AnalyticsManager": {
        "description": "Manages analytics tracking with SQLite backend",
        "icon": "analytics",
        "category": "monitoring",
        "features": [
            "SQLite Backend (WAL mode)",
            "Real-time Session Tracking",
            "User Statistics",
            "Daily Analytics Aggregation",
            "Error Tracking",
            "Hot Reload via CogManager",
            "Graceful Shutdown with DB Flush",
            "64MB Query Cache",
            "15+ Optimized Indexes",
        ],
    },
    "CogManager": {
        "description": "Dynamic cog loading, unloading, and reloading system",
        "icon": "settings",
        "category": "core",
        "features": [
            "/load Command",
            "/unload Command",
            "/reload Command",
            "/listcogs Command",
            "/logs <cog> Command",
            "Interactive Dropdown Selection",
            "Disabled Cogs State File",
            "Log Censoring (URLs/Secrets)",
        ],
    },
    "Changelog": {
        "description": "Manages changelog notifications and version updates",
        "icon": "update",
        "category": "notifications",
        "features": [
            "/changelog Command",
            "GPT-4.1-nano Title Generation",
            "Discord Markdown Formatting",
            "Changelog Role Ping",
            "Opt-in Button",
            "Persistent Views",
            "/update_changelog_view Command",
        ],
    },
    "DailyMeme": {
        "description": "Automated daily meme posting from Reddit and Lemmy",
        "icon": "image",
        "category": "content",
        "features": [
            "Reddit Top Posts",
            "Lemmy Community Support",
            "Daily Scheduled Post (10 AM)",
            "/testmeme Command",
            "/memesubreddits Management",
            "/lemmycommunities Management",
            "/memesources Enable/Disable",
            "/dailyconfig Command",
        ],
    },
    "DiscordLogging": {
        "description": "Logs bot events and errors to a Discord channel",
        "icon": "analytics",
        "category": "monitoring",
        "features": [
            "INFO/WARNING/ERROR Levels",
            "Cog Color-coded Embeds",
            "Emoji Prefixes per Cog",
            "/togglediscordlogs Command",
            "/testdiscordlog Command",
            "Auto-disable on Errors",
            "Rate Limiting (1 msg/2s)",
        ],
    },
    "GamingHub": {
        "description": "Community gaming features with presence tracking",
        "icon": "sports_esports",
        "category": "community",
        "features": [
            "Online/Idle/DND/Offline Status",
            "Current Game Detection",
            "Game Request Posts",
            "Accept/Decline/Maybe Buttons",
            "DM Notifications to Requester",
            "Auto-fill Current Game",
            "Member Filter (All/Online/Playing)",
            "Persistent Views Restore",
        ],
    },
    "Leaderboard": {
        "description": "Server activity leaderboard and statistics",
        "icon": "leaderboard",
        "category": "community",
        "features": [
            "/leaderboard Command",
            "Message Count Tracking",
            "Image Share Tracking",
            "Meme Requests Count",
            "Memes Generated Count",
            "Resolved Tickets Count",
            "Rocket League Rank Display",
            "Interactive Dropdown",
        ],
    },
    "MemeGenerator": {
        "description": "Create custom memes with Imgflip templates",
        "icon": "create",
        "category": "content",
        "features": [
            "/creatememe Command",
            "100+ Imgflip Templates",
            "Interactive Template Selector",
            "Dynamic Text Input Modal",
            "1-5 Text Boxes per Template",
            "Imgflip API Integration",
            "Author Tracking in Embed",
            "/refreshtemplates Command",
        ],
    },
    "ModPerks": {
        "description": "Moderator utilities and management tools",
        "icon": "shield",
        "category": "moderation",
        "features": [
            "/mod Command",
            "/modpanel Interactive View",
            "/modoverview Stats Display",
            "/moddetails Member Stats",
            "/optins Management",
            "Permission-based Access",
            "Admin/Mod Role Checks",
        ],
    },
    "Preferences": {
        "description": "User preference management for notifications",
        "icon": "tune",
        "category": "user",
        "features": [
            "/preferences Command",
            "Changelog Role Toggle",
            "Daily Meme Role Toggle",
            "Interactive Buttons",
            "Role Add/Remove",
            "JSON Preference Storage",
            "Persistent State",
        ],
    },
    "Presence": {
        "description": "Bot status and activity rotation system",
        "icon": "visibility",
        "category": "core",
        "features": [
            "Playing Activity",
            "Watching Activity",
            "Listening Activity",
            "Custom Status Messages",
            "Server Count Display",
            "Member Count Display",
            "Hourly Rotation (3600s)",
        ],
    },
    "Profile": {
        "description": "User profile viewing and statistics",
        "icon": "person",
        "category": "user",
        "features": [
            "/profile Command",
            "Discord Join Date",
            "Server Join Date",
            "Role List",
            "Rocket League Ranks",
            "Activity Stats",
            "Avatar Thumbnail",
        ],
    },
    "RocketLeague": {
        "description": "Rocket League rank tracking with automatic updates",
        "icon": "rocket_launch",
        "category": "gaming",
        "features": [
            "/rocket Hub Command",
            "/setrlaccount (Epic/Steam)",
            "/rlstats View Stats",
            "/unlinkrlaccount Command",
            "1v1/2v2/3v3/4v4 Support",
            "Division Tracking (I-IV)",
            "Auto Rank Check (3h)",
            "Promotion Embeds + Congrats",
            "FlareSolverr Cloudflare Bypass",
            "/restorecongratsview Admin",
        ],
    },
    "RoleInfo": {
        "description": "Server role information and descriptions",
        "icon": "badge",
        "category": "info",
        "features": [
            "/roleinfo Command",
            "Role Descriptions",
            "Permission List",
            "Member Count",
            "Role Color Display",
            "Role ID Display",
            "Formatted Embed",
        ],
    },
    "ServerGuide": {
        "description": "Interactive server guide with quick access buttons",
        "icon": "menu_book",
        "category": "info",
        "features": [
            "/server-guide Command",
            "Help Button",
            "Ticket Button",
            "Profile Button",
            "Rocket League Hub",
            "Warframe Hub",
            "Preferences Button",
            "Interactive Embeds",
        ],
    },
    "SupportButtons": {
        "description": "Persistent support buttons for common actions",
        "icon": "support_agent",
        "category": "support",
        "features": [
            "/create-button Command",
            "Ticket Buttons",
            "Slash Command Buttons",
            "Prefix Command Buttons",
            "Custom Labels/Emojis",
            "Persistent Views",
            "JSON Persistence",
        ],
    },
    "TicketSystem": {
        "description": "Support ticket system with transcripts",
        "icon": "confirmation_number",
        "category": "support",
        "features": [
            "/ticket Command",
            "Support Categories",
            "Claim/Close/Reopen",
            "Add/Remove Users",
            "Transcript Generation",
            "Email Transcripts",
            "Numbered Tickets",
            "JSON Persistence",
        ],
    },
    "TodoList": {
        "description": "Server-wide todo list management",
        "icon": "checklist",
        "category": "productivity",
        "features": [
            "/todo-update Command",
            "Interactive View",
            "Add/Complete/Delete",
            "Priority Levels",
            "Persistent Storage",
            "Formatted Display",
            "JSON Persistence",
        ],
    },
    "Utility": {
        "description": "General utility commands and helper functions",
        "icon": "build",
        "category": "utility",
        "features": [
            "/help Command",
            "/status Command",
            "/clear Command",
            "/say Command",
            "/sync Command",
            "Embed Utils",
            "Admin Tools",
        ],
    },
    "Warframe": {
        "description": "Warframe market integration and game status",
        "icon": "videogame_asset",
        "category": "gaming",
        "features": [
            "/warframe Hub",
            "Game Status",
            "Market Search",
            "Invasions Display",
            "Sortie Info",
            "Price Statistics",
            "Top Orders",
            "Warframe.market API",
        ],
    },
    "Welcome": {
        "description": "Welcome system with rule acceptance and roles",
        "icon": "waving_hand",
        "category": "community",
        "features": [
            "Interest Selection",
            "Rules Acceptance",
            "Member Role Grant",
            "Random Greetings",
            "Server Guide Link",
            "Persistent Views",
            "Event Listeners",
        ],
    },
    "StatusDashboard": {
        "description": (
            "Maintains a live-updating status embed in a dedicated channel with real-time service monitoring"
        ),
        "icon": "📊",
        "category": "monitoring",
        "features": [
            "Live Status Embed",
            "Real-time Updates",
            "Service Monitoring",
            "Configurable Update Interval",
            "Bot Statistics Display",
            "Utility Cog Integration",
            "Auto-Message Management",
        ],
    },
}


@cog_bp.route("/api/cogs", methods=["GET"])
def get_cogs():
    """Get list of all cogs with their status"""
    from flask import current_app

    try:
        # Get bot instance
        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Get cog manager instance
        cog_manager = bot.get_cog("CogManager")
        if not cog_manager:
            return jsonify({"error": "CogManager not available"}), 503

        # Get all cog files and their class names
        all_cogs = cog_manager.get_all_cog_files()

        # Get loaded cogs
        loaded_cogs = list(bot.cogs.keys())

        # Get disabled cogs
        disabled_cogs = cog_manager.get_disabled_cogs()

        # Build response
        cogs_list = []
        for file_name, class_name in all_cogs.items():
            status = "loaded" if class_name in loaded_cogs else "unloaded"
            if file_name in disabled_cogs:
                status = "disabled"

            # Use file_name as key for metadata lookup
            metadata = COG_METADATA.get(
                file_name,
                {
                    "description": f"Discord bot module: {class_name}",
                    "icon": "extension",
                    "category": "other",
                    "features": [],
                },
            )

            cogs_list.append(
                {
                    "name": class_name,
                    "file_name": file_name,
                    "status": status,
                    "description": metadata["description"],
                    "icon": metadata["icon"],
                    "category": metadata["category"],
                    "features": metadata["features"],
                    "can_load": status in ["unloaded", "disabled"],
                    "can_unload": status == "loaded" and class_name != "CogManager",
                    "can_reload": status == "loaded" and class_name != "CogManager",
                    "can_view_logs": status == "loaded",
                }
            )

        # Sort by category, then by name
        category_order = [
            "core",
            "community",
            "content",
            "gaming",
            "moderation",
            "support",
            "user",
            "info",
            "productivity",
            "utility",
            "notifications",
            "monitoring",
            "other",
        ]
        cogs_list.sort(
            key=lambda c: (
                category_order.index(c["category"]) if c["category"] in category_order else 999,
                c["name"],
            )
        )

        return jsonify(
            {
                "success": True,
                "cogs": cogs_list,
                "total": len(cogs_list),
                "loaded_count": len([c for c in cogs_list if c["status"] == "loaded"]),
                "disabled_count": len([c for c in cogs_list if c["status"] == "disabled"]),
            }
        )

    except Exception as e:
        logger.error(f"Error getting cogs list: {e}")
        return jsonify({"error": f"Failed to get cogs list: {str(e)}"}), 500


@cog_bp.route("/api/cogs/<cog_name>/load", methods=["POST"])
def load_cog(cog_name):
    """Load a cog"""
    from flask import current_app

    try:
        # Get bot instance
        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Get cog manager instance
        cog_manager = bot.get_cog("CogManager")
        if not cog_manager:
            return jsonify({"error": "CogManager not available"}), 503

        # Find the file name for this cog
        all_cogs = cog_manager.get_all_cog_files()
        file_name = None

        # Try to match by class name first, then by file name
        for fname, cname in all_cogs.items():
            if cname == cog_name or fname == cog_name:
                file_name = fname
                break

        if not file_name:
            return jsonify({"error": f"Cog '{cog_name}' not found"}), 404

        # Check if already loaded
        loaded_cogs = list(bot.cogs.keys())
        class_name = all_cogs.get(file_name, file_name)
        if class_name in loaded_cogs:
            return jsonify({"error": f"Cog '{cog_name}' is already loaded"}), 400

        # Load the cog
        success, message = asyncio.run_coroutine_threadsafe(cog_manager.load_cog_api(file_name), bot.loop).result(
            timeout=10
        )

        if success:
            return jsonify(
                {
                    "success": True,
                    "message": message,
                    "cog": {"name": class_name, "file_name": file_name, "status": "loaded"},
                }
            )
        else:
            return jsonify({"error": message}), 500

    except Exception as e:
        logger.error(f"Error loading cog {cog_name}: {e}")
        return jsonify({"error": f"Failed to load cog: {str(e)}"}), 500


@cog_bp.route("/api/cogs/<cog_name>/unload", methods=["POST"])
def unload_cog(cog_name):
    """Unload a cog"""
    from flask import current_app

    try:
        # Get bot instance
        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Get cog manager instance
        cog_manager = bot.get_cog("CogManager")
        if not cog_manager:
            return jsonify({"error": "CogManager not available"}), 503

        # Check if trying to unload critical cogs
        if cog_name.lower() == "cogmanager":
            return jsonify({"error": "Cannot unload CogManager"}), 400

        # Check if trying to unload APIServer
        if cog_name.lower() == "apiserver":
            return jsonify({"error": "APIServer cannot be unloaded. Use reload instead."}), 403

        # Find the file name for this cog
        all_cogs = cog_manager.get_all_cog_files()
        file_name = None
        class_name = cog_name

        # Try to match by class name first, then by file name
        for fname, cname in all_cogs.items():
            if cname == cog_name or fname == cog_name:
                file_name = fname
                class_name = cname
                break

        if not file_name:
            return jsonify({"error": f"Cog '{cog_name}' not found"}), 404

        # Check if loaded
        loaded_cogs = list(bot.cogs.keys())
        if class_name not in loaded_cogs:
            return jsonify({"error": f"Cog '{cog_name}' is not loaded"}), 400

        # Unload the cog
        success, message = asyncio.run_coroutine_threadsafe(cog_manager.unload_cog_api(class_name), bot.loop).result(
            timeout=10
        )

        if success:
            return jsonify(
                {
                    "success": True,
                    "message": message,
                    "cog": {"name": class_name, "file_name": file_name, "status": "unloaded"},
                }
            )
        else:
            return jsonify({"error": message}), 500

    except Exception as e:
        logger.error(f"Error unloading cog {cog_name}: {e}")
        return jsonify({"error": f"Failed to unload cog: {str(e)}"}), 500


@cog_bp.route("/api/cogs/<cog_name>/reload", methods=["POST"])
def reload_cog(cog_name):
    """Reload a cog"""
    from flask import current_app

    try:
        # Get bot instance
        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Get cog manager instance
        cog_manager = bot.get_cog("CogManager")
        if not cog_manager:
            return jsonify({"error": "CogManager not available"}), 503

        # Check if trying to reload CogManager
        if cog_name.lower() == "cogmanager":
            return jsonify({"error": "Cannot reload CogManager"}), 400

        # Find the file name for this cog
        all_cogs = cog_manager.get_all_cog_files()
        file_name = None
        class_name = cog_name

        # Try to match by class name first, then by file name
        for fname, cname in all_cogs.items():
            if cname == cog_name or fname == cog_name:
                file_name = fname
                class_name = cname
                break

        if not file_name:
            return jsonify({"error": f"Cog '{cog_name}' not found"}), 404

        # Check if loaded
        loaded_cogs = list(bot.cogs.keys())
        if class_name not in loaded_cogs:
            return jsonify({"error": f"Cog '{cog_name}' is not loaded"}), 400

        # Reload the cog using the API method
        # Longer timeout for APIServer and other slow-loading cogs
        timeout = 35 if class_name == "APIServer" else 15

        try:
            success, message = asyncio.run_coroutine_threadsafe(
                cog_manager.reload_cog_api(class_name), bot.loop
            ).result(timeout=timeout)

            if success:
                return jsonify(
                    {
                        "success": True,
                        "message": message,
                        "cog": {"name": class_name, "file_name": file_name, "status": "loaded"},
                    }
                )
            else:
                return jsonify({"error": message}), 500

        except asyncio.TimeoutError:
            # For APIServer, timeout might occur during reload (expected)
            # Wait a bit more and check if it's actually loaded
            if class_name == "APIServer":
                time.sleep(3)
                # Check if APIServer is now loaded
                if "APIServer" in bot.cogs:
                    return jsonify(
                        {
                            "success": True,
                            "message": f"Cog '{class_name}' reloaded successfully (delayed)",
                            "cog": {"name": class_name, "file_name": file_name, "status": "loaded"},
                        }
                    )
            raise

    except Exception as e:
        # Don't log expected errors for APIServer reload
        if not (class_name == "APIServer" and ("timeout" in str(e).lower() or "file descriptor" in str(e).lower())):
            logger.error(f"Error reloading cog {cog_name}: {e}")
        return jsonify({"error": f"Failed to reload cog: {str(e)}"}), 500


@cog_bp.route("/api/cogs/<cog_name>/logs", methods=["GET"])
def get_cog_logs(cog_name):
    """Get logs for a specific cog"""
    from flask import current_app

    try:
        # Get bot instance
        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Get cog manager instance
        cog_manager = bot.get_cog("CogManager")
        if not cog_manager:
            return jsonify({"error": "CogManager not available"}), 503

        # Find the actual cog name
        all_cogs = cog_manager.get_all_cog_files()
        actual_cog_name = cog_name

        # Try to match by class name first, then by file name
        for fname, cname in all_cogs.items():
            if cname == cog_name or fname == cog_name:
                actual_cog_name = cname
                break

        # Read log file
        log_file = os.path.join(os.getcwd(), "Logs", "HazeBot.log")

        if not os.path.exists(log_file):
            # Try alternative paths
            alternative_paths = [
                "Logs/HazeBot.log",
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "Logs", "HazeBot.log"),
                "/home/liq/gitProjects/HazeBot/Logs/HazeBot.log",
            ]

            for alt_path in alternative_paths:
                if os.path.exists(alt_path):
                    log_file = alt_path
                    break
            else:
                return jsonify({"error": "Log file not found"}), 404

        # Read last 1000 lines
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            lines = lines[-1000:]

        # Filter logs for this cog
        cog_filter = actual_cog_name.lower()
        filtered_logs = [line for line in lines if cog_filter in line.lower()]

        # Format logs for API response
        logs = []
        for log_line in filtered_logs[-100:]:  # Last 100 entries
            parts = log_line.strip().split(None, 3)
            if len(parts) >= 4:
                timestamp = parts[0]
                level = parts[1].strip("[]")
                cog = parts[2].strip("[]")
                message = parts[3] if len(parts) > 3 else ""

                logs.append(
                    {
                        "timestamp": timestamp,
                        "level": level,
                        "cog": cog,
                        "message": message,
                    }
                )

        return jsonify({"success": True, "cog": actual_cog_name, "logs": logs, "count": len(logs)})

    except Exception as e:
        logger.error(f"Error getting logs for cog {cog_name}: {e}")
        return jsonify({"error": f"Failed to get cog logs: {str(e)}"}), 500
