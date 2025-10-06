import random
from discord.ext import commands
import discord
from Config import PINK
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

# Channel and role IDs (replace with your actual IDs)
WELCOME_RULES_CHANNEL_ID = 1424162976247582862  # Channel where rules are shown
WELCOME_PUBLIC_CHANNEL_ID = 1424164269775392858  # Public welcome channel
MEMBER_ROLE_ID = 1424161475718807562            # Member role ID

# Improved interest roles mapping (replace IDs with your actual role IDs)
INTEREST_ROLES = {
    "Chat & Memes": 1424465865297887345,
    "Creative Vibes": 1424465951792828477,
    "Gaming & Chill": 1424466003102007359,
    "Ideas & Projects": 1424466081547817183,
    "Development": 1424466456866852956,
    "Tech & Support": 1424466150330466434,
    "Just Browsing": 1424466239618810019,
}

# Funny welcome messages for public channel
WELCOME_MESSAGES = [
    "Welcome {mention}! Your chillventory just gained a new member. 🌿",
    "Hey {mention}, you unlocked the secret stash of good vibes! ✨",
    "{mention} joined the inventarium. Time to relax and enjoy! 😎",
    "Give a warm welcome to {mention}, our newest collector of chill moments! 🧘",
    "{mention}, you found the legendary lounge zone. Welcome aboard! 🚀",
    "Inventory update: {mention} added. Please store your good mood here! 😁",
    "Alert: {mention} has entered the realm of ultimate relaxation. 🛋️",
    "Welcome {mention}! May your inventory always be full of chill and fun. 🎉"
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

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        if not self.parent_view.interest_selected:
            await interaction.response.send_message(
                "Please select at least one way you want to contribute before accepting the rules.",
                ephemeral=True
            )
            return
        role = discord.utils.get(guild.roles, id=MEMBER_ROLE_ID)
        # Add the role if not present
        if role and role not in member.roles:
            await member.add_roles(role, reason="Accepted rules")
        welcome_channel = guild.get_channel(WELCOME_PUBLIC_CHANNEL_ID)
        # Send the public welcome message after role assignment
        if welcome_channel:
            message = random.choice(WELCOME_MESSAGES).format(mention=member.mention)
            try:
                public_msg = await welcome_channel.send(message)
                Logger.info(f"Sent public welcome message for {member} in {welcome_channel}")
                channel_link = f"https://discord.com/channels/{guild.id}/{welcome_channel.id}"
                response_text = (
                    f"You accepted the rules and are now unlocked! 🎉\n"
                    f"Jump to the welcome channel: {welcome_channel.mention} or [Click here]({channel_link})"
                )
            except Exception as e:
                Logger.error(f"Error sending public welcome message: {e}")
                response_text = "You accepted the rules and are now unlocked! 🎉 (But I couldn't send a public welcome message.)"
        else:
            Logger.warning(f"Public welcome channel not found (ID: {WELCOME_PUBLIC_CHANNEL_ID})")
            response_text = "You accepted the rules and are now unlocked! 🎉"
        await interaction.response.send_message(response_text, ephemeral=True)
        # Stop the view to prevent timeout
        self.parent_view.stop()
        # Delete the rules message after 10 seconds
        if self.parent_view.rules_msg:
            await self.parent_view.rules_msg.delete(delay=10)

class AcceptRulesView(discord.ui.View):
    """
    Interactive view with interest selection first, then accept rules button.
    Times out after 15 minutes and kicks the user if not accepted.
    Deletes the rules message.
    """
    def __init__(self, member, rules_msg=None):
        super().__init__(timeout=30)  # 15 minutes (zurück zu 900)
        self.member = member
        self.interest_selected = False
        self.rules_msg = rules_msg  # Store the rules message object
        self.add_item(InterestSelect(self))  # Dropdown first
        self.add_item(AcceptRulesButton(self))  # Button second (unter dem Dropdown)

    async def on_timeout(self):
        """
        Called when the view times out (15 minutes).
        Kicks the user if they haven't accepted the rules and are still in the server.
        Deletes the rules message.
        """
        guild = self.member.guild
        if self.member in guild.members:
            try:
                await self.member.kick(reason="Did not accept rules within 15 minutes")
                Logger.info(f"Kicked {self.member} for not accepting rules in time")
            except Exception as e:
                Logger.error(f"Failed to kick {self.member}: {e}")
        else:
            Logger.info(f"{self.member} left the server before the 15-minute timeout")
        
        # Always delete the rules message
        if self.rules_msg:
            try:
                await self.rules_msg.delete()
                Logger.info("Deleted rules message after timeout")
            except Exception as e:
                Logger.error(f"Failed to delete rules message: {e}")

class Welcome(commands.Cog):
    """
    Cog for welcoming new members and handling rule acceptance.
    """
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """
        Event: Triggered when a new member joins the server.
        Sends rules embed and interactive view.
        """
        guild = member.guild
        rules_channel = guild.get_channel(WELCOME_RULES_CHANNEL_ID)
        if rules_channel:
            embed = discord.Embed(
                title=f"Welcome to {guild.name}! 💖",
                description=(
                    f"Hey {member.mention}, glad to have you here!\n\n"
                    f"**Server Rules:**\n{RULES_TEXT}\n\n"
                    "**Follow these steps to unlock the server:**\n"
                    "1. Select how you want to contribute (you can choose multiple).\n"
                    "2. Click 'Accept Rules' to agree and get access!\n\n"
                    "⏰ **Note:** You have **15 minutes** to complete this. If not, you'll be kicked from the server."
                ),
                color=PINK
            )
            set_pink_footer(embed, bot=self.bot.user)
            view = AcceptRulesView(member)
            # Save the sent message object and pass it to the view
            rules_msg = await rules_channel.send(embed=embed, view=view)
            view.rules_msg = rules_msg

async def setup(bot):
    """
    Setup function to add the Welcome cog.
    """
    await bot.add_cog(Welcome(bot))