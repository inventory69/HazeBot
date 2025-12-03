"""
Notification and WebSocket Routes
Handles /api/notifications/* endpoints and SocketIO events
"""

import traceback
from datetime import datetime

import jwt
from flask import Blueprint, jsonify, request
from flask_socketio import emit, join_room, leave_room

# Will be initialized by init_notification_routes()
Config = None
logger = None
socketio = None
jwt_decode_lock = None


# Create Blueprint
notification_bp = Blueprint("notifications", __name__)


def init_notification_routes(app, config, log, socketio_instance, jwt_lock):
    """Initialize Notification routes Blueprint with dependencies"""
    global Config, logger, socketio, jwt_decode_lock

    Config = config
    logger = log
    socketio = socketio_instance
    jwt_decode_lock = jwt_lock

    # Register blueprint
    app.register_blueprint(notification_bp)


# ==================================
# Notification Endpoints
# ==================================


@notification_bp.route("/api/notifications/register", methods=["POST"])
async def notification_register_endpoint():
    """Register FCM token for push notifications"""
    try:
        from flask import current_app

        from Utils.notification_service import is_fcm_enabled, register_token

        if not is_fcm_enabled():
            return jsonify({"error": "Push notifications are not enabled on this server"}), 503

        token_data = request.get_json()
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        jwt_token = auth_header.split(" ")[1]

        # Decode JWT to get user info
        try:
            with jwt_decode_lock:
                decoded = jwt.decode(jwt_token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            user_id = decoded.get("discord_id") or decoded.get("user_id")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        fcm_token = token_data.get("fcm_token")
        device_info = token_data.get("device_info")

        if not fcm_token:
            return jsonify({"error": "fcm_token is required"}), 400

        # Register token
        success = await register_token(user_id, fcm_token, device_info)

        if success:
            return jsonify({"message": "Token registered successfully"}), 200
        else:
            return jsonify({"error": "Failed to register token"}), 500

    except Exception as e:
        logger.error(f"Error registering FCM token: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to register token: {str(e)}"}), 500


@notification_bp.route("/api/notifications/unregister", methods=["POST"])
async def notification_unregister_endpoint():
    """Unregister FCM token"""
    try:
        from flask import current_app

        from Utils.notification_service import is_fcm_enabled, unregister_token

        if not is_fcm_enabled():
            return jsonify({"error": "Push notifications are not enabled on this server"}), 503

        token_data = request.get_json()
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        jwt_token = auth_header.split(" ")[1]

        # Decode JWT to get user info
        try:
            with jwt_decode_lock:
                decoded = jwt.decode(jwt_token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            user_id = decoded.get("discord_id") or decoded.get("user_id")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        fcm_token = token_data.get("fcm_token")

        if not fcm_token:
            return jsonify({"error": "fcm_token is required"}), 400

        # Unregister token
        success = await unregister_token(user_id, fcm_token)

        if success:
            return jsonify({"message": "Token unregistered successfully"}), 200
        else:
            return jsonify({"error": "Token not found"}), 404

    except Exception as e:
        logger.error(f"Error unregistering FCM token: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to unregister token: {str(e)}"}), 500


@notification_bp.route("/api/notifications/settings", methods=["GET"])
async def notification_settings_get_endpoint():
    """Get notification settings for authenticated user"""
    try:
        from flask import current_app

        from Utils.notification_service import get_user_notification_settings

        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        jwt_token = auth_header.split(" ")[1]

        # Decode JWT to get user info
        try:
            with jwt_decode_lock:
                decoded = jwt.decode(jwt_token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            user_id = decoded.get("discord_id") or decoded.get("user_id")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        # Get user settings
        settings = await get_user_notification_settings(user_id)

        return jsonify(settings), 200

    except Exception as e:
        logger.error(f"Error getting notification settings: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to get settings: {str(e)}"}), 500


@notification_bp.route("/api/notifications/settings", methods=["PUT"])
async def notification_settings_update_endpoint():
    """Update notification settings for authenticated user"""
    try:
        from flask import current_app

        from Utils.notification_service import update_user_notification_settings

        settings_data = request.get_json()
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        jwt_token = auth_header.split(" ")[1]

        # Decode JWT to get user info
        try:
            with jwt_decode_lock:
                decoded = jwt.decode(jwt_token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            user_id = decoded.get("discord_id") or decoded.get("user_id")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        # Validate settings
        valid_settings = {
            "ticket_new_messages",
            "ticket_mentions",
            "ticket_created",
            "ticket_assigned",
        }

        # Filter invalid settings
        filtered_settings = {k: v for k, v in settings_data.items() if k in valid_settings}

        if not filtered_settings:
            return jsonify({"error": "No valid settings provided"}), 400

        # Update settings
        success = await update_user_notification_settings(user_id, filtered_settings)

        if success:
            return jsonify({"message": "Settings updated successfully"}), 200
        else:
            return jsonify({"error": "Failed to update settings"}), 500

    except Exception as e:
        logger.error(f"Error updating notification settings: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to update settings: {str(e)}"}), 500


# ==================================
# WebSocket Event Handlers
# ==================================


def register_socketio_handlers(socketio_instance):
    """Register SocketIO event handlers"""
    global socketio
    socketio = socketio_instance

    @socketio.on("connect")
    def handle_connect():
        """Handle WebSocket connection"""
        logger.info(f"🔌 WebSocket client connected: {request.sid}")
        emit("connected", {"message": "Connected to HazeBot API"})

    @socketio.on("disconnect")
    def handle_disconnect():
        """Handle WebSocket disconnection"""
        logger.info(f"🔌 WebSocket client disconnected: {request.sid}")

    @socketio.on("join_ticket")
    def handle_join_ticket(data):
        """Join a ticket room to receive real-time updates"""
        ticket_id = data.get("ticket_id")
        if not ticket_id:
            emit("error", {"message": "ticket_id required"})
            return

        room = f"ticket_{ticket_id}"
        join_room(room)
        logger.info(f"🎫 Client {request.sid} joined ticket room: {room}")
        emit("joined_ticket", {"ticket_id": ticket_id, "room": room})

    @socketio.on("leave_ticket")
    def handle_leave_ticket(data):
        """Leave a ticket room"""
        ticket_id = data.get("ticket_id")
        if not ticket_id:
            return

        room = f"ticket_{ticket_id}"
        leave_room(room)
        logger.info(f"🎫 Client {request.sid} left ticket room: {room}")
        emit("left_ticket", {"ticket_id": ticket_id, "room": room})


def notify_ticket_update(ticket_id, event_type, data):
    """
    Notify all clients in a ticket room about an update via WebSocket

    Args:
        ticket_id: Ticket ID
        event_type: Type of event (new_message, status_change, etc.)
        data: Event data
    """
    room = f"ticket_{ticket_id}"
    socketio.emit(
        "ticket_update",
        {"ticket_id": ticket_id, "event_type": event_type, "data": data, "timestamp": datetime.utcnow().isoformat()},
        room=room,
    )
    logger.info(f"📡 Broadcast to {room}: {event_type}")


def clean_admin_panel_prefix(content):
    """
    Remove admin panel formatting from message content for notifications

    Transforms:
        Input:  "**[Admin Panel - wutangwilli]:** Die Nachricht hier"
        Output: "wutangwilli: Die Nachricht hier"

    If no admin panel prefix is found, returns the original content.
    """
    import re

    # Pattern matches: **[Admin Panel - username]:** (with optional whitespace after)
    pattern = r"\*\*\[Admin Panel - ([^\]]+)\]:\*\*\s*"
    match = re.match(pattern, content)

    if match:
        username = match.group(1)
        message = content[match.end() :]
        return f"{username}: {message}"

    # No admin panel prefix found - return original
    return content


async def send_push_notification_for_ticket_event(ticket_id, event_type, ticket_data, message_data=None):
    """
    Send push notifications for ticket events

    Args:
        ticket_id: Ticket ID
        event_type: Type of event (new_ticket, new_message, ticket_assigned, etc.)
        ticket_data: Ticket data
        message_data: Optional message data (for new_message events)
    """
    try:
        from Utils.notification_service import is_fcm_enabled, send_notification

        if not is_fcm_enabled():
            return

        # Access bot instance from Config (set by set_bot_instance in api/app.py)
        # This works in async contexts without needing Flask app context
        bot = getattr(Config, "bot", None)
        if not bot:
            return

        guild = bot.get_guild(Config.GUILD_ID)
        if not guild:
            return

        # Determine who to notify based on event type
        recipients = []

        if event_type == "new_ticket":
            # Notify all admins/mods about new ticket
            from Cogs.TicketSystem import ADMIN_ROLE_ID, MODERATOR_ROLE_ID

            admin_role = guild.get_role(ADMIN_ROLE_ID)
            mod_role = guild.get_role(MODERATOR_ROLE_ID)

            if admin_role:
                recipients.extend([str(member.id) for member in admin_role.members])
            if mod_role:
                recipients.extend([str(member.id) for member in mod_role.members])

            title = f"New Ticket #{ticket_data.get('ticket_num')}"

            # Build body with initial message if available
            user_name = ticket_data.get("user_name", "A user")
            ticket_type = ticket_data.get("type", "Support")
            initial_message = ticket_data.get("initial_message")

            if initial_message:
                # Show preview of initial message (first 80 chars)
                message_preview = initial_message[:80]
                if len(initial_message) > 80:
                    message_preview += "..."
                body = f"{user_name} created a new {ticket_type} ticket: {message_preview}"
            else:
                body = f"{user_name} created a new {ticket_type} ticket"

        elif event_type == "new_message":
            # Notification logic:
            # 1. Always notify ticket creator (unless they sent the message)
            # 2. If ticket is claimed: notify only the claimer (unless they sent the message)
            # 3. If ticket is NOT claimed: notify all admins/mods (except message sender)

            user_id = ticket_data.get("user_id")
            assigned_to = ticket_data.get("assigned_to")

            # Don't notify the message sender
            message_author_id = message_data.get("author_id") if message_data else None

            # Always notify ticket creator (unless they sent the message)
            if user_id and str(user_id) != str(message_author_id):
                recipients.append(str(user_id))
                logger.debug(f"📱 Adding ticket creator {user_id} to notification recipients")

            # Check if ticket is claimed (assigned_to is set)
            if assigned_to:
                # Ticket is claimed: notify only the claimer
                if str(assigned_to) != str(message_author_id):
                    recipients.append(str(assigned_to))
                    logger.debug(f"📱 Ticket claimed: Adding claimer {assigned_to} to notification recipients")
            else:
                # Ticket is NOT claimed: notify all admins/mods
                from Cogs.TicketSystem import ADMIN_ROLE_ID, MODERATOR_ROLE_ID

                admin_role = guild.get_role(ADMIN_ROLE_ID)
                mod_role = guild.get_role(MODERATOR_ROLE_ID)

                if admin_role:
                    for member in admin_role.members:
                        if str(member.id) != str(message_author_id):
                            recipients.append(str(member.id))
                    logger.debug(f"📱 Ticket not claimed: Added {len(admin_role.members)} admins to recipients")

                if mod_role:
                    for member in mod_role.members:
                        if str(member.id) != str(message_author_id):
                            recipients.append(str(member.id))
                    logger.debug(f"📱 Ticket not claimed: Added {len(mod_role.members)} mods to recipients")

            title = f"New Message in Ticket #{ticket_data.get('ticket_num')}"
            if message_data:
                # ✅ Clean admin panel formatting from content for notifications
                raw_content = message_data.get("content", "")
                cleaned_content = clean_admin_panel_prefix(raw_content)
                content_preview = cleaned_content[:100]

                # If content already has username prefix (from cleaning), use it directly
                # Otherwise, add author name
                if cleaned_content.startswith(message_data.get("author_name", "") + ":"):
                    body = content_preview
                else:
                    author_name = message_data.get("author_name", "Someone")
                    body = f"{author_name}: {content_preview}"
            else:
                body = "You have a new message"

        elif event_type == "ticket_assigned":
            # Notify the assigned user
            assigned_to = ticket_data.get("assigned_to")
            if assigned_to:
                recipients.append(str(assigned_to))

            title = f"Ticket #{ticket_data.get('ticket_num')} Assigned"
            body = "A ticket has been assigned to you"

        else:
            # Unknown event type
            return

        # Remove duplicates
        recipients = list(set(recipients))

        # Send notification to each recipient
        for user_id in recipients:
            try:
                await send_notification(
                    user_id,
                    title,
                    body,
                    data={
                        "ticket_id": ticket_id,
                        "ticket_num": str(ticket_data.get("ticket_num", "")),
                        "event_type": event_type,
                        "click_action": "FLUTTER_NOTIFICATION_CLICK",
                        "route": f"/tickets/{ticket_id}",
                    },
                )
                logger.info(f"📱 Sent push notification to user {user_id} for {event_type}")
            except Exception as e:
                logger.warning(f"Failed to send push notification to user {user_id}: {e}")

    except Exception as e:
        logger.error(f"Error in send_push_notification_for_ticket_event: {e}\n{traceback.format_exc()}")
