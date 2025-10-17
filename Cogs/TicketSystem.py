import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import uuid
from datetime import datetime, timedelta
from email.message import EmailMessage
import smtplib
import asyncio
import re
from typing import List, Dict, Optional, Any
from Config import PINK, ADMIN_ROLE_ID, MODERATOR_ROLE_ID, TICKETS_CATEGORY_ID
from Utils.EmbedUtils import set_pink_footer
from Utils.CacheUtils import cache
from Utils.Logger import Logger

# === Path to JSON file ===
TICKET_FILE = "Data/tickets.json"


# === Helper functions for JSON persistence ===
@cache(ttl_seconds=30)  # Cache for 30 seconds since tickets can change frequently
async def load_tickets() -> List[Dict[str, Any]]:
    os.makedirs(os.path.dirname(TICKET_FILE), exist_ok=True)
    if not os.path.exists(TICKET_FILE):
        with open(TICKET_FILE, "w") as f:
            json.dump([], f)
    try:
        with open(TICKET_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        Logger.error("Error loading Data/tickets.json – resetting file.")
        return []


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


async def delete_ticket(channel_id: int) -> None:
    tickets = await load_tickets()
    tickets = [t for t in tickets if t["channel_id"] != channel_id]
    with open(TICKET_FILE, "w") as f:
        json.dump(tickets, f, indent=2)


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
        content = f"Transcript for Ticket #{ticket['ticket_num']}\nType: {ticket['type']}\nCreator: {creator_name}\nClaimed by: {claimer_name}\nAssigned to: {assigned_name}\nStatus: {ticket['status']}\n\nTranscript:\n{transcript_text}"
        msg = EmailMessage()
        msg.set_content(content)
        msg["Subject"] = subject
        msg["From"] = os.getenv("SMTP_USER")
        msg["To"] = to_email
        with smtplib.SMTP_SSL(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT", 465))) as smtp:
            smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
            smtp.send_message(msg)
        Logger.info(f"Transcript email sent to {to_email}.")
    except Exception as e:
        Logger.error(f"Error sending email: {e}")


# === Shared Helper Functions (avoids duplication) ===
def create_ticket_embed(ticket_data: Dict[str, Any], bot_user: discord.User) -> discord.Embed:
    ticket_num = ticket_data.get("ticket_num", ticket_data["ticket_id"])
    embed = discord.Embed(
        title=f"🎫 Ticket #{ticket_num}",
        description=f"**Type:** {ticket_data['type']}\n**Status:** {ticket_data['status']}\n**Creator:** <@{ticket_data['user_id']}>",
        color=PINK,
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
        color=PINK,
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
    # Check cooldown: 1 hour between ticket creations per user
    tickets = await load_tickets()
    now = datetime.now()
    user_tickets = [t for t in tickets if t["user_id"] == interaction.user.id]
    if user_tickets:
        last_ticket = max(user_tickets, key=lambda t: datetime.fromisoformat(t["created_at"]))
        if now - datetime.fromisoformat(last_ticket["created_at"]) < timedelta(hours=1):
            await interaction.response.send_message("You can only create a new ticket every 1 hour.", ephemeral=True)
            return

    guild = interaction.guild
    category = guild.get_channel(TICKETS_CATEGORY_ID)
    if not category or not isinstance(category, discord.CategoryChannel):
        Logger.error(f"Tickets category with ID {TICKETS_CATEGORY_ID} not found or is not a category.")
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
    ticket_num = len(tickets) + 1
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
    view = TicketControlView()  # Buttons are active
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
            Logger.info("Admin/Moderator roles notified in ticket channel.")
        except Exception as e:
            Logger.error(f"Error sending admin/moderator notification: {e}")
    else:
        Logger.warning("Admin or Moderator role not found.")
    # Info for the creator
    await channel.send(
        "Please describe your problem, application, or support request in detail here. An admin or moderator will handle it soon."
    )
    # If initial_message provided, send it in the channel
    if initial_message:
        await channel.send(f"**Initial details from {interaction.user.name}:**\n{initial_message}")
    Logger.info(f"Ticket #{ticket_num} created by {interaction.user}.")


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
        Logger.info(f"Ticket in {interaction.channel} assigned to {user_id}.")


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
        try:
            msg = await interaction.channel.fetch_message(ticket["embed_message_id"])
            await msg.edit(embed=embed, view=view)
        except discord.NotFound:
            Logger.error(f"Embed message for ticket {ticket['ticket_num']} not found.")


# === Helper function to disable buttons for closed tickets ===
async def disable_buttons_for_closed_ticket(channel: discord.TextChannel, ticket: Dict[str, Any]) -> None:
    if not ticket.get("embed_message_id"):
        Logger.error(f"No embed_message_id for ticket {ticket['ticket_num']}")
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
        Logger.info(f"Embed for ticket {ticket['ticket_num']} updated.")
    except Exception as e:
        Logger.error(f"Error updating embed for ticket {ticket['ticket_num']}: {e}")


# === Asynchronous function for ticket closing ===
async def close_ticket_async(
    bot: commands.Bot,
    channel: discord.TextChannel,
    ticket: Dict[str, Any],
    followup: Any,
    closing_msg: discord.Message,
    close_message: Optional[str] = None,
) -> None:
    transcript = await create_transcript(channel)
    embed = create_transcript_embed(transcript, bot.user)
    # Send transcript to handler
    claimer = ticket.get("claimed_by")
    if claimer:
        user = bot.get_user(claimer)
        if user:
            try:
                await user.send(embed=embed)
            except discord.Forbidden:
                Logger.warning(f"Could not send transcript to {user} (DMs disabled).")
    # Send notification to creator with details and optional message
    creator = bot.get_user(ticket["user_id"])
    if creator:
        try:
            description = f"Server: {channel.guild.name}\nType: {ticket['type']}\n\n"
            if close_message:
                description += f"**Closing Message:** {close_message}\n\n"
            description += f"Transcript:\n{transcript[: 1900 - len(description)]}"  # Adjust limit
            dm_embed = discord.Embed(
                title=f"Ticket #{ticket['ticket_num']} closed",
                description=description,
                color=PINK,
            )
            set_pink_footer(dm_embed, bot=bot.user)
            await creator.send(embed=dm_embed)
        except discord.Forbidden:
            Logger.warning(f"Could not send notification to {creator} (DMs disabled).")
    # Update ticket status
    ticket["status"] = "Closed"
    ticket["closed_at"] = datetime.now().isoformat()  # Add closed timestamp
    # Disable buttons and update embed before archiving
    await disable_buttons_for_closed_ticket(channel, ticket)
    # Send success message in channel
    success_msg = "Ticket successfully closed and archived. It will be deleted after 7 days."
    if close_message:
        success_msg += f" **Closing Message:** {close_message}"
    await channel.send(success_msg)
    # Delete the closing message
    try:
        await closing_msg.delete()
    except Exception as e:
        Logger.error(f"Error deleting closing message: {e}")
    # Archive the channel to prevent further writing until reopened
    await channel.edit(archived=True)
    # Get names for email
    creator_user = bot.get_user(ticket["user_id"])
    creator_name = creator_user.name if creator_user else f"User {ticket['user_id']}"
    claimer_user = bot.get_user(ticket.get("claimed_by")) if ticket.get("claimed_by") else None
    claimer_name = claimer_user.name if claimer_user else "None"
    assigned_user = bot.get_user(ticket.get("assigned_to")) if ticket.get("assigned_to") else None
    assigned_name = assigned_user.name if assigned_user else "None"
    # Send email
    send_transcript_email(
        os.getenv("SUPPORT_EMAIL"),
        transcript,
        ticket,
        channel.guild.name,
        creator_name,
        claimer_name,
        assigned_name,
    )
    Logger.info(f"Ticket #{ticket['ticket_num']} closed.")


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
    await interaction.response.defer()
    # Send closing message and get the message object
    msg = await interaction.channel.send("Closing ticket...")
    followup = interaction.followup
    # Update status
    await update_ticket(interaction.channel.id, {"status": "Closed"})
    # Close asynchronously, pass the message to delete it later
    asyncio.create_task(
        close_ticket_async(interaction.client, interaction.channel, ticket, followup, msg, close_message)
    )
    Logger.info(f"Ticket closing started for {interaction.channel}.")


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
        Logger.info(f"Ticket in {interaction.channel} claimed by {interaction.user}.")

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
        if ticket.get("reopen_count", 0) >= 1:
            await interaction.response.send_message("This ticket cannot be reopened anymore.", ephemeral=True)
            return
        if not is_allowed_for_ticket_actions(interaction.user, ticket, "Reopen"):
            await interaction.response.send_message("Not authorized.", ephemeral=True)
            return
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
        Logger.info(f"Ticket #{ticket['ticket_num']} reopened by {interaction.user}.")


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
            color=PINK,
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
        embed = self.get_ticket_help_embed(ctx)
        await ctx.send(embed=embed, view=TicketView())

    # /ticket (Slash) - Only synced in guild
    @app_commands.command(name="ticket", description="🎫 Create a new ticket.")
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    async def ticket_slash(self, interaction: discord.Interaction):
        embed = self.get_ticket_help_embed(interaction)
        await interaction.response.send_message(embed=embed, view=TicketView(), ephemeral=True)

    # On ready: Restore views for open and closed tickets and start cleanup
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        Logger.info("TicketSystem Cog ready. Restoring views for open and closed tickets...")
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
                        # Disable buttons based on status
                        for item in view.children:
                            if isinstance(item, discord.ui.Button):
                                if ticket["status"] == "Closed" and item.label != "Reopen":
                                    item.disabled = True
                                elif item.label == "Claim" and ticket.get("claimed_by"):
                                    item.disabled = True
                                elif item.label == "Assign" and ticket.get("assigned_to"):
                                    item.disabled = True
                        await msg.edit(embed=embed, view=view)
                        Logger.info(f"View for ticket #{ticket['ticket_num']} restored.")
                    await asyncio.sleep(6)  # Further increased sleep to avoid rate limits on server
                except Exception as e:
                    Logger.error(f"Error restoring view for ticket {ticket['ticket_num']}: {e}")
        # Start cleanup task
        self.bot.loop.create_task(self.cleanup_old_tickets())

    # Background task for automatic deletion of old tickets
    async def cleanup_old_tickets(self) -> None:
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            Logger.info("Checking old tickets for deletion...")
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
                try:
                    # Try to get the channel, even if archived
                    channel = self.bot.get_channel(ticket["channel_id"])
                    if not channel:
                        # If not in cache, try to fetch from guild
                        guild = self.bot.get_guild(int(os.getenv("DISCORD_GUILD_ID")))
                        if guild:
                            channel = await guild.fetch_channel(ticket["channel_id"])
                    if channel:
                        await channel.delete()
                        Logger.info(f"Old ticket #{ticket['ticket_num']} deleted.")
                    else:
                        Logger.warning(f"Channel for ticket #{ticket['ticket_num']} not found.")
                    await delete_ticket(ticket["channel_id"])
                except Exception as e:
                    Logger.error(f"Error deleting ticket #{ticket['ticket_num']}: {e}")
            await asyncio.sleep(86400)  # Wait 24 hours


# === Setup function ===
async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the TicketSystem cog.
    """
    await bot.add_cog(TicketSystem(bot))
