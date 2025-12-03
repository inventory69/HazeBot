import asyncio
import json
import logging
import os
import re
import smtplib
import uuid
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Any, Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands

import Config
from Config import (
    ADMIN_ROLE_ID,
    MODERATOR_ROLE_ID,
    TICKETS_CATEGORY_ID,
    TRANSCRIPT_CHANNEL_ID,
    get_data_dir,
    get_guild_id,
)
from Utils.EmbedUtils import set_pink_footer

logger = logging.getLogger(__name__)

# === Path to JSON file ===
TICKET_FILE = f"{get_data_dir()}/tickets.json"
TICKET_COUNTER_FILE = f"{get_data_dir()}/ticket_counter.json"


# === Helper functions for JSON persistence ===
# Removed @cache decorator - tickets change frequently, cache causes issues
async def load_tickets() -> List[Dict[str, Any]]:
    os.makedirs(os.path.dirname(TICKET_FILE), exist_ok=True)
    if not os.path.exists(TICKET_FILE):
        with open(TICKET_FILE, "w") as f:
            json.dump([], f)
    try:
        with open(TICKET_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error(f"Error loading {get_data_dir()}/tickets.json – resetting file.")
        return []


async def delete_ticket(channel_id: int) -> None:
    tickets = await load_tickets()
    tickets = [t for t in tickets if t["channel_id"] != channel_id]
    with open(TICKET_FILE, "w") as f:
        json.dump(tickets, f, indent=2)


async def save_ticket(ticket: Dict[str, Any]) -> None:
    tickets = await load_tickets()
    tickets.append(ticket)
    with open(TICKET_FILE, "w") as f:
        json.dump(tickets, f, indent=2)


async def update_ticket(channel_id: int, updates: Dict[str, Any]) -> None:
    tickets = await load_tickets()
    for ticket in tickets:
        if ticket["channel_id"] == channel_id:
            ticket.update(updates)
            break
    with open(TICKET_FILE, "w") as f:
        json.dump(tickets, f, indent=2)


# === Counter functions for ticket numbering ===
async def load_counter() -> int:
    os.makedirs(os.path.dirname(TICKET_COUNTER_FILE), exist_ok=True)
    if not os.path.exists(TICKET_COUNTER_FILE):
        with open(TICKET_COUNTER_FILE, "w") as f:
            json.dump({"next_num": 1}, f)
        return 1
    try:
        with open(TICKET_COUNTER_FILE, "r") as f:
            data = json.load(f)
            return data.get("next_num", 1)
    except json.JSONDecodeError:
        logger.error(f"Error loading {get_data_dir()}/ticket_counter.json – resetting file.")
        return 1


async def save_counter(num: int) -> None:
    with open(TICKET_COUNTER_FILE, "w") as f:
        json.dump({"next_num": num}, f)


# === Permission helper function ===
# Checks if a user is allowed to perform a specific action on a ticket
def is_allowed_for_ticket_actions(user: discord.User, ticket_data: Dict[str, Any], action: str) -> bool:
    # If ticket is closed, only allow Reopen for creator, admins, or moderators
    if ticket_data["status"] == "Closed":
        if action == "Reopen":
            return user.id == ticket_data["user_id"] or any(
                role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in user.roles
            )
        return False
    # Claim only for Admins or Moderators
    if action == "Claim":
        return any(role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in user.roles)
    # Assign only for Admins
    if action == "Assign":
        return any(role.id == ADMIN_ROLE_ID for role in user.roles)
    # Close for creator, Admins, or Moderators
    elif action == "Close":
        return user.id == ticket_data["user_id"] or any(
            role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in user.roles
        )
    # Status for everyone
    return True


# === Helper function to replace mentions in content ===
def replace_mentions(content: str, guild: discord.Guild) -> str:
    def replace_user(match):
        user_id = int(match.group(1))
        user = guild.get_member(user_id)
        return user.name if user else f"User {user_id}"

    def replace_role(match):
        role_id = int(match.group(1))
        role = guild.get_role(role_id)
        return role.name if role else f"Role {role_id}"

    content = re.sub(r"<@(\d+)>", replace_user, content)
    content = re.sub(r"<@&(\d+)>", replace_role, content)
    return content


# === Transcript creation ===
async def create_transcript(channel: discord.TextChannel) -> str:
    transcript = []
    async for msg in channel.history(limit=None, oldest_first=True):
        timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
        author = msg.author.name
        content = replace_mentions(msg.content or "[Attachment/Embed]", channel.guild)
        transcript.append(f"[{timestamp}] {author}: {content}")
    return "\n".join(transcript)


# === Optional email sending ===


# --- HTML transcript helper ---
def build_transcript_html(
    transcript_text: str,
    ticket: Dict[str, Any],
    guild_name: str,
    creator_name: str,
    claimer_name: str,
    assigned_name: str,
) -> str:
    # Split transcript into lines and format as HTML
    transcript_lines = transcript_text.splitlines()
    transcript_html = "".join(
        f'<tr><td style="padding:4px 8px;font-family:monospace;font-size:13px;border-bottom:1px solid #eee;vertical-align:top;">{line.replace(chr(10), "<br>")}</td></tr>'
        for line in transcript_lines
    )
    # Ticket meta info
    meta_html = f"""
        <table style="margin-bottom:18px;font-family:sans-serif;font-size:15px;">
            <tr><td><b>Ticket #:</b></td><td>{ticket["ticket_num"]}</td></tr>
            <tr><td><b>Type:</b></td><td>{ticket["type"]}</td></tr>
            <tr><td><b>Status:</b></td><td>{ticket["status"]}</td></tr>
            <tr><td><b>Creator:</b></td><td>{creator_name}</td></tr>
            <tr><td><b>Claimed by:</b></td><td>{claimer_name or "-"}</td></tr>
            <tr><td><b>Assigned to:</b></td><td>{assigned_name or "-"}</td></tr>
        </table>
    """
    # Main HTML
    html = f"""
    <html>
    <head>
    <meta charset="utf-8">
    <title>Ticket Transcript #{ticket["ticket_num"]}</title>
    </head>
    <body style="background:#fafbfc;padding:24px;">
        <h2 style="font-family:sans-serif;color:#ad1457;">{guild_name} &ndash; Ticket Transcript #{ticket["ticket_num"]}</h2>
        {meta_html}
        <table style="width:100%;border-collapse:collapse;background:#fff;border-radius:8px;box-shadow:0 2px 8px #0001;">
            <thead>
                <tr><th style="text-align:left;padding:8px 8px 8px 8px;background:#f5f5fa;color:#ad1457;font-size:15px;font-family:sans-serif;">Transcript</th></tr>
            </thead>
            <tbody>
                {transcript_html}
            </tbody>
        </table>
        <div style="margin-top:24px;font-size:13px;color:#888;font-family:sans-serif;">This transcript was generated automatically by HazeWorldBot.</div>
    </body>
    </html>
    """
    return html


def send_transcript_email(
    to_email: str,
    transcript_text: str,
    ticket: Dict[str, Any],
    guild_name: str,
    creator_name: str,
    claimer_name: str,
    assigned_name: str,
) -> None:
    try:
        subject = f"{guild_name} - Ticket Transcript - Ticket #{ticket['ticket_num']} - Type: {ticket['type']} - Creator: {creator_name}"
        html_body = build_transcript_html(
            transcript_text, ticket, guild_name, creator_name, claimer_name, assigned_name
        )
        msg = EmailMessage()
        msg.set_content("This is an HTML email. Please view it in an HTML-compatible email client.")
        msg.add_alternative(html_body, subtype="html")
        msg["Subject"] = subject
        msg["From"] = os.getenv("SMTP_USER")
        msg["To"] = to_email
        with smtplib.SMTP_SSL(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT", 465))) as smtp:
            smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
            smtp.send_message(msg)
        logger.info(f"Transcript email sent to {to_email}.")
    except Exception as e:
        logger.error(f"Error sending email: {e}")


# === Shared Helper Functions (avoids duplication) ===
def create_ticket_embed(ticket_data: Dict[str, Any], bot_user: discord.User) -> discord.Embed:
    ticket_num = ticket_data.get("ticket_num", ticket_data["ticket_id"])
    embed = discord.Embed(
        title=f"🎫 Ticket #{ticket_num}",
        description=f"**Type:** {ticket_data['type']}\n**Status:** {ticket_data['status']}\n**Creator:** <@{ticket_data['user_id']}>",
        color=Config.PINK,
    )
    if ticket_data.get("claimed_by"):
        embed.add_field(name="Handler", value=f"<@{ticket_data['claimed_by']}>", inline=True)
    if ticket_data.get("assigned_to"):
        embed.add_field(name="Assigned to", value=f"<@{ticket_data['assigned_to']}>", inline=True)
    set_pink_footer(embed, bot=bot_user)
    return embed


def create_transcript_embed(transcript: str, bot_user: discord.User) -> discord.Embed:
    embed = discord.Embed(
        title="Ticket Transcript",
        description="The transcript has been created and sent via email.",
        color=Config.PINK,
    )
    embed.add_field(name="Transcript", value=transcript[:1024], inline=False)  # Limit length
    set_pink_footer(embed, bot=bot_user)
    return embed


# === Modal for initial message ===
class InitialMessageModal(discord.ui.Modal, title="Provide additional details (optional)"):
    initial_message = discord.ui.TextInput(
        label="Describe your issue or question briefly",
        placeholder="E.g., 'My game crashes when...' or leave empty",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
    )

    def __init__(self, ticket_type: str) -> None:
        super().__init__()
        self.ticket_type = ticket_type

    async def on_submit(self, interaction: discord.Interaction):
        await create_ticket(interaction, self.ticket_type, self.initial_message.value or None)


# === Dropdown for ticket type selection ===
class TicketTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Application", value="application", emoji="📝"),
            discord.SelectOption(label="Bug", value="bug", emoji="🐛"),
            discord.SelectOption(label="Support", value="support", emoji="🛠️"),
        ]
        super().__init__(placeholder="Choose the ticket type…", options=options)

    async def callback(self, interaction: discord.Interaction):
        ticket_type = self.values[0]
        # Open modal for optional message
        await interaction.response.send_modal(InitialMessageModal(ticket_type))


# === View with dropdown ===
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())


# === Ticket creation ===
async def create_ticket(
    interaction: discord.Interaction, ticket_type: str, initial_message: Optional[str] = None
) -> None:
    # Load tickets for cooldown check and ticket number calculation
    tickets = await load_tickets()

    # Check cooldown: 1 hour between ticket creations per user (except admins/mods)
    is_admin_or_mod = any(role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in interaction.user.roles)
    if not is_admin_or_mod:
        now = datetime.now()
        user_tickets = [t for t in tickets if t["user_id"] == interaction.user.id]
        if user_tickets:
            last_ticket = max(user_tickets, key=lambda t: datetime.fromisoformat(t["created_at"]))
            if now - datetime.fromisoformat(last_ticket["created_at"]) < timedelta(hours=1):
                await interaction.response.send_message(
                    "You can only create a new ticket every 1 hour.", ephemeral=True
                )
                return

    guild = interaction.guild
    category = guild.get_channel(TICKETS_CATEGORY_ID)
    if not category or not isinstance(category, discord.CategoryChannel):
        logger.error(f"Tickets category with ID {TICKETS_CATEGORY_ID} not found or is not a category.")
        await interaction.response.send_message("Error: Tickets category not available.", ephemeral=True)
        return
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True),
        guild.me: discord.PermissionOverwrite(view_channel=True),
    }
    moderator_role = discord.utils.get(guild.roles, id=MODERATOR_ROLE_ID)
    if moderator_role:
        overwrites[moderator_role] = discord.PermissionOverwrite(view_channel=True)
    # Calculate ticket_num as the next highest number (no reuse of deleted IDs)
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
        name=f"ticket-{ticket_num}-{ticket_type}-{interaction.user.name}",
        overwrites=overwrites,
        category=category,
    )
    ticket_data = {
        "ticket_id": str(uuid.uuid4()),
        "ticket_num": ticket_num,
        "user_id": interaction.user.id,
        "channel_id": channel.id,
        "type": ticket_type,
        "status": "Open",
        "claimed_by": None,
        "assigned_to": None,
        "created_at": datetime.now().isoformat(),
        "embed_message_id": None,
        "reopen_count": 0,
    }
    # Add initial_message to ticket_data
    ticket_data["initial_message"] = initial_message
    await save_ticket(ticket_data)
    embed = create_ticket_embed(ticket_data, interaction.client.user)
    view = TicketControlView()
    # Disable Reopen button since ticket is open
    for item in view.children:
        if isinstance(item, discord.ui.Button) and item.label == "Reopen":
            item.disabled = True
    msg = await channel.send(
        f"{interaction.user.mention}, your ticket has been opened!",
        embed=embed,
        view=view,
    )
    ticket_data["embed_message_id"] = msg.id
    await update_ticket(channel.id, {"embed_message_id": msg.id})
    await interaction.response.send_message(f"Ticket created! {channel.mention}", ephemeral=True)
    # Notify Admins/Moderators in the ticket channel
    admin_role = discord.utils.get(guild.roles, id=ADMIN_ROLE_ID)
    moderator_role = discord.utils.get(guild.roles, id=MODERATOR_ROLE_ID) if MODERATOR_ROLE_ID else None
    roles_to_mention = []
    if admin_role:
        roles_to_mention.append(admin_role.mention)
    if moderator_role:
        roles_to_mention.append(moderator_role.mention)
    if roles_to_mention:
        try:
            await channel.send(
                f"{' '.join(roles_to_mention)} New ticket #{ticket_num} created by {interaction.user.mention}."
            )
            logger.info("Admin/Moderator roles notified in ticket channel.")
        except Exception as e:
            logger.error(f"Error sending admin/moderator notification: {e}")
    else:
        logger.warning("Admin or Moderator role not found.")
    # Info for the creator
    await channel.send(
        "Please describe your problem, application, or support request in detail here. An admin or moderator will handle it soon."
    )
    await channel.send(
        "💡 **Notification Tip:** To get notified when someone responds, right-click this channel → Notification Settings → All Messages. This ensures you don't miss any updates!"
    )
    # If initial_message provided, send it in the channel
    if initial_message:
        await channel.send(f"**Initial details from {interaction.user.name}:**\n{initial_message}")

    logger.info(f"Ticket #{ticket_num} created by {interaction.user}.")

    # Send push notifications to admins/mods
    try:
        from api.notification_routes import send_push_notification_for_ticket_event
        import asyncio

        # Prepare ticket data for notification
        notification_ticket_data = {
            "ticket_id": ticket_data["ticket_id"],
            "ticket_num": ticket_num,
            "user_id": interaction.user.id,
            "user_name": interaction.user.name,
            "type": ticket_type,
            "status": "Open",
            "assigned_to": None,
            "initial_message": initial_message,  # Include initial message for notification preview
        }

        asyncio.create_task(
            send_push_notification_for_ticket_event(ticket_data["ticket_id"], "new_ticket", notification_ticket_data)
        )
        logger.info(f"📱 Push notification task created for new ticket #{ticket_num}")
    except Exception as e:
        logger.error(f"❌ Failed to send push notification for new ticket: {e}")
        import traceback

        logger.error(traceback.format_exc())


# === Select for assignment ===
class AssignSelect(discord.ui.Select):
    def __init__(self, available_users: List[discord.User]) -> None:
        options = [
            discord.SelectOption(label=user.name, value=str(user.id), description=f"ID: {user.id}")
            for user in available_users
        ]
        if not options:
            options = [discord.SelectOption(label="No moderators available", value="none")]
        super().__init__(placeholder="Choose a moderator to assign...", options=options[:25])  # Max 25

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("No moderators available.", ephemeral=True)
            return
        user_id = int(self.values[0])
        tickets = await load_tickets()
        ticket = next((t for t in tickets if t["channel_id"] == interaction.channel.id), None)
        if not ticket:
            await interaction.response.send_message("Ticket not found.", ephemeral=True)
            return
        await update_ticket(interaction.channel.id, {"assigned_to": user_id})
        await update_embed_and_disable_buttons(interaction)
        await interaction.response.send_message(f"Ticket assigned to <@{user_id}>.", ephemeral=False)
        # Delete the select message
        try:
            await interaction.message.delete()
        except Exception:
            pass
        logger.info(f"Ticket in {interaction.channel} assigned to {user_id}.")


# === View for assignment ===
class AssignView(discord.ui.View):
    def __init__(self, available_users: List[discord.User]) -> None:
        super().__init__(timeout=300)  # 5 minutes timeout
        self.add_item(AssignSelect(available_users))


# === Helper function to update embed and disable buttons ===
async def update_embed_and_disable_buttons(interaction: discord.Interaction) -> None:
    tickets = await load_tickets()
    ticket = next((t for t in tickets if t["channel_id"] == interaction.channel.id), None)
    if ticket and ticket.get("embed_message_id"):
        embed = create_ticket_embed(ticket, interaction.client.user)
        view = TicketControlView()
        # Disable buttons based on permission and status
        for item in view.children:
            if isinstance(item, discord.ui.Button):
                if ticket["status"] == "Closed" and item.label != "Reopen":
                    item.disabled = True
                elif not is_allowed_for_ticket_actions(interaction.user, ticket, item.label):
                    item.disabled = True
                elif item.label == "Claim" and ticket.get("claimed_by"):
                    item.disabled = True
                elif item.label == "Assign" and ticket.get("assigned_to"):
                    item.disabled = True
                elif item.label == "Delete" and not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
                    item.disabled = True  # Only admins can see/use Delete
                elif item.label == "Reopen" and ticket["status"] == "Open":
                    item.disabled = True  # Reopen only visible/clickable when closed
        try:
            msg = await interaction.channel.fetch_message(ticket["embed_message_id"])
            await msg.edit(embed=embed, view=view)
        except discord.NotFound:
            logger.error(f"Embed message for ticket {ticket['ticket_num']} not found.")


# === Helper function to disable buttons for closed tickets ===
async def disable_buttons_for_closed_ticket(channel: discord.TextChannel, ticket: Dict[str, Any]) -> None:
    if not ticket.get("embed_message_id"):
        logger.error(f"No embed_message_id for ticket {ticket['ticket_num']}")
        return
    embed = create_ticket_embed(ticket, channel.guild.me)
    view = TicketControlView()
    for item in view.children:
        if isinstance(item, discord.ui.Button):
            if item.label != "Reopen":
                item.disabled = True
        try:
            msg = await channel.fetch_message(ticket["embed_message_id"])
            await msg.edit(embed=embed, view=view)
            logger.info(f"Embed for ticket {ticket['ticket_num']} updated.")
        except Exception as e:
            logger.error(f"Error updating embed for ticket {ticket['ticket_num']}: {e}")


# === Asynchronous function for ticket closing ===
async def close_ticket_async(
    bot: commands.Bot,
    channel: discord.TextChannel,
    ticket: Dict[str, Any],
    followup: Any,
    closing_msg: discord.Message,
    close_message: Optional[str] = None,
) -> None:
    # Get creator user
    creator = bot.get_user(ticket["user_id"])

    # Send success message in channel (check for None AND empty string)
    success_msg = "Ticket successfully closed and archived. It will be deleted after 7 days."
    if close_message and close_message.strip():
        success_msg += f"\n\n**Closing Message:** {close_message}"
    await channel.send(success_msg)

    # Create transcript after sending the closing message
    transcript = await create_transcript(channel)

    # === SEND EMAIL WITH TRANSCRIPT ===
    # Get names for meta info
    guild_name = channel.guild.name
    creator_name = bot.get_user(ticket["user_id"]).name if bot.get_user(ticket["user_id"]) else str(ticket["user_id"])
    claimer_name = (
        bot.get_user(ticket["claimed_by"]).name
        if ticket.get("claimed_by") and bot.get_user(ticket["claimed_by"])
        else ""
    )
    assigned_name = (
        bot.get_user(ticket["assigned_to"]).name
        if ticket.get("assigned_to") and bot.get_user(ticket["assigned_to"])
        else ""
    )
    # Use SUPPORT_EMAIL from .env as recipient
    to_email = os.getenv("SUPPORT_EMAIL")
    if to_email:
        send_transcript_email(
            to_email,
            transcript,
            ticket,
            guild_name,
            creator_name,
            claimer_name,
            assigned_name,
        )
    else:
        logger.warning("No transcript recipient email configured (SUPPORT_EMAIL).")

    # Create transcript embed for transcript channel
    embed = discord.Embed(
        title=f"🎫 Ticket #{ticket['ticket_num']} - Transcript",
        description=f"**Type:** {ticket['type']}\n**Creator:** <@{ticket['user_id']}>\
            \n**Status:** Closed",
        color=Config.PINK,
    )

    # Add ticket details
    if ticket.get("claimed_by"):
        embed.add_field(name="Handler", value=f"<@{ticket['claimed_by']}>", inline=True)
    if ticket.get("assigned_to"):
        embed.add_field(name="Assigned to", value=f"<@{ticket['assigned_to']}>", inline=True)

    # Add closing message if provided (check for None AND empty string)
    if close_message and close_message.strip():
        embed.add_field(name="Closing Message", value=close_message, inline=False)

    # Add transcript as field (split if too long)
    if len(transcript) <= 1024:
        embed.add_field(name="Transcript", value=transcript, inline=False)
    else:
        # Split transcript into multiple fields
        chunks = [transcript[i : i + 1024] for i in range(0, len(transcript), 1024)]
        for idx, chunk in enumerate(chunks[:5], 1):  # Max 5 fields to avoid embed limit
            embed.add_field(name=f"Transcript (Part {idx})", value=chunk, inline=False)
        if len(chunks) > 5:
            embed.add_field(name="Note", value="Transcript is too long. Full version sent via email.", inline=False)

    set_pink_footer(embed, bot=bot.user)

    # Post transcript to dedicated channel
    transcript_channel = bot.get_channel(TRANSCRIPT_CHANNEL_ID)
    if transcript_channel:
        try:
            await transcript_channel.send(embed=embed)
            logger.info(f"Transcript for ticket #{ticket['ticket_num']} posted to transcript channel.")
        except Exception as e:
            logger.error(f"Error posting transcript to transcript channel: {e}")
    else:
        logger.error(f"Transcript channel with ID {TRANSCRIPT_CHANNEL_ID} not found.")

    # Send closing message to creator separately (check for None AND empty string)
    if creator and close_message and close_message.strip():
        try:
            close_embed = discord.Embed(
                title=f"Ticket #{ticket['ticket_num']} - Closing Message",
                description=close_message,
                color=Config.PINK,
            )
            set_pink_footer(close_embed, bot=bot.user)
            await creator.send(embed=close_embed)
            logger.info(f"Closing message sent to creator {creator.name}")
        except discord.Forbidden:
            logger.warning(f"Could not send closing message to creator {creator.name} (DMs disabled).")
        except Exception as e:
            logger.error(f"Error sending closing message to creator {creator.name}: {e}")

    # Update ticket status
    ticket["status"] = "Closed"
    ticket["closed_at"] = datetime.now().isoformat()

    # Disable buttons and update embed before archiving
    await disable_buttons_for_closed_ticket(channel, ticket)

    # Log ticket closed (green)
    logger.info("\033[92mTicket closed.\033[0m")


# === Modal for optional close message ===
class CloseMessageModal(discord.ui.Modal, title="Optional close message"):
    close_message = discord.ui.TextInput(
        label="Optional close message",
        placeholder="E.g., 'Issue resolved, let me know if you need more help.'",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
    )

    def __init__(self, ticket: Dict[str, Any]) -> None:
        super().__init__()
        self.ticket = ticket

    async def on_submit(self, interaction: discord.Interaction):
        # Proceed with closing, passing the message
        await close_ticket_with_message(interaction, self.ticket, self.close_message.value or None)


# === Asynchronous function for ticket closing with optional message ===
async def close_ticket_with_message(
    interaction: discord.Interaction, ticket: Dict[str, Any], close_message: Optional[str] = None
) -> None:
    # Defer the interaction to prevent timeout
    await interaction.response.defer(ephemeral=True)

    # Send confirmation to user immediately via followup
    await interaction.followup.send("✅ Ticket is being closed...", ephemeral=True)

    # Send closing message and get the message object
    msg = await interaction.channel.send("🔒 Closing ticket...")
    followup = interaction.followup

    # Update status
    await update_ticket(interaction.channel.id, {"status": "Closed"})

    # Close asynchronously, pass the message to delete it later
    asyncio.create_task(
        close_ticket_async(interaction.client, interaction.channel, ticket, followup, msg, close_message)
    )
    logger.info(f"Ticket closing started for {interaction.channel}.")


# === View with ticket buttons ===
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.blurple, emoji="👋")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        tickets = await load_tickets()
        ticket = next((t for t in tickets if t["channel_id"] == interaction.channel.id), None)
        if not ticket or not is_allowed_for_ticket_actions(interaction.user, ticket, "Claim"):
            await interaction.response.send_message("Not authorized.", ephemeral=True)
            return
        await update_ticket(interaction.channel.id, {"claimed_by": interaction.user.id})
        await update_embed_and_disable_buttons(interaction)
        await interaction.response.send_message(f"{interaction.user.mention} has claimed the ticket.", ephemeral=False)
        logger.info(f"Ticket in {interaction.channel} claimed by {interaction.user}.")

    @discord.ui.button(label="Assign", style=discord.ButtonStyle.gray, emoji="📋")
    async def assign(self, interaction: discord.Interaction, button: discord.ui.Button):
        tickets = await load_tickets()
        ticket = next((t for t in tickets if t["channel_id"] == interaction.channel.id), None)
        if not ticket or not is_allowed_for_ticket_actions(interaction.user, ticket, "Assign"):
            await interaction.response.send_message("Not authorized.", ephemeral=True)
            return
        # Get available moderators/admins
        guild = interaction.guild
        available_users = [
            member
            for member in guild.members
            if any(role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in member.roles)
        ]
        if not available_users:
            await interaction.response.send_message("No moderators available to assign.", ephemeral=True)
            return
        # Send view with select
        view = AssignView(available_users)
        await interaction.response.send_message("Select a moderator to assign:", view=view, ephemeral=True)

    @discord.ui.button(label="Status", style=discord.ButtonStyle.green, emoji="📊")
    async def status(self, interaction: discord.Interaction, button: discord.ui.Button):
        tickets = await load_tickets()
        ticket = next((t for t in tickets if t["channel_id"] == interaction.channel.id), None)
        if ticket:
            embed = create_ticket_embed(ticket, interaction.client.user)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("Ticket not found.", ephemeral=True)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        tickets = await load_tickets()
        ticket = next((t for t in tickets if t["channel_id"] == interaction.channel.id), None)
        if not ticket or not is_allowed_for_ticket_actions(interaction.user, ticket, "Close"):
            await interaction.response.send_message("Not authorized.", ephemeral=True)
            return
        # Open modal for optional close message
        await interaction.response.send_modal(CloseMessageModal(ticket))

    @discord.ui.button(label="Reopen", style=discord.ButtonStyle.secondary, emoji="🔓")
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        tickets = await load_tickets()
        ticket = next((t for t in tickets if t["channel_id"] == interaction.channel.id), None)
        if not ticket:
            await interaction.response.send_message("Ticket not found.", ephemeral=True)
            return
        if ticket["status"] != "Closed":
            await interaction.response.send_message("Ticket is already open.", ephemeral=True)
            return
        if ticket.get("reopen_count", 0) >= 3:
            await interaction.response.send_message("This ticket cannot be reopened more than 3 times.", ephemeral=True)
            return
        if not is_allowed_for_ticket_actions(interaction.user, ticket, "Reopen"):
            await interaction.response.send_message("Not authorized.", ephemeral=True)
            return

        # Restore send permissions for creator
        creator = interaction.client.get_user(ticket["user_id"])
        if creator:
            try:
                await interaction.channel.set_permissions(
                    creator,
                    view_channel=True,
                    send_messages=True,
                    add_reactions=True,
                    reason=f"Ticket #{ticket['ticket_num']} reopened",
                )
                logger.info(f"Restored send permissions for creator {creator.name} in reopened ticket.")
            except Exception as e:
                logger.error(f"Error restoring permissions for creator: {e}")

        # Reopen: Set status to Open, unarchive, increase reopen_count
        await update_ticket(
            interaction.channel.id,
            {
                "status": "Open",
                "claimed_by": None,
                "assigned_to": None,
                "reopen_count": ticket.get("reopen_count", 0) + 1,
            },
        )
        await interaction.channel.edit(archived=False)
        await update_embed_and_disable_buttons(interaction)
        await update_ticket(interaction.channel.id, {"status": "Open"})
        await interaction.response.send_message(f"{interaction.user.mention} has reopened the ticket.", ephemeral=False)
        logger.info(f"Ticket #{ticket['ticket_num']} reopened by {interaction.user}.")

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user is admin
        if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("Not authorized. Only admins can delete tickets.", ephemeral=True)
            return

        # Defer to prevent timeout
        await interaction.response.defer(ephemeral=True)

        # Delete the channel
        try:
            await interaction.channel.delete()
            logger.info(f"Ticket channel {interaction.channel.name} deleted by {interaction.user}.")
        except Exception as e:
            logger.error(f"Error deleting channel {interaction.channel.name}: {e}")
            await interaction.followup.send("Error deleting the ticket channel.", ephemeral=True)
            return

        # Remove from database
        await delete_ticket(interaction.channel.id)
        logger.info(f"Ticket data for channel {interaction.channel.id} removed from database.")


# === Cog definition ===
class TicketSystem(commands.Cog):
    """
    🎫 Ticket System Cog: Allows creating and managing support tickets.
    Modular and persistent with JSON.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # Shared Helper for ticket embed (used in prefix and slash)
    def get_ticket_help_embed(self, ctx_or_interaction: Any) -> discord.Embed:
        embed = discord.Embed(
            title="🎫 Ticket System Help",
            description="Create a new ticket for support, bugs, or applications.\nUse `!ticket` or `/ticket`.",
            color=Config.PINK,
        )
        embed.add_field(
            name="Commands",
            value="`!ticket` – Create ticket\n`/ticket` – Slash version",
            inline=False,
        )
        set_pink_footer(embed, bot=self.bot.user if hasattr(self.bot, "user") else None)
        return embed

    # !ticket (Prefix)
    @commands.command(name="ticket")
    async def ticket_command(self, ctx: commands.Context) -> None:
        """
        🎫 Create a new ticket.
        """
        logger.info(f"Ticket creation initiated by {ctx.author}")
        embed = self.get_ticket_help_embed(ctx)
        await ctx.send(embed=embed, view=TicketView())

    # /ticket (Slash) - Only synced in guild
    @app_commands.command(name="ticket", description="🎫 Create a new ticket.")
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    async def ticket_slash(self, interaction: discord.Interaction):
        logger.info(f"Ticket creation slash initiated by {interaction.user}")
        embed = self.get_ticket_help_embed(interaction)
        await interaction.response.send_message(embed=embed, view=TicketView(), ephemeral=True)

    async def _restore_ticket_views(self) -> None:
        """Restore views for open and closed tickets - called on ready and after reload"""
        logger.info("TicketSystem Cog ready. Restoring views for open and closed tickets...")
        tickets = await load_tickets()
        for ticket in tickets:
            if ticket["status"] in ["Open", "Closed"]:
                # Always restore open tickets as user decides when to close
                # Always restore closed tickets as they are static
                try:
                    channel = self.bot.get_channel(ticket["channel_id"])
                    if channel and ticket.get("embed_message_id"):
                        msg = await channel.fetch_message(ticket["embed_message_id"])
                        embed = create_ticket_embed(ticket, self.bot.user)
                        view = TicketControlView()
                        # Disable buttons based on status only (permissions handled on interaction)
                        for item in view.children:
                            if isinstance(item, discord.ui.Button):
                                if ticket["status"] == "Closed" and item.label != "Reopen":
                                    item.disabled = True
                                elif item.label == "Claim" and ticket.get("claimed_by"):
                                    item.disabled = True
                                elif item.label == "Assign" and ticket.get("assigned_to"):
                                    item.disabled = True
                                elif item.label == "Reopen" and ticket["status"] == "Open":
                                    item.disabled = True
                        await msg.edit(embed=embed, view=view)
                        logger.info(f"View for ticket #{ticket['ticket_num']} restored.")
                    await asyncio.sleep(6)  # Further increased sleep to avoid rate limits on server
                except Exception as e:
                    logger.error(f"Error restoring view for ticket {ticket['ticket_num']}: {e}")
        # Start cleanup task if not running
        if not hasattr(self, "_cleanup_task") or self._cleanup_task.done():
            self._cleanup_task = self.bot.loop.create_task(self.cleanup_old_tickets())

    # On ready: Restore views for open and closed tickets and start cleanup
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self._restore_ticket_views()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Listen for messages in ticket channels and notify WebSocket clients"""
        # Ignore bot messages or non-ticket channels
        if message.author.bot or not message.channel:
            return

        # Check if this is a ticket channel
        tickets = await load_tickets()
        ticket = next((t for t in tickets if t["channel_id"] == message.channel.id), None)
        if not ticket:
            return

        # Get avatar URL with fallback
        avatar_url = None
        try:
            if message.author.display_avatar:
                avatar_url = str(message.author.display_avatar.url)
            elif message.author.avatar:
                avatar_url = str(message.author.avatar.url)
        except (AttributeError, Exception) as e:
            logger.debug(f"Could not get avatar for user {message.author.id}: {e}")

        # Check if author has admin role
        is_admin = False
        if hasattr(message.author, "roles") and message.author.roles:
            for role in message.author.roles:
                if role.id == Config.ADMIN_ROLE_ID or role.id == Config.MODERATOR_ROLE_ID:
                    is_admin = True
                    break

        # Prepare message data
        message_data = {
            "id": str(message.id),
            "author_id": str(message.author.id),
            "author_name": message.author.name,
            "author_avatar": avatar_url,
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
            "is_bot": message.author.bot,
            "is_admin": is_admin,
        }

        # Notify WebSocket clients
        try:
            from api.notification_routes import notify_ticket_update

            notify_ticket_update(ticket["ticket_id"], "new_message", message_data)
            logger.info(f"📡 WebSocket notification sent for message in ticket {ticket['ticket_num']}")
        except Exception as e:
            logger.error(f"Failed to send WebSocket notification: {e}")

        # Send push notifications
        try:
            logger.info(f"📱 About to send push notification for ticket {ticket['ticket_id']}")
            from api.notification_routes import send_push_notification_for_ticket_event
            import asyncio

            asyncio.create_task(
                send_push_notification_for_ticket_event(ticket["ticket_id"], "new_message", ticket, message_data)
            )
            logger.info(f"📱 Push notification task created for ticket {ticket['ticket_num']}")
        except Exception as e:
            logger.error(f"❌ Failed to send push notification: {e}")
            import traceback

            logger.error(traceback.format_exc())

    async def cog_load(self) -> None:
        """Called when the cog is loaded (including reloads)"""
        if self.bot.is_ready():
            await self._restore_ticket_views()

    # Background task for automatic deletion of old tickets
    async def cleanup_old_tickets(self) -> None:
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            logger.info("Checking old tickets for deletion...")
            tickets = await load_tickets()
            now = datetime.now()
            to_delete = []
            for ticket in tickets:
                if ticket["status"] == "Closed":
                    closed_at_str = ticket.get("closed_at", ticket.get("created_at"))
                    closed_at = datetime.fromisoformat(closed_at_str)
                    if now - closed_at > timedelta(days=7):
                        to_delete.append(ticket)
            for ticket in to_delete:
                channel_deleted = False
                try:
                    # Try to get the channel, even if archived
                    channel = self.bot.get_channel(ticket["channel_id"])
                    if not channel:
                        # If not in cache, try to fetch from guild
                        guild = self.bot.get_guild(get_guild_id())
                        if guild:
                            try:
                                channel = await guild.fetch_channel(ticket["channel_id"])
                            except discord.NotFound:
                                # Channel already deleted
                                logger.info(
                                    f"Channel for ticket #{ticket['ticket_num']} already deleted. Removing from database."
                                )
                                channel_deleted = True
                            except discord.Forbidden:
                                logger.error(f"No permission to access channel for ticket #{ticket['ticket_num']}.")
                                channel_deleted = True  # Treat as deleted to remove from database

                    if channel:
                        try:
                            await channel.delete()
                            logger.info(f"Old ticket #{ticket['ticket_num']} channel deleted.")
                            channel_deleted = True
                        except discord.NotFound:
                            # Channel was deleted between fetch and delete
                            logger.info(f"Channel for ticket #{ticket['ticket_num']} already deleted.")
                            channel_deleted = True
                        except discord.Forbidden:
                            logger.error(f"No permission to delete channel for ticket #{ticket['ticket_num']}.")
                            # Don't mark as deleted, will retry next time
                    elif not channel_deleted:
                        logger.warning(
                            f"Channel for ticket #{ticket['ticket_num']} not found (may have been manually deleted)."
                        )
                        channel_deleted = True  # Remove from database anyway

                    # Only remove from database if channel was successfully deleted or confirmed not to exist
                    if channel_deleted:
                        await delete_ticket(ticket["channel_id"])
                        logger.info(f"Ticket #{ticket['ticket_num']} removed from database.")

                except discord.NotFound:
                    # Channel doesn't exist, remove from database
                    logger.info(f"Channel for ticket #{ticket['ticket_num']} not found. Removing from database.")
                    await delete_ticket(ticket["channel_id"])
                except Exception as e:
                    logger.error(f"Unexpected error deleting ticket #{ticket['ticket_num']}: {e}")
                    # Don't remove from database on unexpected errors, will retry next time
            await asyncio.sleep(86400)  # Wait 24 hours


# === Setup function ===
async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the TicketSystem cog.
    """
    await bot.add_cog(TicketSystem(bot))
