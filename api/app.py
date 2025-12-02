"""
Flask API for HazeBot Configuration
Modular REST API with Blueprint architecture
"""

import os
import sys
import threading
import types
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO

# Add parent directory to path to import Config
sys.path.insert(0, str(Path(__file__).parent.parent))
import Config

# Import cache system
from api.cache import cache
import api.cache as cache_module  # Also import module for admin routes
from Utils.ConfigLoader import load_config_from_file
from Utils.Logger import Logger as logger

# Import all Blueprint modules
import api.admin_routes as admin_routes_module
import api.analytics as analytics_module
import api.auth as auth_module
import api.auth_routes as auth_routes_module
import api.cog_routes as cog_routes_module
import api.config_routes as config_routes_module
import api.hazehub_cogs_routes as hazehub_cogs_routes_module
import api.helpers as helpers_module
import api.meme_routes as meme_routes_module
import api.notification_routes as notification_routes_module
import api.rocket_league_routes as rocket_league_routes_module
import api.ticket_routes as ticket_routes_module
import api.user_routes as user_routes_module

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for Flutter web
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent", logger=False, engineio_logger=False)

# Initialize analytics
analytics_file = Path(__file__).parent.parent / Config.DATA_DIR / "app_analytics.json"
analytics = analytics_module.AnalyticsAggregator(analytics_file)

# Initialize error tracking
import api.error_tracking as error_tracking_module
error_file = Path(__file__).parent.parent / Config.DATA_DIR / "error_analytics.json"
error_tracker = error_tracking_module.ErrorTracker(error_file)

# Thread lock for JWT decode (prevents race conditions)
jwt_decode_lock = threading.Lock()

# Active sessions tracking
active_sessions = {}  # {session_id: {username, discord_id, roles, last_seen, ip, user_agent}}

# Recent activity tracking (last 100 interactions)
recent_activity = []  # List of {timestamp, username, discord_id, action, endpoint, details}
MAX_ACTIVITY_LOG = 100

# App usage tracking file
app_usage_file = Path(__file__).parent.parent / Config.DATA_DIR / "app_usage.json"

# Negative emojis that should NOT count as upvotes
NEGATIVE_EMOJIS = {
    "👎",
    "😠",
    "😡",
    "🤬",
    "💩",
    "🖕",
    "❌",
    "⛔",
    "🚫",
    "💔",
    "😤",
    "😒",
    "🙄",
    "😑",
    "😐",
    "😶",
    "🤐",
    "😬",
}

# Secret key for JWT (should be in environment variable in production)
app.config["SECRET_KEY"] = os.getenv("API_SECRET_KEY", "dev-secret-key-change-in-production")


# ============================================================================
# BLUEPRINT INITIALIZATION
# ============================================================================

# Initialize helpers module (standalone - no Blueprint)
# This sets up global variables in helpers module
helpers_module.init_helpers(Config)

# Initialize auth module (standalone - no Blueprint)
# This sets up decorators and JWT handling
auth_module.init_auth(Config, app, active_sessions, recent_activity, MAX_ACTIVITY_LOG, app_usage_file, analytics)

# Create decorator functions that can be used by Blueprint modules
# These wrap the actual decorator implementations with initialized dependencies
token_required = auth_module.create_token_required_decorator()
require_permission = auth_module.require_permission
log_config_action = auth_module.log_config_action

# Create a simple object to pass decorators to Blueprint init functions
decorator_module = types.SimpleNamespace(
    token_required=token_required, require_permission=require_permission, log_config_action=log_config_action
)

# Initialize auth routes Blueprint
auth_routes_bp = auth_routes_module.init_auth_routes(
    app, Config, active_sessions, recent_activity, MAX_ACTIVITY_LOG, app_usage_file
)
app.register_blueprint(auth_routes_bp)

# Initialize config routes Blueprint
config_routes_module.init_config_routes(app, Config, logger, helpers_module, decorator_module)

# Initialize admin routes Blueprint
admin_routes_module.init_admin_routes(
    app, Config, logger, active_sessions, recent_activity, helpers_module, decorator_module, cache_module, analytics
)

# Initialize user routes Blueprint
user_routes_module.init_user_routes(app, Config, logger, cache, helpers_module, decorator_module)

# Initialize meme routes Blueprint
meme_routes_module.init_meme_routes(app, Config, logger, decorator_module)

# Initialize Rocket League routes Blueprint
rocket_league_routes_module.init_rocket_league_routes(app, Config, logger, decorator_module)

# Initialize HazeHub and Cogs routes Blueprint
hazehub_cogs_routes_module.init_hazehub_cogs_routes(app, Config, logger, cache, decorator_module, helpers_module)

# Initialize Cog Management routes Blueprint
cog_routes_module.init_cog_routes(app, logger, decorator_module)

# Initialize notification routes Blueprint (includes WebSocket handlers)
notification_routes_module.init_notification_routes(app, Config, logger, socketio, jwt_decode_lock)

# Register WebSocket handlers from notification module
notification_routes_module.register_socketio_handlers(socketio)

# Initialize ticket routes Blueprint (last - depends on notification handlers)
websocket_handlers = {"notify_ticket_update": notification_routes_module.notify_ticket_update}
notification_handlers = {
    "send_push_notification_for_ticket_event": notification_routes_module.send_push_notification_for_ticket_event
}
ticket_routes_module.init_ticket_routes(
    app, Config, logger, decorator_module, helpers_module, notification_handlers, websocket_handlers
)


# ============================================================================
# GLOBAL ERROR HANDLERS
# ============================================================================


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    """Handle 405 errors"""
    return jsonify({"error": "Method not allowed"}), 405


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {e}")
    # Track error
    try:
        error_tracking_module.track_api_error(
            error_tracker=error_tracker,
            exception=e,
            endpoint="unknown",
            request_data={"error_type": "500_internal_error"}
        )
    except Exception as track_error:
        logger.error(f"Failed to track error: {track_error}")
    return jsonify({"error": "Internal server error"}), 500


@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler - catches all unhandled exceptions"""
    logger.error(f"Unhandled exception: {e}", exc_info=True)
    
    # Track error
    try:
        from flask import request
        endpoint = request.endpoint or "unknown"
        user_id = getattr(request, 'discord_id', None)
        username = getattr(request, 'username', None)
        
        error_tracking_module.track_api_error(
            error_tracker=error_tracker,
            exception=e,
            endpoint=endpoint,
            user_id=user_id,
            username=username,
            request_data={
                "method": request.method,
                "url": request.url,
                "remote_addr": request.remote_addr
            }
        )
    except Exception as track_error:
        logger.error(f"Failed to track error: {track_error}")
    
    # Return user-friendly error message
    return jsonify({
        "error": "An unexpected error occurred",
        "message": str(e),
        "type": type(e).__name__
    }), 500


# ============================================================================
# BOT INSTANCE MANAGEMENT
# ============================================================================


def set_bot_instance(bot):
    """Set the bot instance for the API to use"""
    app.config["bot_instance"] = bot
    # Also store in Config for access from async contexts (like push notifications)
    Config.bot = bot


# ============================================================================
# SESSION CLEANUP TASK (runs periodically to remove stale sessions)
# ============================================================================


def cleanup_stale_sessions():
    """Remove sessions that haven't been seen in 10 minutes"""
    global active_sessions

    current_time = Config.get_utc_now()
    stale_session_ids = []

    for session_id, session_info in active_sessions.items():
        try:
            last_seen = datetime.fromisoformat(session_info["last_seen"])
            time_diff = (current_time - last_seen).total_seconds()

            # Remove sessions inactive for more than 10 minutes
            if time_diff > 600:  # 10 minutes in seconds
                stale_session_ids.append(session_id)
        except (ValueError, TypeError, KeyError):
            # Invalid timestamp or missing key, mark for removal
            stale_session_ids.append(session_id)

    # Remove stale sessions
    for session_id in stale_session_ids:
        del active_sessions[session_id]

    if stale_session_ids:
        logger.debug(f"🧹 Cleaned up {len(stale_session_ids)} stale sessions")


# ============================================================================
# ERROR ANALYTICS ENDPOINT
# ============================================================================

@app.route("/api/analytics/errors", methods=["GET"])
def get_error_analytics():
    """Get error analytics summary"""
    try:
        from flask import request
        days = int(request.args.get("days", 7))
        summary = error_tracker.get_error_summary(days=days)
        return jsonify(summary), 200
    except Exception as e:
        logger.error(f"Failed to get error analytics: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# STARTUP INITIALIZATION
# ============================================================================

if __name__ == "__main__":
    # Load any saved configuration on startup
    load_config_from_file()

    # Initialize Firebase Cloud Messaging (optional)
    try:
        from Utils.notification_service import initialize_firebase

        firebase_initialized = initialize_firebase()
        if firebase_initialized:
            print("✅ Firebase Cloud Messaging initialized")
        else:
            print("⚠️  Firebase Cloud Messaging not available (push notifications disabled)")
    except Exception as e:
        print(f"⚠️  Failed to initialize Firebase: {e}")
        print("   Push notifications will be disabled")

    # Get port from environment or use default
    port = int(os.getenv("API_PORT", 5000))

    # Check if we're in debug mode (only for development)
    debug_mode = os.getenv("API_DEBUG", "false").lower() == "true"

    if debug_mode:
        print("⚠️  WARNING: Running in DEBUG mode. This should NEVER be used in production!")

    print("=" * 70)
    print("🚀 HazeBot Configuration API")
    print("=" * 70)
    print(f"📡 Server: http://0.0.0.0:{port}")
    print(f"🔌 WebSocket: ws://localhost:{port}/socket.io/")
    print(f"📚 Health Check: http://localhost:{port}/api/health")
    print(f"🔧 Debug Mode: {'ENABLED' if debug_mode else 'DISABLED'}")
    print("=" * 70)
    print("\n📦 Registered Blueprints:")
    print("  ✓ Authentication (auth_routes)")
    print("  ✓ Configuration (config_routes)")
    print("  ✓ Administration (admin_routes)")
    print("  ✓ User Management (user_routes)")
    print("  ✓ Meme Generation (meme_routes)")
    print("  ✓ Rocket League (rocket_league_routes)")
    print("  ✓ Ticket System (ticket_routes)")
    print("  ✓ HazeHub & Cogs (hazehub_cogs_routes)")
    print("  ✓ Notifications & WebSockets (notification_routes)")
    print("=" * 70)
    print("\n🎯 Starting server...\n")

    # Schedule session cleanup every 5 minutes
    from threading import Timer

    def periodic_cleanup():
        cleanup_stale_sessions()
        # Reschedule next cleanup
        Timer(300.0, periodic_cleanup).start()

    # Start first cleanup after 5 minutes
    Timer(300.0, periodic_cleanup).start()

    # Use socketio.run instead of app.run for WebSocket support
    socketio.run(app, host="0.0.0.0", port=port, debug=debug_mode)
