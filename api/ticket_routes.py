"""
Ticket System Routes Blueprint
Handles all /api/tickets/* endpoints for ticket management
"""

import asyncio
import json
import traceback
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, jsonify, request

# Will be initialized by init_ticket_routes()
Config = None
logger = None
token_required = None
require_permission = None
log_action = None
notify_ticket_update = None
send_push_notification_for_ticket_event = None

# Create Blueprint
ticket_bp = Blueprint("tickets", __name__)


def init_ticket_routes(
    app, config, log, auth_module, helpers_module, notification_handlers=None, websocket_handlers=None
):
    """Initialize Ticket routes Blueprint with dependencies"""
    global Config, logger, token_required, require_permission, log_action
    global notify_ticket_update, send_push_notification_for_ticket_event

    Config = config
    logger = log
    token_required = auth_module.token_required
    require_permission = auth_module.require_permission
    log_action = helpers_module.log_action

    # Optional WebSocket/Push notification handlers
    def default_notify(*args):
        pass

    if websocket_handlers:
        notify_ticket_update = websocket_handlers.get("notify_ticket_update", default_notify)
    else:
        notify_ticket_update = default_notify

    if notification_handlers:
        send_push_notification_for_ticket_event = notification_handlers.get(
            "send_push_notification_for_ticket_event", None
        )
    else:
        send_push_notification_for_ticket_event = None

    # Register blueprint WITHOUT decorators first
    app.register_blueprint(ticket_bp)

    # NOW apply decorators to already-registered view functions
    vf = app.view_functions
    vf["tickets.get_tickets"] = token_required(require_permission("all")(vf["tickets.get_tickets"]))
    vf["tickets.get_my_tickets"] = token_required(vf["tickets.get_my_tickets"])
    vf["tickets.create_ticket_endpoint"] = token_required(vf["tickets.create_ticket_endpoint"])
    vf["tickets.get_ticket"] = token_required(vf["tickets.get_ticket"])
    vf["tickets.update_ticket_endpoint"] = token_required(vf["tickets.update_ticket_endpoint"])
    vf["tickets.delete_ticket_endpoint"] = token_required(
        require_permission("all")(vf["tickets.delete_ticket_endpoint"])
    )
    vf["tickets.claim_ticket_endpoint"] = token_required(require_permission("all")(vf["tickets.claim_ticket_endpoint"]))
    vf["tickets.assign_ticket_endpoint"] = token_required(
        require_permission("all")(vf["tickets.assign_ticket_endpoint"])
    )
    vf["tickets.close_ticket_endpoint"] = token_required(require_permission("all")(vf["tickets.close_ticket_endpoint"]))
    vf["tickets.reopen_ticket_endpoint"] = token_required(
        require_permission("all")(vf["tickets.reopen_ticket_endpoint"])
    )
    vf["tickets.get_ticket_messages_endpoint"] = token_required(vf["tickets.get_ticket_messages_endpoint"])
    vf["tickets.send_ticket_message_endpoint"] = token_required(vf["tickets.send_ticket_message_endpoint"])


# ============================================================================
# TICKET SYSTEM ENDPOINTS
# ============================================================================


@ticket_bp.route("/api/tickets", methods=["GET"])
def get_tickets():
    """Get all tickets with optional status filter"""
    try:
        from flask import current_app

        from Cogs.TicketSystem import load_tickets

        # Get tickets data
        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        loop = bot.loop
        future = asyncio.run_coroutine_threadsafe(load_tickets(), loop)
        tickets = future.result(timeout=10)

        # Filter by status if provided
        status_filter = request.args.get("status")
        if status_filter:
            tickets = [t for t in tickets if t.get("status", "").lower() == status_filter.lower()]

        # Enrich with Discord user information
        guild = bot.get_guild(Config.GUILD_ID)
        enriched_tickets = []

        for ticket in tickets:
            # Get creator info
            creator_id = ticket.get("user_id")
            creator = None
            if guild and creator_id:
                creator = guild.get_member(int(creator_id))

            # Get claimer info
            claimed_by_id = ticket.get("claimed_by")
            claimer = None
            if guild and claimed_by_id:
                claimer = guild.get_member(int(claimed_by_id))

            # Get assigned user info
            assigned_to_id = ticket.get("assigned_to")
            assigned = None
            if guild and assigned_to_id:
                assigned = guild.get_member(int(assigned_to_id))

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

        # Sort by ticket_num descending (newest first)
        enriched_tickets.sort(key=lambda t: t.get("ticket_num", 0), reverse=True)

        return jsonify({"tickets": enriched_tickets, "total": len(enriched_tickets)})

    except Exception as e:
        logger.error(f"Error fetching tickets: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch tickets: {str(e)}"}), 500


@ticket_bp.route("/api/tickets/my", methods=["GET"])
def get_my_tickets():
    """Get current user's tickets with optional status filter"""
    try:
        from flask import current_app

        from Cogs.TicketSystem import load_tickets

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Get current user's Discord ID from token
        discord_id = getattr(request, "discord_id", None)
        if not discord_id or discord_id == "unknown":
            return jsonify({"error": "User information not found"}), 401

        user_id = int(discord_id)

        # Get all tickets
        loop = bot.loop
        future = asyncio.run_coroutine_threadsafe(load_tickets(), loop)
        tickets = future.result(timeout=10)

        # Filter by current user
        user_tickets = [t for t in tickets if t.get("user_id") == user_id]

        # Filter by status if provided
        status_filter = request.args.get("status")
        if status_filter:
            user_tickets = [t for t in user_tickets if t.get("status", "").lower() == status_filter.lower()]

        # Enrich with Discord user information
        guild = bot.get_guild(Config.GUILD_ID)
        enriched_tickets = []

        for ticket in user_tickets:
            # Get creator info
            creator = guild.get_member(user_id) if guild else None

            # Get claimer info
            claimed_by_id = ticket.get("claimed_by")
            claimer = None
            if guild and claimed_by_id:
                claimer = guild.get_member(int(claimed_by_id))

            # Get assigned user info
            assigned_to_id = ticket.get("assigned_to")
            assigned = None
            if guild and assigned_to_id:
                assigned = guild.get_member(int(assigned_to_id))

            # Get avatar URLs with fallback
            creator_avatar = None
            if creator:
                try:
                    if creator.display_avatar:
                        creator_avatar = str(creator.display_avatar.url)
                    elif creator.avatar:
                        creator_avatar = str(creator.avatar.url)
                except (AttributeError, Exception):
                    creator_avatar = None

            claimer_avatar = None
            if claimer:
                try:
                    if claimer.display_avatar:
                        claimer_avatar = str(claimer.display_avatar.url)
                    elif claimer.avatar:
                        claimer_avatar = str(claimer.avatar.url)
                except (AttributeError, Exception):
                    claimer_avatar = None

            assigned_avatar = None
            if assigned:
                try:
                    if assigned.display_avatar:
                        assigned_avatar = str(assigned.display_avatar.url)
                    elif assigned.avatar:
                        assigned_avatar = str(assigned.avatar.url)
                except (AttributeError, Exception):
                    assigned_avatar = None

            enriched_ticket = {
                "ticket_id": ticket.get("ticket_id"),
                "ticket_num": ticket.get("ticket_num"),
                "channel_id": str(ticket.get("channel_id")) if ticket.get("channel_id") else None,
                "user_id": str(user_id),
                "username": creator.name if creator else "Unknown User",
                "display_name": creator.display_name if creator else "Unknown User",
                "avatar_url": creator_avatar,
                "type": ticket.get("type", "General"),
                "status": ticket.get("status", "Open"),
                "created_at": ticket.get("created_at"),
                "closed_at": ticket.get("closed_at"),
                "claimed_by": str(claimed_by_id) if claimed_by_id else None,
                "claimed_by_name": claimer.display_name if claimer else None,
                "claimed_by_avatar": claimer_avatar,
                "assigned_to": str(assigned_to_id) if assigned_to_id else None,
                "assigned_to_name": assigned.display_name if assigned else None,
                "assigned_to_avatar": assigned_avatar,
                "initial_message": ticket.get("initial_message"),
            }
            enriched_tickets.append(enriched_ticket)

        # Sort by ticket_num descending (newest first)
        enriched_tickets.sort(key=lambda t: t.get("ticket_num", 0), reverse=True)

        return jsonify({"tickets": enriched_tickets, "total": len(enriched_tickets)})

    except Exception as e:
        logger.error(f"Error fetching user tickets: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch tickets: {str(e)}"}), 500


@ticket_bp.route("/api/tickets", methods=["POST"])
def create_ticket_endpoint():
    """Create a new ticket (for regular users)"""
    try:
        from flask import current_app

        from Cogs.TicketSystem import (
            ADMIN_ROLE_ID,
            MODERATOR_ROLE_ID,
            TICKETS_CATEGORY_ID,
            TicketControlView,
            create_ticket_embed,
            load_counter,
            load_tickets,
            save_counter,
            save_ticket,
            update_ticket,
        )

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Parse request body
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        ticket_type = data.get("type")
        subject = data.get("subject")
        description = data.get("description")

        # Validation
        if not ticket_type or not subject or not description:
            return jsonify({"error": "Missing required fields: type, subject, description"}), 400

        # Load config to validate ticket type
        config_file = Path(__file__).parent.parent / Config.DATA_DIR / "tickets_config.json"
        if config_file.exists():
            with open(config_file, encoding="utf-8") as f:
                ticket_config = json.load(f)
                valid_categories = ticket_config.get("categories", ["Application", "Bug", "Support"])
        else:
            valid_categories = ["Application", "Bug", "Support"]

        if ticket_type not in valid_categories:
            return jsonify({"error": f"Invalid ticket type. Must be one of: {', '.join(valid_categories)}"}), 400

        # Validate lengths
        if len(subject) < 3 or len(subject) > 100:
            return jsonify({"error": "Subject must be between 3 and 100 characters"}), 400
        if len(description) < 10 or len(description) > 2000:
            return jsonify({"error": "Description must be between 10 and 2000 characters"}), 400

        # Get current user info from JWT token (set by @token_required decorator)
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

        # Check cooldown: 1 hour between ticket creations (except admins/mods)
        is_admin_or_mod = any(role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in member.roles)

        if not is_admin_or_mod:
            loop = bot.loop
            future = asyncio.run_coroutine_threadsafe(load_tickets(), loop)
            tickets = future.result(timeout=10)

            user_tickets = [t for t in tickets if t["user_id"] == user_id]
            if user_tickets:
                last_ticket = max(user_tickets, key=lambda t: datetime.fromisoformat(t["created_at"]))
                time_since_last = datetime.now() - datetime.fromisoformat(last_ticket["created_at"])
                if time_since_last < timedelta(hours=1):
                    remaining_minutes = int((timedelta(hours=1) - time_since_last).total_seconds() / 60)
                    error_msg = f"You can only create one ticket per hour. Please wait {remaining_minutes} minutes."
                    return (
                        jsonify({"error": error_msg}),
                        429,
                    )

        # Create initial message combining subject and description
        initial_message = f"**Subject:** {subject}\n\n**Description:**\n{description}"

        loop = bot.loop

        async def create_ticket_from_api():
            import discord

            tickets = await load_tickets()

            guild = bot.get_guild(Config.GUILD_ID)
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

            # Calculate ticket_num
            existing_nums = [t.get("ticket_num", 0) for t in tickets]
            max_existing = max(existing_nums) if existing_nums else 0
            current_counter = await load_counter()
            if current_counter <= max_existing:
                ticket_num = max_existing + 1
                await save_counter(ticket_num + 1)
            else:
                ticket_num = current_counter
                await save_counter(ticket_num + 1)

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
            # Disable Reopen button since ticket is open
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

            # Notify Admins/Moderators
            admin_role = discord.utils.get(guild.roles, id=ADMIN_ROLE_ID)
            moderator_role = discord.utils.get(guild.roles, id=MODERATOR_ROLE_ID) if MODERATOR_ROLE_ID else None
            roles_to_mention = []
            if admin_role:
                roles_to_mention.append(admin_role.mention)
            if moderator_role:
                roles_to_mention.append(moderator_role.mention)

            if roles_to_mention:
                await channel.send(
                    f"{' '.join(roles_to_mention)} New ticket #{ticket_num} created by {member.mention}."
                )

            # Send the initial message (subject + description) to the channel
            if initial_message:
                await channel.send(initial_message)

            await channel.send("An admin or moderator will handle your request soon. Please wait patiently.")

            return ticket_data

        future = asyncio.run_coroutine_threadsafe(create_ticket_from_api(), loop)
        ticket_data = future.result(timeout=15)

        logger.info(
            f"✅ Ticket created via API: #{ticket_data['ticket_num']} "
            f"(ID: {ticket_data['ticket_id']}) by user {discord_id}"
        )

        # Send push notification to admins/mods about new ticket
        if send_push_notification_for_ticket_event:

            async def notify_push():
                # Add user_name to ticket_data for notification
                ticket_data["user_name"] = member.display_name if member else "Unknown"
                await send_push_notification_for_ticket_event(ticket_data["ticket_id"], "new_ticket", ticket_data)

            asyncio.run_coroutine_threadsafe(notify_push(), loop)

        return (
            jsonify(
                {
                    "success": True,
                    "ticket_id": ticket_data["ticket_id"],
                    "ticket_num": ticket_data["ticket_num"],
                    "channel_id": str(ticket_data["channel_id"]),
                    "message": f"Ticket #{ticket_data['ticket_num']} created successfully!",
                }
            ),
            201,
        )

    except Exception as e:
        logger.error(f"❌ Error creating ticket via API: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to create ticket: {str(e)}"}), 500


@ticket_bp.route("/api/tickets/<ticket_id>", methods=["GET"])
def get_ticket(ticket_id):
    """Get a single ticket by ID"""
    try:
        from flask import current_app

        from Cogs.TicketSystem import load_tickets

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        loop = bot.loop
        future = asyncio.run_coroutine_threadsafe(load_tickets(), loop)
        tickets = future.result(timeout=10)

        # Find ticket
        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        # Enrich with Discord user information
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
        logger.error(f"Error fetching ticket {ticket_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch ticket: {str(e)}"}), 500


@ticket_bp.route("/api/tickets/<ticket_id>", methods=["PUT"])
def update_ticket_endpoint(ticket_id):
    """Update a ticket (status, assigned user, etc.)"""
    try:
        from flask import current_app

        from Cogs.TicketSystem import load_tickets
        from Cogs.TicketSystem import update_ticket as update_ticket_data

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Load tickets to find the channel_id
        loop = bot.loop
        future = asyncio.run_coroutine_threadsafe(load_tickets(), loop)
        tickets = future.result(timeout=10)

        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        channel_id = ticket.get("channel_id")

        # Prepare updates
        updates = {}
        if "status" in data:
            updates["status"] = data["status"]
        if "assigned_to" in data:
            # Convert string ID to int or None
            updates["assigned_to"] = int(data["assigned_to"]) if data["assigned_to"] else None
        if "claimed_by" in data:
            updates["claimed_by"] = int(data["claimed_by"]) if data["claimed_by"] else None
        if "type" in data:
            updates["type"] = data["type"]

        # Update ticket
        future = asyncio.run_coroutine_threadsafe(update_ticket_data(channel_id, updates), loop)
        future.result(timeout=10)

        # Log the action
        log_action(
            request.username,
            "update_ticket",
            {"ticket_id": ticket_id, "ticket_num": ticket.get("ticket_num"), "updates": list(updates.keys())},
        )

        return jsonify({"success": True, "message": "Ticket updated successfully"})

    except Exception as e:
        logger.error(f"Error updating ticket {ticket_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to update ticket: {str(e)}"}), 500


@ticket_bp.route("/api/tickets/<ticket_id>", methods=["DELETE"])
def delete_ticket_endpoint(ticket_id):
    """Delete a ticket"""
    try:
        from flask import current_app

        from Cogs.TicketSystem import delete_ticket, load_tickets

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        # Load tickets to find the channel_id and ticket_num
        loop = bot.loop
        future = asyncio.run_coroutine_threadsafe(load_tickets(), loop)
        tickets = future.result(timeout=10)

        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        channel_id = ticket.get("channel_id")
        ticket_num = ticket.get("ticket_num")

        # Delete ticket from database
        future = asyncio.run_coroutine_threadsafe(delete_ticket(channel_id), loop)
        future.result(timeout=10)

        # Log the action
        log_action(
            request.username, "delete_ticket", {"ticket_id": ticket_id, "ticket_num": ticket_num, "status": "deleted"}
        )

        return jsonify({"success": True, "message": f"Ticket #{ticket_num} deleted successfully"})

    except Exception as e:
        logger.error(f"Error deleting ticket {ticket_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to delete ticket: {str(e)}"}), 500


@ticket_bp.route("/api/tickets/<ticket_id>/claim", methods=["POST"])
def claim_ticket_endpoint(ticket_id):
    """Claim a ticket using Discord bot functions for consistency"""
    try:
        from flask import current_app

        from Cogs.TicketSystem import claim_ticket_from_api, load_tickets

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        data = request.get_json() or {}
        user_id = data.get("user_id")  # Admin user ID who claims the ticket

        if not user_id:
            return jsonify({"error": "user_id required"}), 400

        loop = bot.loop

        # Load ticket data
        future = asyncio.run_coroutine_threadsafe(load_tickets(), loop)
        tickets = future.result(timeout=10)

        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        if ticket.get("status") == "Closed":
            return jsonify({"error": "Cannot claim a closed ticket"}), 400

        channel_id = ticket.get("channel_id")

        # Use Discord bot function to claim (ensures button updates, logging, etc.)
        future = asyncio.run_coroutine_threadsafe(claim_ticket_from_api(bot, channel_id, int(user_id), ticket), loop)
        result = future.result(timeout=10)

        if not result.get("success"):
            return jsonify({"error": result.get("error", "Unknown error")}), 400

        # WebSocket notification for real-time updates
        if notify_ticket_update:
            notify_ticket_update(ticket_id, "ticket_claimed", {"claimed_by": int(user_id)})

        # Log action
        log_action(
            request.username,
            "claim_ticket",
            {"ticket_id": ticket_id, "ticket_num": ticket.get("ticket_num"), "claimed_by": user_id},
        )

        return jsonify({"success": True, "message": result.get("message", "Ticket claimed successfully")})

    except Exception as e:
        logger.error(f"Error claiming ticket {ticket_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to claim ticket: {str(e)}"}), 500


@ticket_bp.route("/api/tickets/<ticket_id>/assign", methods=["POST"])
def assign_ticket_endpoint(ticket_id):
    """Assign a ticket to a moderator using Discord bot functions for consistency"""
    try:
        from flask import current_app

        from Cogs.TicketSystem import assign_ticket_from_api, load_tickets

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        data = request.get_json() or {}
        assigned_to = data.get("assigned_to")

        if not assigned_to:
            return jsonify({"error": "assigned_to user_id required"}), 400

        loop = bot.loop

        # Load ticket data
        future = asyncio.run_coroutine_threadsafe(load_tickets(), loop)
        tickets = future.result(timeout=10)

        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        if ticket.get("status") == "Closed":
            return jsonify({"error": "Cannot assign a closed ticket"}), 400

        channel_id = ticket.get("channel_id")

        # Use Discord bot function to assign (ensures button updates, logging, etc.)
        future = asyncio.run_coroutine_threadsafe(
            assign_ticket_from_api(bot, channel_id, int(assigned_to), ticket), loop
        )
        result = future.result(timeout=10)

        if not result.get("success"):
            return jsonify({"error": result.get("error", "Unknown error")}), 400

        # Send push notification to assigned user
        if send_push_notification_for_ticket_event:

            async def notify_push():
                ticket["assigned_to"] = int(assigned_to)
                await send_push_notification_for_ticket_event(ticket_id, "ticket_assigned", ticket)

            asyncio.run_coroutine_threadsafe(notify_push(), loop)

        # WebSocket notification for real-time updates
        if notify_ticket_update:
            notify_ticket_update(ticket_id, "ticket_assigned", {"assigned_to": int(assigned_to)})

        # Log action
        log_action(
            request.username,
            "assign_ticket",
            {"ticket_id": ticket_id, "ticket_num": ticket.get("ticket_num"), "assigned_to": assigned_to},
        )

        return jsonify({"success": True, "message": result.get("message", "Ticket assigned successfully")})

    except Exception as e:
        logger.error(f"Error assigning ticket {ticket_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to assign ticket: {str(e)}"}), 500


@ticket_bp.route("/api/tickets/<ticket_id>/close", methods=["POST"])
def close_ticket_endpoint(ticket_id):
    """Close a ticket with optional message using Discord bot functions for consistency"""
    try:
        from flask import current_app

        from Cogs.TicketSystem import close_ticket_from_api, load_tickets

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        data = request.get_json() or {}
        close_message = data.get("close_message", "")

        loop = bot.loop

        # Load ticket data
        future = asyncio.run_coroutine_threadsafe(load_tickets(), loop)
        tickets = future.result(timeout=10)

        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        if ticket.get("status") == "Closed":
            return jsonify({"error": "Ticket is already closed"}), 400

        channel_id = ticket.get("channel_id")

        # Use Discord bot function to close (ensures transcript, email, button updates, etc.)
        future = asyncio.run_coroutine_threadsafe(
            close_ticket_from_api(bot, channel_id, ticket, close_message if close_message.strip() else None), loop
        )
        result = future.result(timeout=10)

        if not result.get("success"):
            return jsonify({"error": result.get("error", "Unknown error")}), 400

        # WebSocket notification for real-time updates
        if notify_ticket_update:
            notify_ticket_update(ticket_id, "ticket_closed", {"close_message": close_message})

        # Log action
        log_action(
            request.username,
            "close_ticket",
            {
                "ticket_id": ticket_id,
                "ticket_num": ticket.get("ticket_num"),
                "close_message": close_message if close_message else None,
            },
        )

        return jsonify({"success": True, "message": result.get("message", "Ticket closed successfully")})

    except Exception as e:
        logger.error(f"Error closing ticket {ticket_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to close ticket: {str(e)}"}), 500


@ticket_bp.route("/api/tickets/<ticket_id>/reopen", methods=["POST"])
def reopen_ticket_endpoint(ticket_id):
    """Reopen a closed ticket"""
    try:
        from flask import current_app

        from Cogs.TicketSystem import load_tickets
        from Cogs.TicketSystem import update_ticket

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        loop = bot.loop
        future = asyncio.run_coroutine_threadsafe(load_tickets(), loop)
        tickets = future.result(timeout=10)

        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        if ticket.get("status") != "Closed":
            return jsonify({"error": "Ticket is not closed"}), 400

        reopen_count = ticket.get("reopen_count", 0)
        if reopen_count >= 3:
            return jsonify({"error": "Ticket cannot be reopened more than 3 times"}), 400

        channel_id = ticket.get("channel_id")
        channel = bot.get_channel(channel_id)
        if not channel:
            return jsonify({"error": "Ticket channel not found"}), 404

        # Restore permissions for creator
        async def restore_permissions():
            creator = bot.get_user(ticket["user_id"])
            if creator:
                try:
                    await channel.set_permissions(
                        creator,
                        view_channel=True,
                        send_messages=True,
                        add_reactions=True,
                        reason=f"Ticket #{ticket['ticket_num']} reopened",
                    )
                except Exception as e:
                    logger.error(f"Error restoring permissions: {e}")

        future = asyncio.run_coroutine_threadsafe(restore_permissions(), loop)
        future.result(timeout=10)

        # Send reopen message to channel
        async def send_reopen_message():
            await channel.send(
                f"🔓 **Ticket has been reopened!**\nStatus changed to: **Open**\nReopen count: {reopen_count + 1}/3"
            )

        future = asyncio.run_coroutine_threadsafe(send_reopen_message(), loop)
        future.result(timeout=10)

        # Update ticket
        future = asyncio.run_coroutine_threadsafe(
            update_ticket(
                channel_id,
                {
                    "status": "Open",
                    "closed_at": None,
                    "reopen_count": reopen_count + 1,
                    "reopened_at": datetime.now().isoformat(),
                },
            ),
            loop,
        )
        future.result(timeout=10)

        log_action(request.username, "reopen_ticket", {"ticket_id": ticket_id, "ticket_num": ticket.get("ticket_num")})

        return jsonify({"success": True, "message": "Ticket reopened successfully"})

    except Exception as e:
        logger.error(f"Error reopening ticket {ticket_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to reopen ticket: {str(e)}"}), 500


@ticket_bp.route("/api/tickets/<ticket_id>/messages", methods=["GET"])
def get_ticket_messages_endpoint(ticket_id):
    """Get messages from a ticket channel"""
    try:
        from flask import current_app

        from Cogs.TicketSystem import load_tickets

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        loop = bot.loop
        future = asyncio.run_coroutine_threadsafe(load_tickets(), loop)
        tickets = future.result(timeout=10)

        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        channel_id = ticket.get("channel_id")
        channel = bot.get_channel(channel_id)
        if not channel:
            return jsonify({"error": "Ticket channel not found"}), 404

        # Fetch messages from channel
        async def fetch_messages():
            from Cogs.TicketSystem import ADMIN_ROLE_ID, MODERATOR_ROLE_ID

            messages = []
            async for message in channel.history(limit=100, oldest_first=True):
                # Skip bot system messages
                # (but keep Initial details, Admin Panel, user messages, important system messages)
                if message.author.bot:
                    # Check if it's a user message from app (has [username]: prefix)
                    is_user_message_from_app = (
                        message.content.startswith("**[")
                        and not message.content.startswith("**[Admin Panel")
                        and "]:**" in message.content
                    )

                    # Include important bot messages (initial, admin panel, user messages, close/claim/assign/reopen)
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
                        continue

                # Get avatar URL with fallback
                # For admin panel messages and user messages from app,
                # extract the real user's username and get their avatar
                avatar_url = None
                is_admin = False
                user_role = None  # 'admin', 'moderator', or None

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

                # Check if this is an admin panel message or user message from app
                if message.content.startswith("**[Admin Panel"):
                    is_admin = True
                    # Parse admin username from message like "**[Admin Panel - username]:**"
                    import re

                    admin_match = re.search(r"\[Admin Panel - ([^\]]+)\]", message.content)
                    if admin_match:
                        admin_username = admin_match.group(1)
                        # Try to find member by username
                        guild = message.guild
                        admin_member = None
                        for member in guild.members:
                            if (
                                member.name == admin_username
                                or member.display_name == admin_username
                                or member.global_name == admin_username
                            ):
                                admin_member = member
                                break

                        if admin_member:
                            # Determine role for admin panel sender
                            if hasattr(admin_member, "roles") and admin_member.roles:
                                for role in admin_member.roles:
                                    if role.id == ADMIN_ROLE_ID:
                                        user_role = "admin"
                                        break
                                    elif role.id == MODERATOR_ROLE_ID:
                                        user_role = "moderator"
                                        break
                            try:
                                if admin_member.display_avatar:
                                    avatar_url = str(admin_member.display_avatar.url)
                                elif admin_member.avatar:
                                    avatar_url = str(admin_member.avatar.url)
                            except (AttributeError, Exception) as e:
                                logger.debug(f"Could not get avatar for admin {admin_member.id}: {e}")

                elif is_user_message_from_app:
                    # Parse username from user message like "**[username]:**"
                    import re

                    user_match = re.search(r"\*\*\[([^\]]+)\]:\*\*", message.content)
                    if user_match:
                        username = user_match.group(1)
                        # Try to find member by username
                        guild = message.guild
                        user_member = None
                        for member in guild.members:
                            if (
                                member.name == username
                                or member.display_name == username
                                or member.global_name == username
                            ):
                                user_member = member
                                break

                        if user_member:
                            try:
                                if user_member.display_avatar:
                                    avatar_url = str(user_member.display_avatar.url)
                                elif user_member.avatar:
                                    avatar_url = str(user_member.avatar.url)
                            except (AttributeError, Exception) as e:
                                logger.debug(f"Could not get avatar for user {user_member.id}: {e}")

                # If not an admin/user message from app or avatar not found, use message author's avatar
                if avatar_url is None:
                    try:
                        if message.author.display_avatar:
                            avatar_url = str(message.author.display_avatar.url)
                        elif message.author.avatar:
                            avatar_url = str(message.author.avatar.url)
                    except (AttributeError, Exception) as e:
                        logger.debug(f"Could not get avatar for user {message.author.id}: {e}")
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
                        "role": user_role,  # 'admin', 'moderator', or None
                    }
                )

            return messages  # Already in correct order (oldest first)
            return messages  # Already in correct order (oldest first)

        future = asyncio.run_coroutine_threadsafe(fetch_messages(), loop)
        messages = future.result(timeout=10)

        return jsonify({"messages": messages})

    except Exception as e:
        logger.error(f"Error fetching messages for ticket {ticket_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch messages: {str(e)}"}), 500


@ticket_bp.route("/api/tickets/<ticket_id>/messages", methods=["POST"])
def send_ticket_message_endpoint(ticket_id):
    """Send a message to a ticket channel (admins can message any ticket, users can only message their own)"""
    try:
        from flask import current_app

        from Cogs.TicketSystem import ADMIN_ROLE_ID, MODERATOR_ROLE_ID, load_tickets

        bot = current_app.config.get("bot_instance")
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 503

        data = request.get_json() or {}
        message_content = data.get("content", "").strip()

        if not message_content:
            return jsonify({"error": "Message content required"}), 400

        loop = bot.loop
        future = asyncio.run_coroutine_threadsafe(load_tickets(), loop)
        tickets = future.result(timeout=10)

        ticket = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        # Check permissions: Admins/Mods can message any ticket, users can only message their own
        discord_id = getattr(request, "discord_id", None)
        if not discord_id:
            return jsonify({"error": "User information not found"}), 401

        user_id = int(discord_id)
        guild = bot.get_guild(Config.GUILD_ID)
        if not guild:
            return jsonify({"error": "Guild not found"}), 500

        member = guild.get_member(user_id)
        if not member:
            return jsonify({"error": "User not found in guild"}), 404

        is_admin_or_mod = any(role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in member.roles)

        # Users can only message their own tickets
        if not is_admin_or_mod and ticket.get("user_id") != user_id:
            return jsonify({"error": "You can only message your own tickets"}), 403

        channel_id = ticket.get("channel_id")
        channel = bot.get_channel(channel_id)
        if not channel:
            return jsonify({"error": "Ticket channel not found"}), 404

        # Send message to channel
        async def send_message():
            # Format message with prefix for both admins and users (for Discord visibility)
            if is_admin_or_mod:
                formatted_content = f"**[Admin Panel - {request.username}]:** {message_content}"
            else:
                # Add user prefix so it's clear in Discord that message is from app
                formatted_content = f"**[{request.username}]:** {message_content}"

            msg = await channel.send(formatted_content)

            # Get avatar URL with fallback
            avatar_url = None
            try:
                if member.display_avatar:
                    avatar_url = str(member.display_avatar.url)
                elif member.avatar:
                    avatar_url = str(member.avatar.url)
            except (AttributeError, Exception) as e:
                logger.debug(f"Could not get avatar for user {member.id}: {e}")
                avatar_url = None

            # Determine user role for badge display
            user_role = None
            if any(role.id == ADMIN_ROLE_ID for role in member.roles):
                user_role = "admin"
            elif any(role.id == MODERATOR_ROLE_ID for role in member.roles):
                user_role = "moderator"

            logger.info(
                f"📤 Message sent from {member.name} (ID: {member.id}) - "
                f"avatar_url: {avatar_url or 'None'}, is_admin: {is_admin_or_mod}, role: {user_role}"
            )

            return {
                "id": str(msg.id),
                "author_id": str(member.id),
                "author_name": member.name,
                "author_avatar": avatar_url,
                "content": formatted_content,
                "display_content": message_content,  # Original content for app display (without prefix)
                "timestamp": msg.created_at.isoformat(),
                "is_bot": False,
                "is_admin": is_admin_or_mod,
                "role": user_role,
            }

        future = asyncio.run_coroutine_threadsafe(send_message(), loop)
        message_data = future.result(timeout=10)

        # Notify WebSocket clients about new message
        logger.info(f"📨 NEW MESSAGE | Ticket: {ticket_id} | Author: {message_data.get('author_name')} | Content preview: {message_data.get('content', '')[:50]}...")
        notify_ticket_update(ticket_id, "new_message", message_data)

        # Send push notification for new message
        if send_push_notification_for_ticket_event:
            logger.debug(f"📱 About to schedule push notification for ticket {ticket_id}")

            async def notify_push():
                try:
                    logger.debug(f"📱 Starting push notification for new message in ticket {ticket_id}")
                    await send_push_notification_for_ticket_event(ticket_id, "new_message", ticket, message_data)
                    logger.debug(f"📱 Push notification completed for ticket {ticket_id}")
                except Exception as e:
                    logger.error(f"❌ Exception in notify_push: {e}")
                    logger.error(traceback.format_exc())

            try:
                future = asyncio.run_coroutine_threadsafe(notify_push(), loop)
                logger.debug("📱 Push notification scheduled, waiting for result...")
                # Wait for it to complete to see any errors
                future.result(timeout=5)
                logger.debug("📱 Push notification future completed")
            except Exception as e:
                logger.error(f"❌ Push notification future failed: {e}")
                logger.error(traceback.format_exc())

        log_action(
            request.username,
            "send_ticket_message",
            {"ticket_id": ticket_id, "ticket_num": ticket.get("ticket_num"), "message_preview": message_content[:50]},
        )

        return jsonify({"success": True, "message": "Message sent successfully", "data": message_data})

    except Exception as e:
        logger.error(f"Error sending message to ticket {ticket_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Failed to send message: {str(e)}"}), 500
