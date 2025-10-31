import discord
from discord.ext import commands
from Config import ADMIN_ROLE_ID, PINK, MEME_CHANNEL_ID
from Utils.EmbedUtils import set_pink_footer
import logging

logger = logging.getLogger(__name__)


class CommandButtonView(discord.ui.View):
    """Persistent view with buttons that trigger slash commands"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Help", style=discord.ButtonStyle.primary, emoji="❓", custom_id="guide_help_button")
    async def help_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Trigger /help command"""
        # Get the help command
        help_cog = interaction.client.get_cog("Utility")
        if help_cog and hasattr(help_cog, "create_help_embed"):
            # Check if user is admin/mod
            is_admin = any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)
            embed = help_cog.create_help_embed(interaction, is_admin=is_admin)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Help button pressed by {interaction.user}")
        else:
            await interaction.response.send_message("❌ Help command not available.", ephemeral=True)

    @discord.ui.button(label="Ticket", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="guide_ticket_button")
    async def ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Trigger /ticket command"""
        # Import TicketView from TicketSystem
        try:
            from Cogs.TicketSystem import TicketView

            ticket_cog = interaction.client.get_cog("TicketSystem")
            if ticket_cog and hasattr(ticket_cog, "get_ticket_help_embed"):
                embed = ticket_cog.get_ticket_help_embed(interaction)
            else:
                # Fallback embed
                embed = discord.Embed(
                    title="🎫 Create Support Ticket",
                    description="Choose the type of support ticket:",
                    color=PINK,
                )
                set_pink_footer(embed, bot=interaction.client.user)

            await interaction.response.send_message(embed=embed, view=TicketView(), ephemeral=True)
            logger.info(f"Ticket button pressed by {interaction.user}")
        except ImportError:
            await interaction.response.send_message("❌ Ticket system not available.", ephemeral=True)

    @discord.ui.button(label="Profile", style=discord.ButtonStyle.primary, emoji="👤", custom_id="guide_profile_button")
    async def profile_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Trigger /profile command"""
        # Get the profile command
        profile_cog = interaction.client.get_cog("Profile")
        if profile_cog and hasattr(profile_cog, "create_profile_embed"):
            embed = await profile_cog.create_profile_embed(interaction.user)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Profile button pressed by {interaction.user}")
        else:
            await interaction.response.send_message("❌ Profile command not available.", ephemeral=True)

    @discord.ui.button(
        label="Rocket League", style=discord.ButtonStyle.primary, emoji="🚀", custom_id="guide_rocket_button"
    )
    async def rocket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Trigger /rocket command"""
        # Get the rocket league cog
        rl_cog = interaction.client.get_cog("RocketLeague")
        if rl_cog:
            # Call the rocket hub method
            await rl_cog.show_rocket_hub(interaction)
            logger.info(f"Rocket League hub button pressed by {interaction.user}")
        else:
            await interaction.response.send_message("❌ Rocket League system not available.", ephemeral=True)

    @discord.ui.button(
        label="Warframe", style=discord.ButtonStyle.primary, emoji="🎮", custom_id="guide_warframe_button"
    )
    async def warframe_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Trigger /warframe command"""
        # Get the warframe cog
        wf_cog = interaction.client.get_cog("Warframe")
        if wf_cog:
            # Call the warframe hub method
            await wf_cog.show_warframe_hub(interaction)
            logger.info(f"Warframe hub button pressed by {interaction.user}")
        else:
            await interaction.response.send_message("❌ Warframe system not available.", ephemeral=True)

    @discord.ui.button(
        label="Preferences", style=discord.ButtonStyle.success, emoji="⚙️", custom_id="guide_preferences_button", row=1
    )
    async def preferences_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Trigger /preferences command"""
        # Get the preferences cog (note: cog name is PreferencesSystem)
        pref_cog = interaction.client.get_cog("PreferencesSystem")
        if pref_cog and hasattr(pref_cog, "get_preferences_help_embed"):
            # Import PreferencesView
            from Cogs.Preferences import PreferencesView

            embed = pref_cog.get_preferences_help_embed(interaction, interaction.user)
            view = PreferencesView(interaction.user.id, interaction.guild)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            logger.info(f"Preferences button pressed by {interaction.user}")
        else:
            await interaction.response.send_message("❌ Preferences system not available.", ephemeral=True)

    @discord.ui.button(
        label="Meme", style=discord.ButtonStyle.secondary, emoji="🎭", custom_id="guide_meme_button", row=1
    )
    async def meme_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Meme Hub with channel posting enabled"""
        # Get the meme cog
        meme_cog = interaction.client.get_cog("DailyMeme")
        if not meme_cog:
            await interaction.response.send_message("❌ Meme system not available.", ephemeral=True)
            return

        # Import here to avoid circular imports
        from Cogs._DailyMemeViews import MemeHubView, is_mod_or_admin

        # Check if user is mod/admin
        is_admin_or_mod = is_mod_or_admin(interaction.user)

        # Create Meme Hub embed
        embed = discord.Embed(
            title="🎭 Meme Hub",
            description=(
                "Welcome to the Meme Hub! Get trending memes from multiple sources.\n\n"
                "**Available Sources:** Reddit, Lemmy\n"
                "**Memes will be posted to the meme channel!**\n"
                "**Rate Limit:** 10 seconds between requests"
                if not is_admin_or_mod
                else (
                    "**Mod/Admin Access:** Full management + no cooldown\n**Memes will be posted to the meme channel!**"
                )
            ),
            color=PINK,
        )

        if is_admin_or_mod:
            embed.add_field(
                name="🔧 Management",
                value=(
                    "Use the buttons below to:\n"
                    "• Get random memes (posted to meme channel)\n"
                    "• Choose specific source\n"
                    "• Manage subreddit sources\n"
                    "• Manage Lemmy communities\n"
                    "• Toggle meme sources"
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="📝 How to Use",
                value=(
                    "• **🎭 Get Random Meme** - Random from all sources\n"
                    "• **🎯 Choose Source** - Pick specific subreddit/community\n"
                    "*Memes will be posted to the meme channel*\n"
                    "*10 second cooldown between requests*"
                ),
                inline=False,
            )

        set_pink_footer(embed, bot=interaction.client.user)

        # Create view with channel posting enabled
        view = MemeHubView(meme_cog, is_admin_or_mod, post_to_channel_id=MEME_CHANNEL_ID)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"Meme Hub (channel posting) opened by {interaction.user} via Server Guide")


class ServerGuide(commands.Cog):
    """Helper cog for server guide message with command buttons"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="server-guide")
    async def server_guide(self, ctx: commands.Context):
        """
        📨 Send the server guide embed with command buttons.
        Only admins can use this command.
        """
        # Check admin permission
        if not any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles):
            embed = discord.Embed(
                description="🚫 You do not have permission to use this command.",
                color=discord.Color.red(),
            )
            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed, delete_after=5)
            return

        # Delete command message
        await ctx.message.delete()

        # Create welcome embed
        embed = discord.Embed(
            title="Welcome to the Chillventory! 🌟",
            color=PINK,
        )

        # Add banner image
        embed.set_image(
            url="https://cdn.discordapp.com/attachments/1424848960333414581/1433070391051550871/welcometochillventory.png?ex=69035a4e&is=690208ce&hm=5d57c1ca0b18e9bc3c839530d0211ca3da952e3af0fb4b4d45712d2d20dddfdd"
        )

        # Add sections
        embed.add_field(
            name="🎯 Get Started",
            value=(
                "Click the buttons below to access our most important features!\n\n"
                "• **Help** – View all available commands\n"
                "• **Ticket** – Create a support ticket\n"
                "• **Profile** – Check your server profile\n"
                "• **Rocket League** – Track your RL ranks\n"
                "• **Warframe** – Market & game status (Beta)\n"
                "• **Preferences** – Configure your opt-ins & settings\n"
                "• **Meme** – Get memes posted to the meme channel"
            ),
            inline=False,
        )

        embed.add_field(
            name="💡 Quick Tips",
            value=(
                "Use `/help` anytime to discover more commands.\n"
                "Need assistance? Create a ticket and our team will help you!"
            ),
            inline=False,
        )

        # Add footer
        set_pink_footer(embed, bot=self.bot.user, text=f"Powered by {ctx.guild.name} 💖")

        # Send with command buttons
        view = CommandButtonView()
        await ctx.send(embed=embed, view=view)

        logger.info(f"Server guide sent by {ctx.author} in {ctx.channel}")

    async def _setup_persistent_views(self):
        """Setup persistent views - called on ready and after reload"""
        self.bot.add_view(CommandButtonView())
        logger.info("ServerGuide cog ready. Persistent command buttons restored.")

    @commands.Cog.listener()
    async def on_ready(self):
        """Restore persistent views on bot startup"""
        await self._setup_persistent_views()

    async def cog_load(self):
        """Called when the cog is loaded (including reloads)"""
        if self.bot.is_ready():
            await self._setup_persistent_views()


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerGuide(bot))
