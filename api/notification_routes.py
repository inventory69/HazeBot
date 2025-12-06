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

# Track which users are actively viewing which tickets (to suppress push notifications)
# Format: {"ticket_id": set(user_discord_ids)}
active_ticket_viewers = {}

# Track which WebSocket client (SID) is viewing which user_id
# Format: {"client_sid": "user_discord_id"}
# This allows auto-cleanup when client disconnects without sending leave_ticket
client_to_user = {}

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
        logger.debug(f"🔌 WebSocket client connected: {request.sid}")
        emit("connected", {"message": "Connected to HazeBot API"})

    @socketio.on("disconnect")
    def handle_disconnect():
        """Handle WebSocket disconnection"""
        client_sid = request.sid
        logger.debug(f"🔌 WebSocket client disconnected: {client_sid}")

        # ✅ CRITICAL: Auto-cleanup - remove user from all active_ticket_viewers
        # This handles cases where client disconnects without sending leave_ticket
        user_id = client_to_user.get(client_sid)
        if user_id:
            logger.debug(
                f"🧹 Auto-cleanup: Removing user {user_id} from active viewers (client {client_sid} disconnected)"
            )

            # Remove user from all tickets they were viewing
            tickets_to_clean = []
            for ticket_id, viewers in active_ticket_viewers.items():
                if user_id in viewers:
                    viewers.discard(user_id)
                    tickets_to_clean.append(ticket_id)
                    logger.debug(f"📱 Removed user {user_id} from ticket {ticket_id} active viewers")

            # Clean up empty sets
            for ticket_id in tickets_to_clean:
                if not active_ticket_viewers[ticket_id]:
                    del active_ticket_viewers[ticket_id]
                    logger.debug(f"📱 Removed empty viewer set for ticket {ticket_id}")

            # Remove client-to-user mapping
            del client_to_user[client_sid]

            if tickets_to_clean:
                logger.debug(f"✅ Auto-cleanup complete: User {user_id} removed from {len(tickets_to_clean)} ticket(s)")

    @socketio.on("join_ticket")
    def handle_join_ticket(data):
        """Join a ticket room to receive real-time updates"""
        ticket_id = data.get("ticket_id")
        user_id = data.get("user_id")  # ✅ NEW: Get user_id to track active viewers

        if not ticket_id:
            emit("error", {"message": "ticket_id required"})
            return

        room = f"ticket_{ticket_id}"
        join_room(room)

        # ✅ Track this user as actively viewing the ticket (suppress push notifications)
        if user_id:
            if ticket_id not in active_ticket_viewers:
                active_ticket_viewers[ticket_id] = set()
            active_ticket_viewers[ticket_id].add(str(user_id))

            # ✅ Track client-to-user mapping for auto-cleanup on disconnect
            client_to_user[request.sid] = str(user_id)

            logger.debug(f"🎫 JOIN | Client: {request.sid} | User: {user_id} | Room: {room} | Active viewers: {len(active_ticket_viewers[ticket_id])}")
        else:
            logger.debug(f"🎫 JOIN | Client: {request.sid} | Room: {room} | No user_id provided")

        # ✅ FIX: Check cache first before fetching from Discord
        from Utils.CacheUtils import cache_instance as cache
        
        cache_key = f"ticket:messages:{ticket_id}"
        cached_messages = cache.get(cache_key)
        
        if cached_messages is not None:
            logger.debug(f"✅ Serving {len(cached_messages)} message(s) from cache (WebSocket join_ticket)")
            emit("message_history", {"ticket_id": ticket_id, "messages": cached_messages})
            return

        # Send recent message history to newly joined client (only on cache miss)
        try:
            from flask import current_app
            from Cogs.TicketSystem import load_tickets, ADMIN_ROLE_ID, MODERATOR_ROLE_ID
            import asyncio

            bot = current_app.config.get("bot_instance")
            if bot:

                async def fetch_recent_messages():
                    tickets = await load_tickets()
                    ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)

                    if not ticket:
                        return []

                    channel_id = ticket.get("channel_id")
                    channel = bot.get_channel(channel_id)

                    if not channel:
                        return []

                    messages = []
                    total_fetched = 0
                    total_filtered = 0
                    async for message in channel.history(limit=100, oldest_first=False):
                        total_fetched += 1

                        # Skip bot system messages except important ones
                        if message.author.bot:
                            # Check if it's a user message from app (has [username]: prefix)
                            is_user_message_from_app = (
                                message.content.startswith("**[")
                                and not message.content.startswith("**[Admin Panel")
                                and "]:**" in message.content
                            )

                            # Keep important bot messages
                            if not (
                                message.content.startswith("**Initial details")
                                or message.content.startswith("**Subject:")  # API-created tickets
                                or message.content.startswith("**[Admin Panel")
                                or is_user_message_from_app  # User messages from app
                                or "Ticket successfully closed" in message.content
                                or "Ticket claimed by" in message.content
                                or "Ticket assigned to" in message.content
                                or "Ticket has been reopened" in message.content
                            ):
                                total_filtered += 1
                                logger.debug(f"🔇 Filtered bot message: {message.content[:50]}...")
                                continue

                        # Get avatar URL
                        avatar_url = None
                        is_admin = False
                        user_role = None

                        # Check if author has admin or moderator role
                        if hasattr(message.author, "roles") and message.author.roles:
                            for role in message.author.roles:
                                if role.id == ADMIN_ROLE_ID:
                                    is_admin = True
                                    user_role = "admin"
                                    break
                                elif role.id == MODERATOR_ROLE_ID:
                                    is_admin = True
                                    user_role = "moderator"
                                    break

                        if message.content.startswith("**[Admin Panel"):
                            is_admin = True

                        try:
                            if message.author.display_avatar:
                                avatar_url = str(message.author.display_avatar.url)
                            elif message.author.avatar:
                                avatar_url = str(message.author.avatar.url)
                        except Exception:
                            pass

                        messages.append(
                            {
                                "id": str(message.id),
                                "author_id": str(message.author.id),
                                "author_name": message.author.name,
                                "author_avatar": avatar_url,
                                "content": message.content,
                                "timestamp": message.created_at.isoformat(),
                                "is_bot": message.author.bot,
                                "is_admin": is_admin,
                                "role": user_role,
                            }
                        )

                    # Reverse to get oldest first
                    messages.reverse()
                    logger.debug(
                        f"📊 Message history: fetched={total_fetched}, filtered={total_filtered}, sent={len(messages)}"
                    )
                    return messages

                loop = bot.loop
                future = asyncio.run_coroutine_threadsafe(fetch_recent_messages(), loop)
                messages = future.result(timeout=10)

                # ✅ FIX: Cache messages after fetching from Discord
                from Utils.CacheUtils import cache_instance as cache
                cache_key = f"ticket:messages:{ticket_id}"
                cache.set(cache_key, messages, ttl_seconds=300)  # 5 minutes
                logger.info(f"💾 Cached {len(messages)} message(s) for ticket {ticket_id} (300s TTL)")

                emit("message_history", {"ticket_id": ticket_id, "messages": messages})
                logger.debug(f"📨 Sent {len(messages)} message(s) history to client {request.sid}")
        except Exception as e:
            logger.error(f"Failed to fetch message history: {e}")

        emit("joined_ticket", {"ticket_id": ticket_id, "room": room})

    @socketio.on("leave_ticket")
    def handle_leave_ticket(data):
        """Leave a ticket room"""
        ticket_id = data.get("ticket_id")
        user_id = data.get("user_id")  # ✅ NEW: Get user_id to remove from active viewers

        if not ticket_id:
            return

        room = f"ticket_{ticket_id}"
        leave_room(room)

        # ✅ Remove user from active viewers (re-enable push notifications)
        if user_id and ticket_id in active_ticket_viewers:
            active_ticket_viewers[ticket_id].discard(str(user_id))
            # Clean up empty sets
            if not active_ticket_viewers[ticket_id]:
                del active_ticket_viewers[ticket_id]
            logger.debug(f"🚪 LEAVE | Client: {request.sid} | User: {user_id} | Room: {room} | Remaining viewers: {len(active_ticket_viewers.get(ticket_id, set()))}")
        else:
            logger.debug(f"🚪 LEAVE | Client: {request.sid} | Room: {room}")

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
    
    payload = {"ticket_id": ticket_id, "event_type": event_type, "data": data, "timestamp": datetime.utcnow().isoformat()}
    logger.debug(f"🔌 WebSocket EMIT | Room: {room} | Event: {event_type}")
    
    socketio.emit(
        "ticket_update",
        payload,
        room=room,
    )
    
    logger.debug(f"✅ WebSocket EMITTED | Room: {room} | Event: {event_type}")


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

        logger.debug(f"📱 Initial notification recipients: {recipients}")

        # ✅ Filter out users who are actively viewing the ticket via WebSocket
        # These users see real-time updates and don't need push notifications
        if ticket_id in active_ticket_viewers:
            active_viewers = active_ticket_viewers[ticket_id]
            original_count = len(recipients)
            recipients = [uid for uid in recipients if uid not in active_viewers]
            filtered_count = original_count - len(recipients)
            if filtered_count > 0:
                logger.debug(
                    f"📱 Filtered out {filtered_count} active viewer(s) from push recipients for ticket {ticket_id}"
                )
                logger.debug(f"📱 Active viewers: {active_viewers}, Final recipients: {recipients}")
        else:
            logger.debug(f"📱 No active viewers for ticket {ticket_id}, sending to all recipients")

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
                logger.debug(f"📱 Sent push notification to user {user_id} for {event_type}")
            except Exception as e:
                logger.warning(f"Failed to send push notification to user {user_id}: {e}")

    except Exception as e:
        logger.error(f"Error in send_push_notification_for_ticket_event: {e}\n{traceback.format_exc()}")
