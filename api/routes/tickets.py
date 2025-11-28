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

        tickets = tickets_data_list

        # Filter by status if provided
        status_filter = request.args.get("status")
        if status_filter:
            tickets = [t for t in tickets if t.get("status", "").lower() == status_filter.lower()]

        guild = bot.get_guild(Config.GUILD_ID)
        enriched_tickets = []

        for ticket in tickets:
            creator_id = ticket.get("user_id")
            creator = guild.get_member(int(creator_id)) if guild and creator_id else None

            claimed_by_id = ticket.get("claimed_by")
            claimer = guild.get_member(int(claimed_by_id)) if guild and claimed_by_id else None

            assigned_to_id = ticket.get("assigned_to")
            assigned = guild.get_member(int(assigned_to_id)) if guild and assigned_to_id else None

            enriched_ticket = {
                "ticket_id": ticket.get("ticket_id"),
                "ticket_num": ticket.get("ticket_num"),
                "channel_id": str(ticket.get("channel_id")) if ticket.get("channel_id") else None,
                "user_id": str(creator_id) if creator_id else None,
                "username": creator.name if creator else "Unknown User",
                "display_name": creator.display_name if creator else "Unknown User",
                "avatar_url": str(creator.avatar.url) if creator and creator.avatar else None,
                "type": ticket.get("type", "General"),
                "status": ticket.get("status", "Open"),
                "created_at": ticket.get("created_at"),
                "closed_at": ticket.get("closed_at"),
                "claimed_by": str(claimed_by_id) if claimed_by_id else None,
                "claimed_by_name": claimer.display_name if claimer else None,
                "claimed_by_avatar": str(claimer.avatar.url) if claimer and claimer.avatar else None,
                "assigned_to": str(assigned_to_id) if assigned_to_id else None,
                "assigned_to_name": assigned.display_name if assigned else None,
                "assigned_to_avatar": str(assigned.avatar.url) if assigned and assigned.avatar else None,
            }
            enriched_tickets.append(enriched_ticket)

        enriched_tickets.sort(key=lambda t: t.get("ticket_num", 0), reverse=True)

        return jsonify({"tickets": enriched_tickets, "total": len(enriched_tickets)})
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
                # normalize string fields for frontend
                if enriched.get("channel_id") is not None:
                    enriched["channel_id"] = str(enriched["channel_id"])
                if enriched.get("claimed_by") is not None:
                    enriched["claimed_by"] = str(enriched["claimed_by"])
                if enriched.get("assigned_to") is not None:
                    enriched["assigned_to"] = str(enriched["assigned_to"])
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
        import asyncio
        from Cogs.TicketSystem import load_tickets, load_counter, save_ticket, update_ticket, TICKETS_CATEGORY_ID, TicketControlView, create_ticket_embed, ADMIN_ROLE_ID, MODERATOR_ROLE_ID
        import uuid

        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        ticket_type = data.get("type")
        subject = data.get("subject")
        description = data.get("description")

        if not ticket_type or not subject or not description:
            return jsonify({"error": "Missing required fields: type, subject, description"}), 400

        config_file = Path(__file__).parent.parent / Config.DATA_DIR / "tickets_config.json"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                ticket_config = json.load(f)
                valid_categories = ticket_config.get("categories", ["Application", "Bug", "Support"])
        else:
            valid_categories = ["Application", "Bug", "Support"]

        if ticket_type not in valid_categories:
            return jsonify({"error": f"Invalid ticket type. Must be one of: {', '.join(valid_categories)}"}), 400

        if len(subject) < 3 or len(subject) > 100:
            return jsonify({"error": "Subject must be between 3 and 100 characters"}), 400
        if len(description) < 10 or len(description) > 2000:
            return jsonify({"error": "Description must be between 10 and 2000 characters"}), 400

        discord_id = getattr(request, "discord_id", None)
        if not discord_id or discord_id == "unknown":
            return jsonify({"error": "User information not found"}), 401

        user_id = int(discord_id)
        guild = bot.get_guild(Config.GUILD_ID)
        if not guild:
            return jsonify({"error": "Guild not found"}), 500

        member = guild.get_member(user_id)
        if not member:
            return jsonify({"error": "User not found in guild"}), 404

        is_admin_or_mod = any(role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in member.roles)

        loop = bot.loop
        tickets = asyncio.run_coroutine_threadsafe(load_tickets(), loop).result(timeout=10)

        if not is_admin_or_mod:
            last_ticket = None
            for t in tickets:
                if t.get("user_id") == user_id:
                    if not last_ticket or t.get("created_at") > last_ticket.get("created_at"):
                        last_ticket = t
            if last_ticket:
                from datetime import datetime, timedelta

                time_since_last = datetime.now() - datetime.fromisoformat(last_ticket["created_at"])
                if time_since_last < timedelta(hours=1):
                    remaining_minutes = int((timedelta(hours=1) - time_since_last).total_seconds() / 60)
                    return jsonify(
                        {"error": f"You can only create one ticket per hour. Please wait {remaining_minutes} minutes."}
                    ), 429

        initial_message = f"**Subject:** {subject}\n\n**Description:**\n{description}"

        async def create_ticket_from_api():
            import discord

            tickets_list = await load_tickets()
            category = guild.get_channel(TICKETS_CATEGORY_ID)
            if not category or not isinstance(category, discord.CategoryChannel):
                raise Exception("Tickets category not available")

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                member: discord.PermissionOverwrite(view_channel=True),
                guild.me: discord.PermissionOverwrite(view_channel=True),
            }
            moderator_role = discord.utils.get(guild.roles, id=MODERATOR_ROLE_ID)
            if moderator_role:
                overwrites[moderator_role] = discord.PermissionOverwrite(view_channel=True)

            existing_nums = [t.get("ticket_num", 0) for t in tickets_list]
            max_existing = max(existing_nums) if existing_nums else 0
            current_counter = await load_counter()
            if current_counter <= max_existing:
                ticket_num = max_existing + 1
                await update_ticket(None, {"counter": ticket_num + 1}) if callable(update_ticket) else None
            else:
                ticket_num = current_counter
                await update_ticket(None, {"counter": ticket_num + 1}) if callable(update_ticket) else None

            channel = await guild.create_text_channel(
                name=f"ticket-{ticket_num}-{ticket_type}-{member.name}",
                overwrites=overwrites,
                category=category,
            )

            ticket_data = {
                "ticket_id": str(uuid.uuid4()),
                "ticket_num": ticket_num,
                "user_id": member.id,
                "channel_id": channel.id,
                "type": ticket_type,
                "status": "Open",
                "claimed_by": None,
                "assigned_to": None,
                "created_at": datetime.now().isoformat(),
                "embed_message_id": None,
                "reopen_count": 0,
                "initial_message": initial_message,
            }

            await save_ticket(ticket_data)

            embed = create_ticket_embed(ticket_data, guild.me)
            view = TicketControlView()
            for item in view.children:
                if isinstance(item, discord.ui.Button) and item.label == "Reopen":
                    item.disabled = True

            msg = await channel.send(
                f"{member.mention}, your ticket has been opened!",
                embed=embed,
                view=view,
            )

            ticket_data["embed_message_id"] = msg.id
            await update_ticket(channel.id, {"embed_message_id": msg.id})

            admin_role = discord.utils.get(guild.roles, id=ADMIN_ROLE_ID)
            moderator_role = discord.utils.get(guild.roles, id=MODERATOR_ROLE_ID) if MODERATOR_ROLE_ID else None
            roles_to_mention = []
            if admin_role:
                roles_to_mention.append(admin_role.mention)
            if moderator_role:
                roles_to_mention.append(moderator_role.mention)

            if roles_to_mention:
                await channel.send(f"{' '.join(roles_to_mention)} New ticket #{ticket_num} created by {member.mention}.")

            if initial_message:
                await channel.send(initial_message)

            await channel.send("An admin or moderator will handle your request soon. Please wait patiently.")

            return ticket_data

        ticket_data = asyncio.run_coroutine_threadsafe(create_ticket_from_api(), loop).result(timeout=20)

        async def notify_push():
            ticket_data["user_name"] = member.display_name if member else "Unknown"
            await send_push_notification_for_ticket_event(ticket_data["ticket_id"], "new_ticket", ticket_data)

        asyncio.run_coroutine_threadsafe(notify_push(), loop)

        return jsonify(
            {
                "success": True,
                "ticket_id": ticket_data["ticket_id"],
                "ticket_num": ticket_data["ticket_num"],
                "channel_id": str(ticket_data["channel_id"]),
                "message": f"Ticket #{ticket_data['ticket_num']} created successfully!",
            }
        ), 201
    except Exception as e:
        return jsonify({"error": f"Failed to create ticket: {str(e)}", "details": traceback.format_exc()}), 500


@tickets_bp.route("/api/tickets/<ticket_id>", methods=["GET"])
@token_required
def get_ticket(ticket_id):
    """Get a ticket by ID"""
    try:
        import asyncio
        from Cogs.TicketSystem import load_tickets

        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        loop = bot.loop
        tickets = asyncio.run_coroutine_threadsafe(load_tickets(), loop).result(timeout=10)

        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        guild = bot.get_guild(Config.GUILD_ID)
        creator_id = ticket.get("user_id")
        creator = guild.get_member(int(creator_id)) if guild and creator_id else None

        claimed_by_id = ticket.get("claimed_by")
        claimer = guild.get_member(int(claimed_by_id)) if guild and claimed_by_id else None

        assigned_to_id = ticket.get("assigned_to")
        assigned = guild.get_member(int(assigned_to_id)) if guild and assigned_to_id else None

        enriched_ticket = {
            "ticket_id": ticket.get("ticket_id"),
            "ticket_num": ticket.get("ticket_num"),
            "channel_id": str(ticket.get("channel_id")) if ticket.get("channel_id") else None,
            "user_id": str(creator_id) if creator_id else None,
            "username": creator.name if creator else "Unknown User",
            "display_name": creator.display_name if creator else "Unknown User",
            "avatar_url": str(creator.avatar.url) if creator and creator.avatar else None,
            "type": ticket.get("type", "General"),
            "status": ticket.get("status", "Open"),
            "created_at": ticket.get("created_at"),
            "closed_at": ticket.get("closed_at"),
            "claimed_by": str(claimed_by_id) if claimed_by_id else None,
            "claimed_by_name": claimer.name if claimer else None,
            "assigned_to": str(assigned_to_id) if assigned_to_id else None,
            "assigned_to_name": assigned.name if assigned else None,
        }

        return jsonify(enriched_ticket)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch ticket: {str(e)}", "details": traceback.format_exc()}), 500


@tickets_bp.route("/api/tickets/<ticket_id>", methods=["PUT"])
@token_required
@require_permission("all")
def update_ticket(ticket_id):
    """Update a ticket"""
    try:
        import asyncio
        from Cogs.TicketSystem import load_tickets, update_ticket as update_ticket_data

        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        loop = bot.loop
        tickets = asyncio.run_coroutine_threadsafe(load_tickets(), loop).result(timeout=10)
        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        channel_id = ticket.get("channel_id")

        updates = {}
        if "status" in data:
            updates["status"] = data["status"]
        if "assigned_to" in data:
            updates["assigned_to"] = int(data["assigned_to"]) if data["assigned_to"] else None
        if "claimed_by" in data:
            updates["claimed_by"] = int(data["claimed_by"]) if data["claimed_by"] else None
        if "type" in data:
            updates["type"] = data["type"]

        asyncio.run_coroutine_threadsafe(update_ticket_data(channel_id, updates), loop).result(timeout=10)

        log_action(
            request.username,
            "update_ticket",
            {"ticket_id": ticket_id, "ticket_num": ticket.get("ticket_num"), "updates": list(updates.keys())},
        )

        return jsonify({"success": True, "message": "Ticket updated successfully"})
    except Exception as e:
        return jsonify({"error": f"Failed to update ticket: {str(e)}", "details": traceback.format_exc()}), 500


@tickets_bp.route("/api/tickets/<ticket_id>", methods=["DELETE"])
@token_required
@require_permission("all")
def delete_ticket(ticket_id):
    """Delete a ticket"""
    try:
        import asyncio
        from Cogs.TicketSystem import delete_ticket as delete_ticket_storage, load_tickets

        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        loop = bot.loop
        tickets = asyncio.run_coroutine_threadsafe(load_tickets(), loop).result(timeout=10)
        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        channel_id = ticket.get("channel_id")
        asyncio.run_coroutine_threadsafe(delete_ticket_storage(channel_id), loop).result(timeout=10)

        log_action(
            request.username, "delete_ticket", {"ticket_id": ticket_id, "ticket_num": ticket.get("ticket_num"), "status": "deleted"}
        )

        return jsonify({"success": True, "message": f"Ticket #{ticket.get('ticket_num')} deleted successfully"})
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
        import asyncio
        from Cogs.TicketSystem import load_tickets

        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        ticket_cog = bot.get_cog("TicketSystem")
        if not ticket_cog:
            return jsonify({"error": "TicketSystem cog not loaded"}), 503

        # Load tickets from storage
        loop = bot.loop
        tickets = asyncio.run_coroutine_threadsafe(load_tickets(), loop).result(timeout=10)
        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        channel = bot.get_channel(ticket.get("channel_id"))
        if not channel:
            return jsonify({"error": "Ticket channel not found"}), 404

        async def fetch_messages():
            messages = []
            async for message in channel.history(limit=50, oldest_first=False):
                # Skip bot system messages unless they are meaningful
                if message.author.bot:
                    if not (
                        message.content.startswith("**Initial details")
                        or message.content.startswith("**[Admin Panel")
                        or "Ticket successfully closed" in message.content
                        or "Ticket claimed by" in message.content
                        or "Ticket assigned to" in message.content
                        or "Ticket has been reopened" in message.content
                    ):
                        continue

                avatar_url = None
                is_admin = False
                user_role = None  # 'admin', 'moderator', or None

                # Check roles on the author
                if hasattr(message.author, "roles") and message.author.roles:
                    for role in message.author.roles:
                        if role.id == Config.ADMIN_ROLE_ID:
                            is_admin = True
                            user_role = "admin"
                            break
                        if role.id == Config.MODERATOR_ROLE_ID:
                            is_admin = True
                            user_role = "moderator"
                            break

                # Admin panel proxy message -> resolve real admin avatar/role
                if message.content.startswith("**[Admin Panel"):
                    is_admin = True
                    admin_match = re.search(r"\[Admin Panel - ([^\]]+)\]", message.content)
                    if admin_match:
                        admin_username = admin_match.group(1)
                        guild = message.guild
                        admin_member = None
                        for member in guild.members:
                            if (
                                member.name == admin_username
                                or member.display_name == admin_username
                                or getattr(member, "global_name", None) == admin_username
                            ):
                                admin_member = member
                                break

                        if admin_member:
                            if hasattr(admin_member, "roles") and admin_member.roles:
                                for role in admin_member.roles:
                                    if role.id == Config.ADMIN_ROLE_ID:
                                        user_role = "admin"
                                        break
                                    if role.id == Config.MODERATOR_ROLE_ID:
                                        user_role = "moderator"
                                        break
                            try:
                                if admin_member.display_avatar:
                                    avatar_url = str(admin_member.display_avatar.url)
                                elif getattr(admin_member, "avatar", None):
                                    avatar_url = str(admin_member.avatar.url)
                            except Exception:
                                avatar_url = None

                if avatar_url is None:
                    try:
                        if message.author.display_avatar:
                            avatar_url = str(message.author.display_avatar.url)
                        elif getattr(message.author, "avatar", None):
                            avatar_url = str(message.author.avatar.url)
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
                        "is_admin": is_admin,
                        "role": user_role,
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
        import asyncio
        from Cogs.TicketSystem import load_tickets

        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        ticket_cog = bot.get_cog("TicketSystem")
        if not ticket_cog:
            return jsonify({"error": "TicketSystem cog not loaded"}), 503

        loop = bot.loop
        tickets = asyncio.run_coroutine_threadsafe(load_tickets(), loop).result(timeout=10)
        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
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

            user_role = None
            if any(role.id == Config.ADMIN_ROLE_ID for role in member.roles):
                user_role = "admin"
            elif any(role.id == Config.MODERATOR_ROLE_ID for role in member.roles):
                user_role = "moderator"

            return {
                "id": str(msg.id),
                "author_id": str(member.id),
                "author_name": member.name,
                "author_avatar": avatar_url,
                "content": content,
                "timestamp": msg.created_at.isoformat(),
                "is_bot": False,
                "is_admin": is_admin_or_mod,
                "role": user_role,
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
        import asyncio
        from Cogs.TicketSystem import load_tickets, update_ticket

        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        data = request.get_json()
        claimed_by = data.get("claimed_by")
        if not claimed_by:
            return jsonify({"error": "claimed_by is required"}), 400

        loop = bot.loop
        tickets = asyncio.run_coroutine_threadsafe(load_tickets(), loop).result(timeout=10)
        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        if ticket.get("status") == "Closed":
            return jsonify({"error": "Cannot claim a closed ticket"}), 400

        channel_id = ticket.get("channel_id")
        channel = bot.get_channel(channel_id)
        if channel:
            claimer_name = f"User {claimed_by}"
            guild = bot.get_guild(Config.GUILD_ID)
            if guild:
                claimer = guild.get_member(int(claimed_by))
                if claimer:
                    claimer_name = claimer.display_name

            async def send_claim():
                await channel.send(f"🎫 **Ticket claimed by {claimer_name}**\nStatus changed to: **Claimed**")

            asyncio.run_coroutine_threadsafe(send_claim(), loop).result(timeout=10)

        asyncio.run_coroutine_threadsafe(
            update_ticket(channel_id, {"claimed_by": int(claimed_by), "status": "Claimed"}), loop
        ).result(timeout=10)

        notify_ticket_update(ticket_id, "status_change", {"status": "Claimed", "claimed_by": str(claimed_by)})
        try:
            asyncio.run_coroutine_threadsafe(
                send_push_notification_for_ticket_event(ticket_id, "ticket_assigned", ticket),
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
        import asyncio
        from Cogs.TicketSystem import load_tickets, update_ticket

        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        data = request.get_json()
        assigned_to = data.get("assigned_to")
        if not assigned_to:
            return jsonify({"error": "assigned_to is required"}), 400

        loop = bot.loop
        tickets = asyncio.run_coroutine_threadsafe(load_tickets(), loop).result(timeout=10)
        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        if ticket.get("status") == "Closed":
            return jsonify({"error": "Cannot assign a closed ticket"}), 400

        channel_id = ticket.get("channel_id")
        channel = bot.get_channel(channel_id)
        if channel:
            guild = bot.get_guild(Config.GUILD_ID)
            assignee_display = f"User {assigned_to}"
            assignee_mention = f"<@{assigned_to}>"
            if guild:
                assignee = guild.get_member(int(assigned_to))
                if assignee:
                    assignee_display = assignee.display_name
                    assignee_mention = assignee.mention

            async def send_assign():
                await channel.send(f"👤 **Ticket assigned to {assignee_display}** ({assignee_mention})")

            asyncio.run_coroutine_threadsafe(send_assign(), loop).result(timeout=10)

        asyncio.run_coroutine_threadsafe(
            update_ticket(channel_id, {"assigned_to": int(assigned_to)}), loop
        ).result(timeout=10)

        notify_ticket_update(ticket_id, "status_change", {"assigned_to": str(assigned_to)})
        try:
            asyncio.run_coroutine_threadsafe(
                send_push_notification_for_ticket_event(ticket_id, "ticket_assigned", ticket),
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
        import asyncio
        from Cogs.TicketSystem import load_tickets, update_ticket

        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        data = request.get_json() or {}
        close_message = data.get("close_message", "Ticket closed by admin.")

        loop = bot.loop
        tickets = asyncio.run_coroutine_threadsafe(load_tickets(), loop).result(timeout=10)
        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        channel_id = ticket.get("channel_id")
        asyncio.run_coroutine_threadsafe(
            update_ticket(
                channel_id,
                {"status": "Closed", "closed_at": Config.get_utc_now().isoformat(), "claimed_by": None, "assigned_to": None},
            ),
            loop,
        ).result(timeout=10)

        # Send close message
        try:
            channel = bot.get_channel(channel_id)
            if channel:
                asyncio.run_coroutine_threadsafe(channel.send(close_message), bot.loop).result(timeout=5)
        except Exception:
            pass

        notify_ticket_update(ticket_id, "status_change", {"status": "Closed"})
        try:
            asyncio.run_coroutine_threadsafe(
                send_push_notification_for_ticket_event(ticket_id, "ticket_assigned", ticket),
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
        import asyncio
        from Cogs.TicketSystem import load_tickets, update_ticket

        bot = _get_bot()
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        loop = bot.loop
        tickets = asyncio.run_coroutine_threadsafe(load_tickets(), loop).result(timeout=10)
        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        reopen_count = ticket.get("reopen_count", 0)
        channel_id = ticket.get("channel_id")
        asyncio.run_coroutine_threadsafe(
            update_ticket(
                channel_id,
                {"status": "Open", "closed_at": None, "reopen_count": reopen_count + 1},
            ),
            loop,
        ).result(timeout=10)

        notify_ticket_update(ticket_id, "status_change", {"status": "Open"})
        try:
            asyncio.run_coroutine_threadsafe(
                send_push_notification_for_ticket_event(ticket_id, "ticket_assigned", ticket),
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
