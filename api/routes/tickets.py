"""
Ticket and notification routes.
"""

import asyncio
import json
import os
import re
import traceback
from datetime import datetime
from pathlib import Path

import jwt
from flask import Blueprint, current_app, jsonify, request

import Config
from Utils.Logger import Logger as logger
from api.utils.audit import log_action, log_config_action
from api.utils.auth import require_permission, token_required

tickets_bp = Blueprint("tickets", __name__)


def _get_bot():
    return current_app.config.get("bot_instance")


def _get_socketio():
    # SocketIO instance stored by Flask-SocketIO in extensions
    return current_app.extensions.get("socketio")


async def send_push_notification_for_ticket_event(ticket_id, event_type, ticket_data, message_data=None):
    """
    Send push notifications for ticket events

    Args:
        ticket_id: Ticket ID
        event_type: Type of event (new_ticket, new_message, ticket_assigned, etc.)
        ticket_data: Ticket data dictionary
        message_data: Optional message data for new_message events
    """
    try:
        from Utils.notification_service import (
            is_fcm_enabled,
            send_notification,
            send_notification_to_multiple_users,
        )

        if not is_fcm_enabled():
            return

        notify_user_ids = []
        notification_type = None
        title = ""
        body = ""

        if event_type == "new_ticket":
            notification_type = "ticket_created"
            title = f"🎫 New Ticket #{ticket_data.get('ticket_num', '?')}"
            body = f"{ticket_data.get('user_name', 'Someone')} created a new ticket"

            bot = _get_bot()
            if bot:
                guild = bot.get_guild(Config.GUILD_ID)
                if guild:
                    admin_role = guild.get_role(Config.ADMIN_ROLE_ID)
                    mod_role = guild.get_role(Config.MODERATOR_ROLE_ID)
                    if admin_role:
                        notify_user_ids.extend([str(member.id) for member in admin_role.members])
                    if mod_role:
                        notify_user_ids.extend([str(member.id) for member in mod_role.members])
                    notify_user_ids = list(set(notify_user_ids))

        elif event_type == "new_message":
            notification_type = "ticket_new_messages"

            if message_data:
                author_name = message_data.get("author_name", "Someone")
                content = message_data.get("content", "")
                title = f"💬 New message in Ticket #{ticket_data.get('ticket_num', '?')}"
                body = f"{author_name}: {content[:100]}"

                # Mentions in message -> send mention notifications
                mention_ids = re.findall(r"<@!?(\\d+)>", content)
                for mentioned_id in mention_ids:
                    if mentioned_id != str(message_data.get("author_id")):
                        await send_notification(
                            mentioned_id,
                            f"📢 You were mentioned in Ticket #{ticket_data.get('ticket_num', '?')}",
                            f"{author_name} mentioned you: {content[:100]}",
                            data={
                                "ticket_id": ticket_id,
                                "notification_type": "mention",
                                "ticket_num": str(ticket_data.get("ticket_num", "")),
                                "open_tab": "messages",
                            },
                            notification_type="ticket_mentions",
                        )

                author_id = str(message_data.get("author_id"))
                ticket_creator_id = str(ticket_data.get("user_id"))
                assigned_to = ticket_data.get("assigned_to")
                claimed_by = ticket_data.get("claimed_by")

                if author_id == ticket_creator_id:
                    if assigned_to:
                        notify_user_ids = [str(assigned_to)]
                    elif claimed_by:
                        notify_user_ids = [str(claimed_by)]
                else:
                    notify_user_ids = [ticket_creator_id]

                notify_user_ids = [uid for uid in notify_user_ids if uid != author_id]

        elif event_type == "ticket_assigned":
            notification_type = "ticket_assigned"
            assigned_to = ticket_data.get("assigned_to")
            if assigned_to:
                title = f"📌 Ticket #{ticket_data.get('ticket_num', '?')} assigned to you"
                body = "You have been assigned to handle this ticket"
                notify_user_ids = [str(assigned_to)]

        if notify_user_ids and title and body:
            payload_data = {
                "ticket_id": ticket_id,
                "notification_type": event_type,
                "ticket_num": str(ticket_data.get("ticket_num", "")),
            }
            if notify_user_ids and ticket_data.get("user_id") and notify_user_ids[0] == str(ticket_data["user_id"]):
                payload_data["open_tab"] = "messages"

            if len(notify_user_ids) == 1:
                await send_notification(
                    notify_user_ids[0], title, body, data=payload_data, notification_type=notification_type
                )
            else:
                await send_notification_to_multiple_users(
                    notify_user_ids, title, body, data=payload_data, notification_type=notification_type
                )
    except Exception as e:
        logger.error(f"❌ Error sending push notification: {e}")
        logger.error(traceback.format_exc())


@tickets_bp.route("/api/tickets", methods=["GET"])
@token_required
@require_permission("all")
def get_tickets():
    """Get all tickets with optional filters"""
    try:
        import asyncio
        from Cogs.TicketSystem import load_tickets

        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        ticket_cog = bot.get_cog("TicketSystem")
        if not ticket_cog:
            return jsonify({"error": "TicketSystem cog not loaded"}), 503

        # Always load from storage to avoid relying on an attribute that may not exist
        loop = bot.loop
        tickets_data_list = asyncio.run_coroutine_threadsafe(load_tickets(), loop).result(timeout=10)

        # Convert list to dict keyed by ticket_id if needed
        tickets_data = {t.get("ticket_id") or str(t.get("channel_id")): t for t in tickets_data_list}

        status_filter = request.args.get("status")
        type_filter = request.args.get("type")
        claimed_by_filter = request.args.get("claimed_by")
        assigned_to_filter = request.args.get("assigned_to")

        if status_filter:
            tickets_data = {k: v for k, v in tickets_data.items() if v.get("status") == status_filter}
        if type_filter:
            tickets_data = {k: v for k, v in tickets_data.items() if v.get("type") == type_filter}
        if claimed_by_filter:
            tickets_data = {k: v for k, v in tickets_data.items() if str(v.get("claimed_by")) == claimed_by_filter}
        if assigned_to_filter:
            tickets_data = {k: v for k, v in tickets_data.items() if str(v.get("assigned_to")) == assigned_to_filter}

        ticket_list = []
        for ticket_id, ticket_data in tickets_data.items():
            enriched = ticket_data.copy()
            enriched["ticket_id"] = ticket_id
            if "user_id" in enriched:
                enriched["user_id"] = str(enriched["user_id"])
            if "claimed_by" in enriched and enriched["claimed_by"]:
                enriched["claimed_by"] = str(enriched["claimed_by"])
            if "assigned_to" in enriched and enriched["assigned_to"]:
                enriched["assigned_to"] = str(enriched["assigned_to"])
            ticket_list.append(enriched)

        return jsonify({"tickets": ticket_list, "total": len(ticket_list)})
    except Exception as e:
        return jsonify({"error": f"Failed to fetch tickets: {str(e)}", "details": traceback.format_exc()}), 500


@tickets_bp.route("/api/tickets/my", methods=["GET"])
@token_required
def get_my_tickets():
    """Get tickets created by current user"""
    try:
        import asyncio
        from Cogs.TicketSystem import load_tickets

        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        ticket_cog = bot.get_cog("TicketSystem")
        if not ticket_cog:
            return jsonify({"error": "TicketSystem cog not loaded"}), 503

        loop = bot.loop
        tickets_data_list = asyncio.run_coroutine_threadsafe(load_tickets(), loop).result(timeout=10)
        tickets_data = {t.get("ticket_id") or str(t.get("channel_id")): t for t in tickets_data_list}
        user_id = str(request.discord_id)

        my_tickets = []
        for ticket_id, ticket_data in tickets_data.items():
            if str(ticket_data.get("user_id")) == user_id:
                enriched = ticket_data.copy()
                enriched["ticket_id"] = ticket_id
                my_tickets.append(enriched)

        return jsonify({"tickets": my_tickets, "total": len(my_tickets)})
    except Exception as e:
        return jsonify({"error": f"Failed to fetch user tickets: {str(e)}", "details": traceback.format_exc()}), 500


@tickets_bp.route("/api/tickets", methods=["POST"])
@token_required
@require_permission("all")
def create_ticket():
    """Create a new ticket"""
    try:
        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        ticket_cog = bot.get_cog("TicketSystem")
        if not ticket_cog:
            return jsonify({"error": "TicketSystem cog not loaded"}), 503

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = ["type", "user_id", "user_name", "channel_id", "message_id", "ticket_num"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

        ticket_id = str(data.get("ticket_id") or data.get("message_id"))
        ticket_cog.tickets_data[ticket_id] = data
        ticket_cog.save_tickets()

        return jsonify({"success": True, "ticket": data})
    except Exception as e:
        return jsonify({"error": f"Failed to create ticket: {str(e)}", "details": traceback.format_exc()}), 500


@tickets_bp.route("/api/tickets/<ticket_id>", methods=["GET"])
@token_required
def get_ticket(ticket_id):
    """Get a ticket by ID"""
    try:
        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        ticket_cog = bot.get_cog("TicketSystem")
        if not ticket_cog:
            return jsonify({"error": "TicketSystem cog not loaded"}), 503

        ticket_data = ticket_cog.tickets_data.get(ticket_id)
        if not ticket_data:
            return jsonify({"error": "Ticket not found"}), 404

        enriched = ticket_data.copy()
        enriched["ticket_id"] = ticket_id
        if "user_id" in enriched:
            enriched["user_id"] = str(enriched["user_id"])
        if "claimed_by" in enriched and enriched["claimed_by"]:
            enriched["claimed_by"] = str(enriched["claimed_by"])
        if "assigned_to" in enriched and enriched["assigned_to"]:
            enriched["assigned_to"] = str(enriched["assigned_to"])

        return jsonify(enriched)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch ticket: {str(e)}", "details": traceback.format_exc()}), 500


@tickets_bp.route("/api/tickets/<ticket_id>", methods=["PUT"])
@token_required
@require_permission("all")
def update_ticket(ticket_id):
    """Update a ticket"""
    try:
        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        ticket_cog = bot.get_cog("TicketSystem")
        if not ticket_cog:
            return jsonify({"error": "TicketSystem cog not loaded"}), 503

        if ticket_id not in ticket_cog.tickets_data:
            return jsonify({"error": "Ticket not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        ticket_cog.tickets_data[ticket_id].update(data)
        ticket_cog.save_tickets()

        return jsonify({"success": True, "ticket": ticket_cog.tickets_data[ticket_id]})
    except Exception as e:
        return jsonify({"error": f"Failed to update ticket: {str(e)}", "details": traceback.format_exc()}), 500


@tickets_bp.route("/api/tickets/<ticket_id>", methods=["DELETE"])
@token_required
@require_permission("all")
def delete_ticket(ticket_id):
    """Delete a ticket"""
    try:
        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        ticket_cog = bot.get_cog("TicketSystem")
        if not ticket_cog:
            return jsonify({"error": "TicketSystem cog not loaded"}), 503

        if ticket_id not in ticket_cog.tickets_data:
            return jsonify({"error": "Ticket not found"}), 404

        del ticket_cog.tickets_data[ticket_id]
        ticket_cog.save_tickets()

        return jsonify({"success": True, "message": "Ticket deleted"})
    except Exception as e:
        return jsonify({"error": f"Failed to delete ticket: {str(e)}", "details": traceback.format_exc()}), 500


def notify_ticket_update(ticket_id, event_type, data):
    """Emit ticket updates via WebSocket to subscribed clients."""
    socketio = _get_socketio()
    if not socketio:
        return
    room = f"ticket_{ticket_id}"
    socketio.emit(
        "ticket_update",
        {"ticket_id": ticket_id, "event_type": event_type, "data": data, "timestamp": datetime.utcnow().isoformat()},
        room=room,
    )


@tickets_bp.route("/api/tickets/<ticket_id>/messages", methods=["GET"])
@token_required
@require_permission("all")
def get_ticket_messages(ticket_id):
    """Get messages from a ticket channel (last 50)."""
    try:
        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        ticket_cog = bot.get_cog("TicketSystem")
        if not ticket_cog:
            return jsonify({"error": "TicketSystem cog not loaded"}), 503

        ticket = ticket_cog.tickets_data.get(ticket_id)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        channel = bot.get_channel(ticket.get("channel_id"))
        if not channel:
            return jsonify({"error": "Ticket channel not found"}), 404

        async def fetch_messages():
            messages = []
            async for message in channel.history(limit=50, oldest_first=False):
                if message.author.bot:
                    important = (
                        message.content.startswith("**[Admin Panel")
                        or "Ticket" in message.content
                        or "ticket" in message.content
                    )
                    if not important:
                        continue

                avatar_url = None
                try:
                    if message.author.display_avatar:
                        avatar_url = str(message.author.display_avatar.url)
                except Exception:
                    avatar_url = None

                messages.append(
                    {
                        "id": str(message.id),
                        "author_id": str(message.author.id),
                        "author_name": message.author.name,
                        "author_avatar": avatar_url,
                        "content": message.content,
                        "timestamp": message.created_at.isoformat(),
                        "is_bot": message.author.bot,
                    }
                )
            return list(reversed(messages))

        future = asyncio.run_coroutine_threadsafe(fetch_messages(), bot.loop)
        msgs = future.result(timeout=10)
        return jsonify({"messages": msgs})
    except Exception as e:
        logger.error(f"Error fetching ticket messages: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch messages: {str(e)}"}), 500


@tickets_bp.route("/api/tickets/<ticket_id>/messages", methods=["POST"])
@token_required
def send_ticket_message(ticket_id):
    """Send a message to a ticket channel."""
    try:
        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        ticket_cog = bot.get_cog("TicketSystem")
        if not ticket_cog:
            return jsonify({"error": "TicketSystem cog not loaded"}), 503

        ticket = ticket_cog.tickets_data.get(ticket_id)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        data = request.get_json() or {}
        message_content = data.get("content", "").strip()
        if not message_content:
            return jsonify({"error": "Message content required"}), 400

        discord_id = getattr(request, "discord_id", None)
        if not discord_id:
            return jsonify({"error": "User information not found"}), 401

        guild = bot.get_guild(Config.GUILD_ID)
        if not guild:
            return jsonify({"error": "Guild not found"}), 500

        member = guild.get_member(int(discord_id))
        if not member:
            return jsonify({"error": "User not found in guild"}), 404

        is_admin_or_mod = any(role.id in [Config.ADMIN_ROLE_ID, Config.MODERATOR_ROLE_ID] for role in member.roles)
        if not is_admin_or_mod and str(ticket.get("user_id")) != str(discord_id):
            return jsonify({"error": "You can only message your own tickets"}), 403

        channel = bot.get_channel(ticket.get("channel_id"))
        if not channel:
            return jsonify({"error": "Ticket channel not found"}), 404

        async def send_message():
            content = (
                f"**[Admin Panel - {request.username}]:** {message_content}"
                if is_admin_or_mod
                else message_content
            )
            msg = await channel.send(content)
            avatar_url = None
            try:
                if member.display_avatar:
                    avatar_url = str(member.display_avatar.url)
            except Exception:
                avatar_url = None

            return {
                "id": str(msg.id),
                "author_id": str(member.id),
                "author_name": member.name,
                "author_avatar": avatar_url,
                "content": content,
                "timestamp": msg.created_at.isoformat(),
                "is_bot": False,
            }

        future = asyncio.run_coroutine_threadsafe(send_message(), bot.loop)
        message_data = future.result(timeout=10)

        notify_ticket_update(ticket_id, "new_message", message_data)
        try:
            asyncio.run_coroutine_threadsafe(
                send_push_notification_for_ticket_event(ticket_id, "new_message", ticket, message_data),
                bot.loop,
            )
        except Exception:
            pass

        return jsonify({"success": True, "message": "Message sent successfully", "data": message_data})
    except Exception as e:
        logger.error(f"Error sending message to ticket {ticket_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to send message: {str(e)}"}), 500


@tickets_bp.route("/api/tickets/<ticket_id>/claim", methods=["POST"])
@token_required
@require_permission("all")
def claim_ticket(ticket_id):
    """Claim a ticket"""
    try:
        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        ticket_cog = bot.get_cog("TicketSystem")
        if not ticket_cog:
            return jsonify({"error": "TicketSystem cog not loaded"}), 503

        if ticket_id not in ticket_cog.tickets_data:
            return jsonify({"error": "Ticket not found"}), 404

        data = request.get_json()
        claimed_by = data.get("claimed_by")
        if not claimed_by:
            return jsonify({"error": "claimed_by is required"}), 400

        ticket_cog.tickets_data[ticket_id]["claimed_by"] = int(claimed_by)
        ticket_cog.tickets_data[ticket_id]["status"] = "Claimed"
        ticket_cog.save_tickets()

        notify_ticket_update(ticket_id, "status_change", {"status": "Claimed", "claimed_by": str(claimed_by)})
        try:
            asyncio.run_coroutine_threadsafe(
                send_push_notification_for_ticket_event(ticket_id, "ticket_assigned", ticket_cog.tickets_data[ticket_id]),
                bot.loop,
            )
        except Exception:
            pass

        return jsonify({"success": True, "message": "Ticket claimed"})
    except Exception as e:
        return jsonify({"error": f"Failed to claim ticket: {str(e)}", "details": traceback.format_exc()}), 500


@tickets_bp.route("/api/tickets/<ticket_id>/assign", methods=["POST"])
@token_required
@require_permission("all")
def assign_ticket(ticket_id):
    """Assign a ticket"""
    try:
        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        ticket_cog = bot.get_cog("TicketSystem")
        if not ticket_cog:
            return jsonify({"error": "TicketSystem cog not loaded"}), 503

        if ticket_id not in ticket_cog.tickets_data:
            return jsonify({"error": "Ticket not found"}), 404

        data = request.get_json()
        assigned_to = data.get("assigned_to")
        if not assigned_to:
            return jsonify({"error": "assigned_to is required"}), 400

        ticket_cog.tickets_data[ticket_id]["assigned_to"] = int(assigned_to)
        ticket_cog.save_tickets()

        notify_ticket_update(ticket_id, "status_change", {"assigned_to": str(assigned_to)})
        try:
            asyncio.run_coroutine_threadsafe(
                send_push_notification_for_ticket_event(ticket_id, "ticket_assigned", ticket_cog.tickets_data[ticket_id]),
                bot.loop,
            )
        except Exception:
            pass

        return jsonify({"success": True, "message": "Ticket assigned"})
    except Exception as e:
        return jsonify({"error": f"Failed to assign ticket: {str(e)}", "details": traceback.format_exc()}), 500


@tickets_bp.route("/api/tickets/<ticket_id>/close", methods=["POST"])
@token_required
@require_permission("all")
def close_ticket(ticket_id):
    """Close a ticket"""
    try:
        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        ticket_cog = bot.get_cog("TicketSystem")
        if not ticket_cog:
            return jsonify({"error": "TicketSystem cog not loaded"}), 503

        if ticket_id not in ticket_cog.tickets_data:
            return jsonify({"error": "Ticket not found"}), 404

        data = request.get_json() or {}
        close_message = data.get("close_message", "Ticket closed by admin.")

        ticket_cog.tickets_data[ticket_id]["status"] = "Closed"
        ticket_cog.tickets_data[ticket_id]["closed_at"] = Config.get_utc_now().isoformat()
        ticket_cog.tickets_data[ticket_id]["claimed_by"] = None
        ticket_cog.tickets_data[ticket_id]["assigned_to"] = None
        ticket_cog.save_tickets()

        # Send close message
        try:
            channel_id = int(ticket_cog.tickets_data[ticket_id].get("channel_id"))
            channel = bot.get_channel(channel_id)
            if channel:
                asyncio.run_coroutine_threadsafe(channel.send(close_message), bot.loop).result(timeout=5)
        except Exception:
            pass

        notify_ticket_update(ticket_id, "status_change", {"status": "Closed"})
        try:
            asyncio.run_coroutine_threadsafe(
                send_push_notification_for_ticket_event(ticket_id, "ticket_assigned", ticket_cog.tickets_data[ticket_id]),
                bot.loop,
            )
        except Exception:
            pass

        return jsonify({"success": True, "message": "Ticket closed"})
    except Exception as e:
        return jsonify({"error": f"Failed to close ticket: {str(e)}", "details": traceback.format_exc()}), 500


@tickets_bp.route("/api/tickets/<ticket_id>/reopen", methods=["POST"])
@token_required
@require_permission("all")
def reopen_ticket(ticket_id):
    """Reopen a ticket"""
    try:
        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        ticket_cog = bot.get_cog("TicketSystem")
        if not ticket_cog:
            return jsonify({"error": "TicketSystem cog not loaded"}), 503

        if ticket_id not in ticket_cog.tickets_data:
            return jsonify({"error": "Ticket not found"}), 404

        ticket_data = ticket_cog.tickets_data[ticket_id]
        reopen_count = ticket_data.get("reopen_count", 0)
        ticket_data["reopen_count"] = reopen_count + 1
        ticket_data["status"] = "Open"
        ticket_data["closed_at"] = None
        ticket_cog.save_tickets()

        notify_ticket_update(ticket_id, "status_change", {"status": "Open"})
        try:
            asyncio.run_coroutine_threadsafe(
                send_push_notification_for_ticket_event(ticket_id, "ticket_assigned", ticket_cog.tickets_data[ticket_id]),
                bot.loop,
            )
        except Exception:
            pass

        return jsonify({"success": True, "message": "Ticket reopened"})
    except Exception as e:
        return jsonify({"error": f"Failed to reopen ticket: {str(e)}", "details": traceback.format_exc()}), 500



@tickets_bp.route("/api/config/tickets", methods=["GET"])
@token_required
@require_permission("all")
def get_ticket_config():
    """Get ticket configuration"""
    try:
        config_file = Path(__file__).parent.parent.parent / Config.DATA_DIR / "tickets_config.json"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {
                "categories": ["Application", "Bug", "Support"],
                "auto_delete_after_close_days": 7,
                "require_claim": False,
                "send_transcript_email": False,
                "transcript_email_address": "",
            }
        return jsonify(config)
    except Exception as e:
        return jsonify({"error": f"Failed to get ticket config: {str(e)}"}), 500


@tickets_bp.route("/api/config/tickets", methods=["PUT"])
@token_required
@require_permission("all")
@log_config_action("ticket_config")
def update_ticket_config():
    """Update ticket configuration"""
    try:
        config_file = Path(__file__).parent.parent.parent / Config.DATA_DIR / "tickets_config.json"
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {}

        if "categories" in data:
            config["categories"] = data["categories"]
        if "auto_delete_after_close_days" in data:
            config["auto_delete_after_close_days"] = int(data["auto_delete_after_close_days"])
        if "require_claim" in data:
            config["require_claim"] = bool(data["require_claim"])
        if "send_transcript_email" in data:
            config["send_transcript_email"] = bool(data["send_transcript_email"])
        if "transcript_email_address" in data:
            config["transcript_email_address"] = data["transcript_email_address"]

        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        log_action(request.username, "update_ticket_config", {"keys_modified": list(data.keys())})
        return jsonify({"success": True, "message": "Ticket configuration updated successfully"})
    except Exception as e:
        return jsonify({"error": f"Failed to update ticket config: {str(e)}", "details": traceback.format_exc()}), 500


@tickets_bp.route("/api/config/tickets/reset", methods=["POST"])
@token_required
@require_permission("all")
def reset_ticket_config():
    """Reset ticket configuration to defaults"""
    try:
        config_file = Path(__file__).parent.parent.parent / Config.DATA_DIR / "tickets_config.json"
        support_email = os.getenv("SUPPORT_EMAIL", "")
        default_config = {
            "categories": ["Application", "Bug", "Support"],
            "auto_delete_after_close_days": 7,
            "require_claim": False,
            "send_transcript_email": bool(support_email),
            "transcript_email_address": support_email,
        }

        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2)

        log_action(request.username, "reset_ticket_config", {"status": "reset to defaults"})

        return jsonify({"success": True, "message": "Ticket configuration reset to defaults"})

    except Exception as e:
        return jsonify({"error": f"Failed to reset ticket config: {str(e)}", "details": traceback.format_exc()}), 500


@tickets_bp.route("/api/notifications/register", methods=["POST"])
async def notification_register_endpoint():
    """Register FCM token for push notifications"""
    try:
        from Utils.notification_service import is_fcm_enabled, register_token

        if not is_fcm_enabled():
            return jsonify({"error": "Push notifications are not enabled on this server"}), 503

        token_data = request.get_json()
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        jwt_token = auth_header.split(" ")[1]

        try:
            from api.utils.auth import jwt_decode_lock

            with jwt_decode_lock:
                decoded = jwt.decode(jwt_token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            user_id = decoded.get("discord_id") or decoded.get("user_id")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        fcm_token = token_data.get("fcm_token") if token_data else None
        device_info = token_data.get("device_info") if token_data else None

        if not fcm_token:
            return jsonify({"error": "fcm_token is required"}), 400

        success = await register_token(user_id, fcm_token, device_info)

        if success:
            return jsonify({"message": "Token registered successfully"}), 200
        else:
            return jsonify({"error": "Failed to register token"}), 500

    except Exception as e:
        logger.error(f"Error registering FCM token: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to register token: {str(e)}"}), 500


@tickets_bp.route("/api/notifications/unregister", methods=["POST"])
async def notification_unregister_endpoint():
    """Unregister FCM token"""
    try:
        from Utils.notification_service import is_fcm_enabled, unregister_token

        if not is_fcm_enabled():
            return jsonify({"error": "Push notifications are not enabled on this server"}), 503

        token_data = request.get_json()
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        jwt_token = auth_header.split(" ")[1]

        try:
            from api.utils.auth import jwt_decode_lock

            with jwt_decode_lock:
                decoded = jwt.decode(jwt_token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            user_id = decoded.get("discord_id") or decoded.get("user_id")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        fcm_token = token_data.get("fcm_token") if token_data else None

        if not fcm_token:
            return jsonify({"error": "fcm_token is required"}), 400

        success = await unregister_token(user_id, fcm_token)

        if success:
            return jsonify({"message": "Token unregistered successfully"}), 200
        else:
            return jsonify({"error": "Token not found"}), 404

    except Exception as e:
        logger.error(f"Error unregistering FCM token: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to unregister token: {str(e)}"}), 500


@tickets_bp.route("/api/notifications/settings", methods=["GET"])
async def notification_settings_get_endpoint():
    """Get notification settings for authenticated user."""
    try:
        from Utils.notification_service import get_user_notification_settings

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        jwt_token = auth_header.split(" ")[1]

        try:
            from api.utils.auth import jwt_decode_lock

            with jwt_decode_lock:
                decoded = jwt.decode(jwt_token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            user_id = decoded.get("discord_id") or decoded.get("user_id")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        settings = await get_user_notification_settings(user_id)
        return jsonify(settings), 200
    except Exception as e:
        logger.error(f"Error getting notification settings: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to get settings: {str(e)}"}), 500


@tickets_bp.route("/api/notifications/settings", methods=["PUT"])
async def notification_settings_update_endpoint():
    """Update notification settings for authenticated user."""
    try:
        from Utils.notification_service import update_user_notification_settings

        settings_data = request.get_json() or {}
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        jwt_token = auth_header.split(" ")[1]

        try:
            from api.utils.auth import jwt_decode_lock

            with jwt_decode_lock:
                decoded = jwt.decode(jwt_token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            user_id = decoded.get("discord_id") or decoded.get("user_id")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        valid_settings = {
            "ticket_new_messages",
            "ticket_mentions",
            "ticket_created",
            "ticket_assigned",
        }
        filtered_settings = {k: v for k, v in settings_data.items() if k in valid_settings}
        if not filtered_settings:
            return jsonify({"error": "No valid settings provided"}), 400

        success = await update_user_notification_settings(user_id, filtered_settings)
        if success:
            return jsonify({"message": "Settings updated successfully"}), 200
        return jsonify({"error": "Failed to update settings"}), 500
    except Exception as e:
        logger.error(f"Error updating notification settings: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to update settings: {str(e)}"}), 500
