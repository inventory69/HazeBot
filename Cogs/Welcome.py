import random
import asyncio
import os
from discord.ext import commands
import discord
from Config import PINK, INTEREST_ROLES, WELCOME_RULES_CHANNEL_ID, WELCOME_PUBLIC_CHANNEL_ID, MEMBER_ROLE_ID, PERSISTENT_VIEWS_FILE
from Utils.EmbedUtils import set_pink_footer
from Utils.Logger import Logger

# Polished rules text shown to new members
RULES_TEXT = (
    "🌿 **1. Be kind and respectful to everyone.**\n"
    "✨ **2. No spam, flooding, or excessive self-promotion.**\n"
    "🚫 **3. Illegal content, hate speech, and NSFW are strictly forbidden.**\n"
    "🧑‍💼 **4. Follow the instructions of the team and moderators.**\n"
    "💖 **5. Keep the vibes chill and positive!**\n\n"
    "By clicking 'Accept Rules', you agree to follow these guidelines and unlock full access to the server. Welcome to the lounge!"
)

# Funny welcome messages for public channel (use {name} for username)
WELCOME_MESSAGES = [
    "Welcome {name}! Your chillventory just gained a new member. 🌿",
    "Hey {name}, you unlocked the secret stash of good vibes! ✨",
    "{name} joined the inventarium. Time to relax and enjoy! 😎",
    "Give a warm welcome to {name}, our newest collector of chill moments! 🧘",
    "{name}, you found the legendary lounge zone. Welcome aboard! 🚀",
    "Inventory update: {name} added. Please store your good mood here! 😁",
    "Alert: {name} has entered the realm of ultimate relaxation. 🛋️",
    "Welcome {name}! May your inventory always be full of chill and fun. 🎉",
    "New item in stock: {name}, the ultimate chill collector! 📦",
    "{name} discovered the hidden inventory of positivity. Welcome! 🌟"
]

class InterestSelect(discord.ui.Select):
    """
    Dropdown for user interests. Selection is required before accepting rules.
    """
    def __init__(self, parent_view):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label="Chat & Memes", emoji="💬", description="Talk, joke, and share memes"),
            discord.SelectOption(label="Creative Vibes", emoji="🎨", description="Art, music, writing, and more"),
            discord.SelectOption(label="Gaming & Chill", emoji="🎮", description="Play games and hang out"),
            discord.SelectOption(label="Ideas & Projects", emoji="💡", description="Brainstorm and build together"),
            discord.SelectOption(label="Development", emoji="🖥️", description="Coding, programming, and dev talk"),
            discord.SelectOption(label="Tech & Support", emoji="🛠️", description="Tech talk and help others"),
            discord.SelectOption(label="Just Browsing", emoji="👀", description="Just here to read and vibe"),
        ]
        super().__init__(
            placeholder="Step 1: Select how you want to contribute",
            min_values=1,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        added_roles = []
        for selected in self.values:
            role_id = INTEREST_ROLES.get(selected)
            role = discord.utils.get(guild.roles, id=role_id)
            if role and role not in member.roles:
                await member.add_roles(role, reason=f"Selected interest: {selected}")
                added_roles.append(selected)
        # Mark selection as done in parent view
        self.parent_view.interest_selected = True
        await interaction.response.send_message(
            f"You chose **{', '.join(added_roles)}**! The roles have been added. Now you can accept the rules. 🚀",
            ephemeral=True
        )

class AcceptRulesButton(discord.ui.Button):
    """
    Button for accepting rules.
    """
    def __init__(self, parent_view):
        super().__init__(label="Step 2: Accept Rules", style=discord.ButtonStyle.success, emoji="✅")
        self.parent_view = parent_view
        self.bot = parent_view.bot  # Get bot reference from parent view
        self.cog = parent_view.cog  # Get cog reference from parent view
        self.member = parent_view.member  # Get member reference from parent view

    async def callback(self, interaction: discord.Interaction):
        # Defer the response to avoid timeout
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        member = interaction.user
        if not self.parent_view.interest_selected:
            await interaction.followup.send(
                "Please select at least one way you want to contribute before accepting the rules.",
                ephemeral=True
            )
            return
        role = discord.utils.get(guild.roles, id=MEMBER_ROLE_ID)
        # Add the role if not present
        if role and role not in member.roles:
            await member.add_roles(role, reason="Accepted rules")
        welcome_channel = guild.get_channel(WELCOME_PUBLIC_CHANNEL_ID)
        # Send the polished welcome embed after role assignment
        if welcome_channel:
            # Get the member's interest roles
            interest_role_names = []
            for role_name, role_id in INTEREST_ROLES.items():
                role = discord.utils.get(guild.roles, id=role_id)
                if role and role in member.roles:
                    interest_role_names.append(role_name)
            # Random welcome message with username
            welcome_message = random.choice(WELCOME_MESSAGES).format(name=member.display_name)
            embed = discord.Embed(
                title=f"🎉 Welcome to {guild.name}, {member.display_name}!",
                description=welcome_message,
                color=PINK
            )
            embed.add_field(
                name="🎨 Your Interests",
                value="\n".join([f"• {interest}" for interest in interest_role_names]) if interest_role_names else "None selected",
                inline=True
            )
            embed.add_field(
                name="📅 Joined At",
                value=member.joined_at.strftime("%B %d, %Y"),
                inline=True
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            embed.set_footer(text="Powered by Haze World 💖", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            try:
                view = WelcomeCardView(member, cog=self.cog)
                mention_msg = await welcome_channel.send(member.mention)
                embed_msg = await welcome_channel.send(embed=embed, view=view)
                view.message = embed_msg  # Store the message for editing on timeout
                # Store the sent messages for cleanup
                if member.id not in self.cog.sent_messages:
                    self.cog.sent_messages[member.id] = []
                self.cog.sent_messages[member.id].extend([mention_msg, embed_msg])
                Logger.info(f"Sent polished welcome embed for {member} in {welcome_channel}")
                channel_link = f"https://discord.com/channels/{guild.id}/{welcome_channel.id}"
                response_text = (
                    f"You accepted the rules and are now unlocked! 🎉\n"
                    f"Check out your welcome card: {welcome_channel.mention} or [Click here]({channel_link})"
                )
            except Exception as e:
                Logger.error(f"Error sending welcome embed: {e}")
                response_text = "You accepted the rules and are now unlocked! 🎉 (But I couldn't send a welcome card.)"
        else:
            Logger.warning(f"Public welcome channel not found (ID: {WELCOME_PUBLIC_CHANNEL_ID})")
            response_text = "You accepted the rules and are now unlocked! 🎉"
        await interaction.followup.send(response_text, ephemeral=True)
        # Stop the view to prevent timeout
        self.parent_view.stop()
        # Delete the rules message after 10 seconds
        if self.parent_view.rules_msg:
            await self.parent_view.rules_msg.delete(delay=10)
        # Also delete the mention message immediately
        if self.cog and self.member.id in self.cog.active_rules_messages:
            mention_msg = self.cog.active_rules_messages[self.member.id][0]
            await mention_msg.delete()  # Delete immediately
            # Clean up the dict after successful acceptance
            del self.cog.active_rules_messages[self.member.id]

        # Nach view.message = embed_msg
        import json, os  # Importiere hier oder oben
        persistent_views_file = self.cog.persistent_views_file
        os.makedirs(os.path.dirname(persistent_views_file), exist_ok=True)
        persistent_data = {
            'member_id': member.id,
            'channel_id': welcome_channel.id,
            'message_id': embed_msg.id,
            'start_time': view.start_time.isoformat()
        }
        with open(persistent_views_file, 'r') as f:
            data = json.load(f)
        data.append(persistent_data)
        with open(persistent_views_file, 'w') as f:
            json.dump(data, f)

class AcceptRulesView(discord.ui.View):
    """
    Interactive view with interest selection first, then accept rules button.
    Times out after 15 minutes and kicks the user if not accepted.
    Deletes the rules message.
    """
    def __init__(self, member, rules_msg=None, cog=None):
        super().__init__(timeout=900)  # 15 minutes
        self.member = member
        self.interest_selected = False
        self.rules_msg = rules_msg  # Store the rules message object
        self.cog = cog  # Reference to the cog for cleanup
        self.bot = cog.bot if cog else None  # Store bot reference
        self.add_item(InterestSelect(self))  # Dropdown first
        self.add_item(AcceptRulesButton(self))  # Button second

    async def on_timeout(self):
        """
        Called when the view times out (15 minutes).
        Kicks the user if they haven't accepted the rules and are still in the server.
        Deletes the rules messages.
        """
        Logger.info(f"Rules acceptance timed out for: {self.member.display_name} ({self.member.id})")  # Added logging for timeouts
        guild = self.member.guild
        if self.member in guild.members:
            try:
                await self.member.kick(reason="Did not accept rules within 15 minutes")
                Logger.info(f"Kicked {self.member.display_name} ({self.member.id}) for not accepting rules in time")
            except Exception as e:
                Logger.error(f"Failed to kick {self.member}: {e}")
        else:
            Logger.info(f"{self.member.display_name} ({self.member.id}) left the server before the 15-minute timeout")
        
        # Always delete the rules messages
        if self.cog:
            messages = self.cog.active_rules_messages.pop(self.member.id, [])  # Safe removal with pop
            for msg in messages:
                try:
                    await msg.delete()
                    Logger.info(f"Deleted rules message for {self.member.display_name} ({self.member.id}) (timeout/leave)")
                except Exception as e:
                    Logger.warning(f"Could not delete rules message for {self.member.display_name} ({self.member.id}): {e}")
        
        # Also delete the rules_msg if set
        if self.rules_msg:
            try:
                await self.rules_msg.delete()
            except Exception:
                pass

class WelcomeCardView(discord.ui.View):
    """
    Persistent view for the welcome card with a welcome button for others.
    Times out after 1 week to reduce bot load.
    """
    def __init__(self, new_member, cog=None, start_time=None):
        from datetime import datetime  # Importiere hier oder oben
        if start_time:
            elapsed = (datetime.now() - start_time).total_seconds()
            remaining = 604800 - elapsed
            timeout = max(remaining, 0)
        else:
            timeout = 604800
        super().__init__(timeout=timeout)
        self.new_member = new_member
        self.cog = cog  # Store cog reference
        self.start_time = start_time or datetime.now()
        self.add_item(WelcomeButton(self))

    async def on_timeout(self):
        """
        Called when the view times out (1 week).
        Disables the button to reduce bot load.
        """
        for item in self.children:
            item.disabled = True
        # Try to edit the message to show disabled button
        if hasattr(self, 'message') and self.message:
            try:
                await self.message.edit(view=self)
            except Exception as e:
                Logger.error(f"Failed to disable welcome button: {e}")
        # Remove from persistent data
        import json  # Importiere hier oder oben
        persistent_views_file = self.cog.persistent_views_file  # Use cog's attribute instead of self
        os.makedirs(os.path.dirname(persistent_views_file), exist_ok=True)
        try:
            with open(persistent_views_file, 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = []
        data = [d for d in data if not (d['message_id'] == self.message.id)]
        with open(persistent_views_file, 'w') as f:
            json.dump(data, f)

class WelcomeButton(discord.ui.Button):
    """
    Button for others to welcome the new member.
    """
    def __init__(self, parent_view):
        super().__init__(label="Welcome!", style=discord.ButtonStyle.primary, emoji="🎉")
        self.parent_view = parent_view
        self.cog = parent_view.cog  # Get cog from parent view

    async def callback(self, interaction: discord.Interaction):
        # Defer the response to allow followup
        await interaction.response.defer()  # Defer to allow followup
        user = interaction.user
        if user == self.parent_view.new_member:
            await interaction.followup.send("You can't welcome yourself! 😄", ephemeral=True)
            return
        # Fun welcome replies with inventory vibe (no mention for welcomer)
        welcome_replies = [
            f"Inventory alert: {user.display_name} welcomes {self.parent_view.new_member.mention} to the chillventory! 📦",
            f"{user.display_name} adds a warm welcome to {self.parent_view.new_member.mention}'s inventory! 🤗",
            f"New stock in the lounge: {user.display_name} welcomes {self.parent_view.new_member.mention}! 🛋️",
            f"{user.display_name} unlocks extra vibes for {self.parent_view.new_member.mention}! ✨",
            f"Chillventory update: {user.display_name} says hi to {self.parent_view.new_member.mention}! 😎",
            f"{user.display_name} throws positivity confetti for {self.parent_view.new_member.mention}! 🎊",
            f"Welcome stash expanded: {user.display_name} greets {self.parent_view.new_member.mention}! 🌟",
            f"{user.display_name} shares good mood from the inventory with {self.parent_view.new_member.mention}! 😁",
            f"Realm of relaxation welcomes {self.parent_view.new_member.mention} via {user.display_name}! 🧘",
            f"{user.display_name} discovers {self.parent_view.new_member.mention} in the positivity inventory! 🌿",
        ]
        reply = random.choice(welcome_replies)
        reply_msg = await interaction.followup.send(reply)
        # Store the reply message for cleanup
        member_id = self.parent_view.new_member.id
        if member_id not in self.cog.sent_messages:
            self.cog.sent_messages[member_id] = []
        self.cog.sent_messages[member_id].append(reply_msg)
        Logger.info(f"{user} welcomed {self.parent_view.new_member} via button")

class Welcome(commands.Cog):
    """
    Cog for welcoming new members and handling rule acceptance.
    """
    def __init__(self, bot):
        self.bot = bot
        self.active_rules_messages = {}  # Store active rules messages by member ID
        self.sent_messages = {}  # Store all sent welcome-related messages by member ID for cleanup
        # Neue Zeilen:
        import json, os  # Importiere hier oder oben
        self.persistent_views_file = PERSISTENT_VIEWS_FILE
        if os.path.exists(self.persistent_views_file):
            with open(self.persistent_views_file, 'r') as f:
                self.persistent_views_data = json.load(f)
        else:
            os.makedirs(os.path.dirname(self.persistent_views_file), exist_ok=True)
            self.persistent_views_data = []

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """
        Event: Triggered when a new member joins the server.
        Sends rules embed and interactive view.
        """
        Logger.info(f"New member joined: {member.display_name} ({member.id})")  # Added logging for joins
        guild = member.guild
        rules_channel = guild.get_channel(WELCOME_RULES_CHANNEL_ID)
        if rules_channel:
            embed = discord.Embed(
                title=f"Welcome to {guild.name} ! 💖",
                description=(
                    f"Hey there, glad to have you here!\n\n"  # Removed mention from description
                    f"**Server Rules:**\n{RULES_TEXT}\n\n"
                    "**Follow these steps to unlock the server:**\n"
                    "1. Select how you want to contribute (you can choose multiple).\n"
                    "2. Click 'Accept Rules' to agree and get access!\n\n"
                    "⏰ **Note:** You have **15 minutes** to complete this. If not, you'll be kicked from the server.\n"
                    "📝 **Privacy:** This message is public, but your selections and responses are only visible to you."
                ),
                color=PINK
            )
            set_pink_footer(embed, bot=self.bot.user)
            view = AcceptRulesView(member, cog=self)
            # Send separate mention message first
            mention_msg = await rules_channel.send(member.mention)
            # Then send the embed with view
            rules_msg = await rules_channel.send(embed=embed, view=view)
            view.rules_msg = rules_msg
            # Store both messages for cleanup
            self.active_rules_messages[member.id] = [mention_msg, rules_msg]

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """
        Event: Triggered when a member leaves the server.
        Deletes the rules messages and all welcome-related messages if they exist.
        """
        # Delete rules messages
        messages = self.active_rules_messages.pop(member.id, [])  # Safe removal with pop
        deleted_count = 0
        for msg in messages:
            try:
                await msg.delete()
                deleted_count += 1
            except Exception as e:
                Logger.warning(f"Could not delete rules message for {member}: {e}")
        if deleted_count > 0:
            Logger.info(f"Deleted {deleted_count} rules message(s) for {member.display_name} ({member.id}) who left the server")
        
        # Delete all sent welcome messages
        sent_msgs = self.sent_messages.pop(member.id, [])  # Safe removal with pop
        deleted_welcome_count = 0
        for msg in sent_msgs:
            try:
                await msg.delete()
                deleted_welcome_count += 1
            except Exception as e:
                Logger.error(f"Failed to delete welcome message for {member}: {e}")
        if deleted_welcome_count > 0:
            Logger.info(f"Deleted {deleted_welcome_count} welcome message(s) for {member.display_name} ({member.id}) who left the server")

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Restore persistent views when the bot is ready.
        """
        restored_count = 0
        for data in self.persistent_views_data:
            channel = self.bot.get_channel(data['channel_id'])
            if channel:
                try:
                    message = await channel.fetch_message(data['message_id'])
                    from datetime import datetime
                    start_time = datetime.fromisoformat(data['start_time'])
                    member = self.bot.get_user(data['member_id'])  # Oder None, wenn nicht gefunden
                    view = WelcomeCardView(member, cog=self, start_time=start_time)
                    view.message = message
                    # Check if the view is already attached to avoid unnecessary edits
                    if not message.components or not any(isinstance(comp, discord.ui.View) for comp in message.components):
                        await message.edit(view=view)
                        restored_count += 1
                    else:
                        restored_count += 1  # Still count as restored if no edit needed
                    await asyncio.sleep(6)  # Increased sleep to avoid rate limits (adjust as needed)
                except Exception as e:
                    Logger.error(f"Failed to restore view for message {data['message_id']}: {e}")
        Logger.info(f"Restored {restored_count} persistent views.")

async def setup(bot):
    """
    Setup function to add the Welcome cog.
    """
    await bot.add_cog(Welcome(bot))