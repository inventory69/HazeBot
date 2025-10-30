import random
import asyncio
import os
import json
from datetime import datetime
from discord.ext import commands
import discord
from typing import Optional, Any
from Config import (
    PINK,
    INTEREST_ROLES,
    WELCOME_RULES_CHANNEL_ID,
    WELCOME_PUBLIC_CHANNEL_ID,
    MEMBER_ROLE_ID,
    PERSISTENT_VIEWS_FILE,
    ACTIVE_RULES_VIEWS_FILE,
)
from Utils.EmbedUtils import set_pink_footer
import logging

logger = logging.getLogger(__name__)

# Polished rules text shown to new members
RULES_TEXT = (
    "🌿 **1. Be kind and respectful to everyone.**\n"
    "✨ **2. No spam, flooding, or excessive self-promotion.**\n"
    "🔞 **3. NSFW content is permitted only inside a clearly labeled, age-verified channel.**\n"
    "🚫 **4. Illegal content and hate speech are strictly forbidden anywhere on the server.**\n"
    "🧑‍💼 **5. Follow the instructions of staff and moderators.**\n"
    "💖 **6. Keep the atmosphere calm, considerate, and positive.**\n\n"
    "By clicking 'Accept Rules' you agree to these guidelines and unlock full access to the server. Welcome to the lounge — enjoy your stay!"
)

# Funny welcome messages for public channel (use {name} for username)
WELCOME_MESSAGES = [
    "Welcome {name}! The chill inventory just gained a legendary item — you. 🌿",
    "Hey {name}, you unlocked the secret stash of good vibes. Proceed to sofa extraction. ✨🛋️",
    "{name} has joined the inventarium. Claim your complimentary imaginary hammock. 😎",
    "Give it up for {name}, our newest collector of zen moments and midnight memes. 🧘‍♂️🔥",
    "{name}, you found the legendary lounge zone — free snacks not included but vibes guaranteed. 🚀",
    "Inventory update: {name} added. Please store your worries in the lost-and-found. 😁",
    "Alert: {name} has entered the realm of ultimate relaxation. Please mind the plants. 🌱",
    "Welcome {name}! May your inventory be full of chill, memes, and excellent tea. 🎉🍵",
    "New item in stock: {name}, the ultimate chill curator. Limited edition energy. 📦✨",
    "{name} discovered the hidden lounge of positivity — badge unlocked, mission: unwind. 🌟"
]


class InterestSelect(discord.ui.Select):
    """
    Dropdown for user interests. Selection is required before accepting rules.
    """

    def __init__(self, parent_view: Any) -> None:
        self.parent_view = parent_view
        options = [
            discord.SelectOption(
                label="Chat & Memes",
                emoji="💬",
                description="Talk, joke, and share memes",
            ),
            discord.SelectOption(
                label="Creative Vibes",
                emoji="🎨",
                description="Art, music, writing, and more",
            ),
            discord.SelectOption(
                label="Gaming & Chill",
                emoji="🎮",
                description="Play games and hang out",
            ),
            discord.SelectOption(
                label="Ideas & Projects",
                emoji="💡",
                description="Brainstorm and build together",
            ),
            discord.SelectOption(
                label="Development",
                emoji="🖥️",
                description="Coding, programming, and dev talk",
            ),
            discord.SelectOption(
                label="Tech & Support",
                emoji="🛠️",
                description="Tech talk and help others",
            ),
            discord.SelectOption(
                label="Just Browsing",
                emoji="👀",
                description="Just here to read and vibe",
            ),
        ]
        super().__init__(
            placeholder="Step 1: Select how you want to contribute",
            min_values=1,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
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
            ephemeral=True,
        )


class AcceptRulesButton(discord.ui.Button):
    """
    Button for accepting rules.
    """

    def __init__(self, parent_view: Any) -> None:
        super().__init__(label="Step 2: Accept Rules", style=discord.ButtonStyle.success, emoji="✅")
        self.parent_view = parent_view
        self.bot = parent_view.bot  # Get bot reference from parent view
        self.cog = parent_view.cog  # Get cog reference from parent view
        self.member = parent_view.member  # Get member reference from parent view

    async def callback(self, interaction: discord.Interaction) -> None:
        # Defer the response to avoid timeout
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        member = interaction.user
        if not self.parent_view.interest_selected:
            await interaction.followup.send(
                "Please select at least one way you want to contribute before accepting the rules.",
                ephemeral=True,
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
                color=PINK,
            )
            embed.add_field(
                name="🎨 Your Interests",
                value="\n".join([f"• {interest}" for interest in interest_role_names])
                if interest_role_names
                else "None selected",
                inline=True,
            )
            embed.add_field(
                name="📅 Joined At",
                value=member.joined_at.strftime("%B %d, %Y"),
                inline=True,
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            embed.set_footer(
                text="Powered by Haze World 💖",
                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None,
            )
            try:
                view = WelcomeCardView(member, cog=self.cog)
                mention_msg = await welcome_channel.send(member.mention)
                embed_msg = await welcome_channel.send(embed=embed, view=view)
                view.message = embed_msg  # Store the message for editing on timeout
                # Store the sent messages for cleanup
                if member.id not in self.cog.sent_messages:
                    self.cog.sent_messages[member.id] = []
                self.cog.sent_messages[member.id].extend([mention_msg, embed_msg])
                logger.info(f"Sent polished welcome embed for {member} in {welcome_channel}")
                channel_link = f"https://discord.com/channels/{guild.id}/{welcome_channel.id}"
                response_text = (
                    f"You accepted the rules and are now unlocked! 🎉\n"
                    f"Check out your welcome card: {welcome_channel.mention} or [Click here]({channel_link})"
                )
            except Exception as e:
                logger.error(f"Error sending welcome embed: {e}")
                response_text = "You accepted the rules and are now unlocked! 🎉 (But I couldn't send a welcome card.)"
        else:
            logger.warning(f"Public welcome channel not found (ID: {WELCOME_PUBLIC_CHANNEL_ID})")
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
        persistent_views_file = self.cog.persistent_views_file
        os.makedirs(os.path.dirname(persistent_views_file), exist_ok=True)
        persistent_data = {
            "member_id": member.id,
            "channel_id": welcome_channel.id,
            "message_id": embed_msg.id,
            "start_time": view.start_time.isoformat(),
        }
        with open(persistent_views_file, "r") as f:
            data = json.load(f)
        data.append(persistent_data)
        with open(persistent_views_file, "w") as f:
            json.dump(data, f)


class AcceptRulesView(discord.ui.View):
    """
    Interactive view with interest selection first, then accept rules button.
    Times out after 15 minutes and kicks the user if not accepted.
    Deletes the rules message.
    """

    def __init__(
        self, member: discord.Member, rules_msg: Optional[discord.Message] = None, cog: Optional[Any] = None
    ) -> None:
        self.start_time = datetime.now()  # Store start time
        super().__init__(timeout=900)  # 15 minutes
        self.member = member
        self.interest_selected = False
        self.rules_msg = rules_msg  # Store the rules message object
        self.cog = cog  # Reference to the cog for cleanup
        self.bot = cog.bot if cog else None  # Store bot reference
        self.add_item(InterestSelect(self))  # Dropdown first
        self.add_item(AcceptRulesButton(self))  # Button second

    async def on_timeout(self) -> None:
        """
        Called when the view times out (15 minutes).
        Kicks the user if they haven't accepted the rules and are still in the server.
        Deletes the rules messages.
        """
        logger.info(
            f"Rules acceptance timed out for: {self.member.display_name} ({self.member.id})"
        )  # Added logging for timeouts
        guild = self.member.guild
        if self.member in guild.members:
            try:
                await self.member.kick(reason="Did not accept rules within 15 minutes")
                logger.info(f"Kicked {self.member.display_name} ({self.member.id}) for not accepting rules in time")
            except Exception as e:
                logger.error(f"Failed to kick {self.member}: {e}")
        else:
            logger.info(f"{self.member.display_name} ({self.member.id}) left the server before the 15-minute timeout")

        # Always delete the rules messages
        if self.cog:
            messages = self.cog.active_rules_messages.pop(self.member.id, [])  # Safe removal with pop
            for msg in messages:
                try:
                    await msg.delete()
                    logger.info(
                        f"Deleted rules message for {self.member.display_name} ({self.member.id}) (timeout/leave)"
                    )
                except Exception as e:
                    logger.warning(
                        f"Could not delete rules message for {self.member.display_name} ({self.member.id}): {e}"
                    )

        # Remove from persistent data
        if self.cog:
            self.cog.active_rules_views_data = [
                d for d in self.cog.active_rules_views_data if not (d["member_id"] == self.member.id)
            ]
            with open(self.cog.active_rules_views_file, "w") as f:
                json.dump(self.cog.active_rules_views_data, f)


class WelcomeCardView(discord.ui.View):
    """
    Persistent view for the welcome card with a welcome button for others.
    Times out after 1 week to reduce bot load.
    """

    def __init__(
        self, new_member: discord.Member, cog: Optional[Any] = None, start_time: Optional[datetime] = None
    ) -> None:
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

    async def on_timeout(self) -> None:
        """
        Called when the view times out (1 week).
        Disables the button to reduce bot load.
        """
        for item in self.children:
            item.disabled = True
        # Try to edit the message to show disabled button
        if hasattr(self, "message") and self.message:
            try:
                await self.message.edit(view=self)
            except Exception as e:
                logger.error(f"Failed to disable welcome button: {e}")
        # Remove from persistent data
        persistent_views_file = self.cog.persistent_views_file  # Use cog's attribute instead of self
        os.makedirs(os.path.dirname(persistent_views_file), exist_ok=True)
        try:
            with open(persistent_views_file, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = []
        data = [d for d in data if not (d["message_id"] == self.message.id)]
        with open(persistent_views_file, "w") as f:
            json.dump(data, f)


class WelcomeButton(discord.ui.Button):
    """
    Button for others to welcome the new member.
    """

    def __init__(self, parent_view: Any) -> None:
        super().__init__(label="Welcome!", style=discord.ButtonStyle.primary, emoji="🎉")
        self.parent_view = parent_view
        self.cog = parent_view.cog  # Get cog from parent view

    async def callback(self, interaction: discord.Interaction) -> None:
        # Defer the response to allow followup
        await interaction.response.defer()  # Defer to allow followup
        user = interaction.user
        if user == self.parent_view.new_member:
            await interaction.followup.send("You can't welcome yourself! 😄", ephemeral=True)
            return
        # Epic welcome replies with maximum inventory vibes ✨
        welcome_replies = [
            f"🎊 **LEGENDARY DROP!** {user.mention} just summoned {self.parent_view.new_member.mention} into the chillventory vault! 📦",
            f"✨ {user.mention} equipped {self.parent_view.new_member.mention} with *Infinite Good Vibes +99* — welcome buff activated! 💫",
            f"📦 **New inventory slot unlocked!** {user.mention} warmly stores {self.parent_view.new_member.mention} in the premium lounge section! 🛋️",
            f"🌟 Achievement unlocked: {user.mention} successfully welcomed {self.parent_view.new_member.mention}! Friendship XP +100 🎮",
            f"🛋️ **Sofa reservation confirmed!** {user.mention} rolls out the red carpet for {self.parent_view.new_member.mention}! 🎭",
            f"🎨 {user.mention} adds a splash of positivity paint to {self.parent_view.new_member.mention}'s welcome canvas! Masterpiece! 🖼️",
            f"🌿 **Rare plant spotted!** {user.mention} places {self.parent_view.new_member.mention} in the zen garden of eternal chill! 🧘",
            f"🎉 {user.mention} throws legendary confetti bombs for {self.parent_view.new_member.mention}! The lounge is now 200% more sparkly! ✨",
            f"🔥 **Epic combo!** {user.mention} + {self.parent_view.new_member.mention} = Maximum vibes unlocked! The inventory is blessed! 🙏",
            f"💎 {user.mention} just found a rare gem: {self.parent_view.new_member.mention}! Added to the collection of awesome people! 💖",
            f"🚀 **Mission success!** Agent {user.mention} has secured {self.parent_view.new_member.mention} for the chill squad! Welcome aboard! 🎯",
            f"🧘 {user.mention} transmits good energy waves to {self.parent_view.new_member.mention}! Harmony level: MAXIMUM! 🌊",
        ]
        reply = random.choice(welcome_replies)
        reply_msg = await interaction.followup.send(reply)
        # Store the reply message for cleanup
        member_id = self.parent_view.new_member.id
        if member_id not in self.cog.sent_messages:
            self.cog.sent_messages[member_id] = []
        self.cog.sent_messages[member_id].append(reply_msg)
        logger.info(f"{user} welcomed {self.parent_view.new_member} via button")


class Welcome(commands.Cog):
    """
    Cog for welcoming new members and handling rule acceptance.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_rules_messages = {}  # Store active rules messages by member ID
        self.sent_messages = {}  # Store all sent welcome-related messages by member ID for cleanup
        # New lines:
        self.persistent_views_file = PERSISTENT_VIEWS_FILE
        if os.path.exists(self.persistent_views_file):
            with open(self.persistent_views_file, "r") as f:
                self.persistent_views_data = json.load(f)
        else:
            os.makedirs(os.path.dirname(self.persistent_views_file), exist_ok=True)
            self.persistent_views_data = []

        # New lines for active_rules_views
        self.active_rules_views_file = ACTIVE_RULES_VIEWS_FILE
        if os.path.exists(self.active_rules_views_file):
            with open(self.active_rules_views_file, "r") as f:
                self.active_rules_views_data = json.load(f)
        else:
            os.makedirs(os.path.dirname(self.active_rules_views_file), exist_ok=True)
            self.active_rules_views_data = []

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """
        Event: Triggered when a new member joins the server.
        Sends rules embed and interactive view.
        """
        logger.info(f"New member joined: {member.display_name} ({member.id})")  # Added logging for joins
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
                color=PINK,
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

            # New lines: Remove old entries for this member to avoid duplicates
            self.active_rules_views_data = [d for d in self.active_rules_views_data if d["member_id"] != member.id]
            # Save view data persistently, including mention_message_id
            active_data = {
                "member_id": member.id,
                "channel_id": rules_channel.id,
                "message_id": rules_msg.id,
                "mention_message_id": mention_msg.id,
                "start_time": view.start_time.isoformat(),  # Use start_time from View
            }
            self.active_rules_views_data.append(active_data)
            with open(self.active_rules_views_file, "w") as f:
                json.dump(self.active_rules_views_data, f)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
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
                logger.warning(f"Could not delete rules message for {member}: {e}")
        if deleted_count > 0:
            logger.info(
                f"Deleted {deleted_count} rules message(s) for {member.display_name} ({member.id}) who left the server"
            )

        # Delete all sent welcome messages
        sent_msgs = self.sent_messages.pop(member.id, [])  # Safe removal with pop
        deleted_welcome_count = 0
        for msg in sent_msgs:
            try:
                await msg.delete()
                deleted_welcome_count += 1
            except Exception as e:
                logger.error(f"Failed to delete welcome message for {member}: {e}")
        if deleted_welcome_count > 0:
            logger.info(
                f"Deleted {deleted_welcome_count} welcome message(s) for {member.display_name} ({member.id}) who left the server"
            )

        # New lines: Remove from active_rules_views_data
        self.active_rules_views_data = [d for d in self.active_rules_views_data if d["member_id"] != member.id]
        with open(self.active_rules_views_file, "w") as f:
            json.dump(self.active_rules_views_data, f)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """
        Restore persistent views when the bot is ready.
        """
        restored_count = 0
        cleaned_persistent_views_data = []  # New list for cleaned data
        for data in self.persistent_views_data:
            channel = self.bot.get_channel(data["channel_id"])
            if channel:
                try:
                    message = await channel.fetch_message(data["message_id"])
                    start_time = datetime.fromisoformat(data["start_time"])
                    member = self.bot.get_user(data["member_id"])  # Oder None, wenn nicht gefunden
                    view = WelcomeCardView(member, cog=self, start_time=start_time)
                    view.message = message
                    # Check if the view is already attached to avoid unnecessary edits
                    if not message.components or not any(
                        isinstance(comp, discord.ui.View) for comp in message.components
                    ):
                        await message.edit(view=view)
                        restored_count += 1
                        cleaned_persistent_views_data.append(data)  # Keep valid entries
                    else:
                        restored_count += 1  # Still count as restored if no edit needed
                        cleaned_persistent_views_data.append(data)  # Keep valid entries
                    await asyncio.sleep(5)  # Increased sleep to avoid rate limits (adjust as needed)
                except discord.NotFound:
                    # Message no longer exists, skip and remove from data
                    logger.warning(f"Message {data['message_id']} not found, removing from persistent views data.")
                except Exception as e:
                    logger.error(f"Failed to restore view for message {data['message_id']}: {e}")
                    cleaned_persistent_views_data.append(data)  # Keep on other errors
            else:
                cleaned_persistent_views_data.append(data)  # Keep if channel not found
        # Save the cleaned list
        self.persistent_views_data = cleaned_persistent_views_data
        with open(self.persistent_views_file, "w") as f:
            json.dump(self.persistent_views_data, f)
        logger.info(f"Restored {restored_count} persistent welcome views.")

        # Restore active_rules_views
        restored_rules_count = 0  # Separate counter
        cleaned_active_rules_views_data = []  # New list for cleaned data
        for data in self.active_rules_views_data:
            channel = self.bot.get_channel(data["channel_id"])
            if channel:
                try:
                    rules_msg = await channel.fetch_message(data["message_id"])
                    mention_msg = await channel.fetch_message(data["mention_message_id"])
                    start_time = datetime.fromisoformat(data["start_time"])
                    member = channel.guild.get_member(data["member_id"])  # Get member from guild instead of user
                    if member:
                        view = AcceptRulesView(member, rules_msg=rules_msg, cog=self)
                        view.start_time = start_time  # Set start_time
                        # Calculate remaining timeout time
                        elapsed = (datetime.now() - start_time).total_seconds()
                        remaining = 900 - elapsed  # 15 minutes = 900 seconds
                        if remaining > 0:
                            view.timeout = remaining
                            await rules_msg.edit(view=view)
                            restored_rules_count += 1
                            cleaned_active_rules_views_data.append(data)  # Keep valid entries
                            # Restore active_rules_messages
                            self.active_rules_messages[data["member_id"]] = [
                                mention_msg,
                                rules_msg,
                            ]
                        else:
                            # Timeout bereits erreicht, trigger on_timeout
                            await view.on_timeout()
                    await asyncio.sleep(5)  # Sleep to avoid rate limits
                except discord.NotFound:
                    # Message no longer exists, skip and remove from data
                    logger.warning(
                        f"Message {data['message_id']} or mention message not found, removing from active rules views data."
                    )
                except Exception as e:
                    logger.error(f"Failed to restore rules view for message {data['message_id']}: {e}")
                    cleaned_active_rules_views_data.append(data)  # Keep on other errors
            else:
                cleaned_active_rules_views_data.append(data)  # Keep if channel not found
        # Save the cleaned list
        self.active_rules_views_data = cleaned_active_rules_views_data
        with open(self.active_rules_views_file, "w") as f:
            json.dump(self.active_rules_views_data, f)
        logger.info(f"Restored {restored_rules_count} active rules views.")


async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the Welcome cog.
    """
    await bot.add_cog(Welcome(bot))
