import discord
from discord.ext import commands
from discord import app_commands
import os
import logging
import json
from datetime import datetime
from Config import PINK, ADMIN_ROLE_ID, MODERATOR_ROLE_ID, MOD_DATA_FILE
from Utils.EmbedUtils import set_pink_footer

# === File Logger for this cog only ===
LOG_DIR = "Logs"
os.makedirs(LOG_DIR, exist_ok=True)
modpanel_logger = logging.getLogger("modpanel")
modpanel_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(os.path.join(LOG_DIR, "modpanel.log"), encoding="utf-8")
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s │ %(message)s', datefmt='[%Y-%m-%d %H:%M:%S]'))
modpanel_logger.handlers.clear()  # Clear any existing handlers
modpanel_logger.addHandler(file_handler)

# === Mod data ===
def load_mod_data():
    if not os.path.exists(MOD_DATA_FILE):
        return {"warnings": {}, "kicks": {}, "bans": {}, "mutes": {}}
    with open(MOD_DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Ensure all keys exist
        data.setdefault("warnings", {})
        data.setdefault("kicks", {})
        data.setdefault("bans", {})
        data.setdefault("mutes", {})
        return data

def save_mod_data(data):
    os.makedirs(os.path.dirname(MOD_DATA_FILE), exist_ok=True)
    with open(MOD_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# Helper to increment mod action count
def increment_mod_count(action, user_id):
    mod_data = load_mod_data()
    if str(user_id) not in mod_data[action]:
        mod_data[action][str(user_id)] = 0
    mod_data[action][str(user_id)] += 1
    save_mod_data(mod_data)

def create_modpanel_embed(bot_user):
    embed = discord.Embed(
        title="📦 Mod Panel",
        description="Quick moderation actions for Slot Keepers and Admins.",
        color=PINK
    )
    embed.add_field(
        name="Actions",
        value=(
            "• Mute\n"
            "• Kick\n"
            "• Ban\n"
            "• Warn\n"
            "• Lock Channel\n"
            "• Slowmode"
        ),
        inline=False
    )
    set_pink_footer(embed, bot=bot_user)
    return embed

def is_mod_or_admin(member):
    return any(role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in member.roles)

class UserSelect(discord.ui.Select):
    def __init__(self, members):
        options = [
            discord.SelectOption(label=f"{m.display_name}#{m.discriminator}", value=str(m.id))
            for m in members
        ]
        super().__init__(
            placeholder="Select a user...",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        member_id = int(self.values[0])
        member = interaction.guild.get_member(member_id)
        if not member:
            await interaction.response.send_message("❌ User not found.", ephemeral=True)
            modpanel_logger.warning(f"User not found: {member_id} by {interaction.user}")
            return
        if not is_mod_or_admin(interaction.user):
            await interaction.response.send_message("❌ You do not have permission.", ephemeral=True)
            modpanel_logger.warning(f"Permission denied for {interaction.user}")
            return
        await interaction.response.send_message(
            f"Selected user: {member.mention}\nChoose an action below:",
            view=ModActionView(member),
            ephemeral=True
        )
        modpanel_logger.info(f"User selected: {member} by {interaction.user}")

class WarnModal(discord.ui.Modal):
    def __init__(self, member):
        super().__init__(title=f"Warn {member.display_name}")
        self.member = member
        self.reason = discord.ui.TextInput(
            label="Reason",
            placeholder="Enter reason (optional)",
            required=False,
            max_length=200
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            reason_text = self.reason.value if self.reason.value else "No reason provided"
            # Load mod data
            mod_data = load_mod_data()
            warnings_data = mod_data.get("warnings", {})
            user_id = str(self.member.id)
            if user_id not in warnings_data:
                warnings_data[user_id] = {"count": 0, "warnings": []}
            warnings_data[user_id]["count"] += 1
            warnings_data[user_id]["warnings"].append({
                "reason": reason_text,
                "timestamp": datetime.now().isoformat(),
                "mod": str(interaction.user)
            })
            # Save mod data
            mod_data["warnings"] = warnings_data
            save_mod_data(mod_data)
            # Post the warning in the channel
            await interaction.channel.send(f"⚠️ {self.member.mention} has been warned. Reason: {reason_text} (Warning #{warnings_data[user_id]['count']})")
            await interaction.response.send_message(f"⚠️ Warned {self.member.mention}. Reason: {reason_text} (Total warnings: {warnings_data[user_id]['count']})", ephemeral=True)
            modpanel_logger.info(f"Warned {self.member} by {interaction.user}. Reason: {reason_text}. Total: {warnings_data[user_id]['count']}")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            modpanel_logger.error(f"Error warning {self.member}: {e}")

class ModActionView(discord.ui.View):
    def __init__(self, member):
        super().__init__(timeout=60)
        self.member = member

    @discord.ui.button(label="Mute", style=discord.ButtonStyle.gray, emoji="🔇")
    async def mute(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.member.edit(mute=True)
            increment_mod_count("mutes", self.member.id)
            await interaction.response.send_message(f"🔇 Muted {self.member.mention}.", ephemeral=True)
            modpanel_logger.info(f"Muted {self.member} by {interaction.user}")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            modpanel_logger.error(f"Error muting {self.member}: {e}")

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.red, emoji="👢")
    async def kick(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.member.kick()
            increment_mod_count("kicks", self.member.id)
            await interaction.response.send_message(f"👢 Kicked {self.member.mention}.", ephemeral=True)
            modpanel_logger.info(f"Kicked {self.member} by {interaction.user}")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            modpanel_logger.error(f"Error kicking {self.member}: {e}")

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.red, emoji="🔨")
    async def ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.member.ban()
            increment_mod_count("bans", self.member.id)
            await interaction.response.send_message(f"🔨 Banned {self.member.mention}.", ephemeral=True)
            modpanel_logger.info(f"Banned {self.member} by {interaction.user}")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            modpanel_logger.error(f"Error banning {self.member}: {e}")

    @discord.ui.button(label="Warn", style=discord.ButtonStyle.blurple, emoji="⚠️")
    async def warn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WarnModal(self.member))

class ModPanelView(discord.ui.View):
    def __init__(self, members):
        super().__init__(timeout=None)
        self.add_item(UserSelect(members))

    @discord.ui.button(label="Lock Channel", style=discord.ButtonStyle.gray, emoji="🔒", row=1)
    async def lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
            overwrite.send_messages = False
            await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
            await interaction.response.send_message("🔒 Channel locked.", ephemeral=True)
            modpanel_logger.info(f"Channel locked by {interaction.user}")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            modpanel_logger.error(f"Error locking channel: {e}")

    @discord.ui.button(label="Slowmode", style=discord.ButtonStyle.gray, emoji="🐢", row=1)
    async def slowmode(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.channel.edit(slowmode_delay=30)
            await interaction.response.send_message("🐢 Slowmode set to 30 seconds.", ephemeral=True)
            modpanel_logger.info(f"Slowmode set by {interaction.user}")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            modpanel_logger.error(f"Error setting slowmode: {e}")

class ModPanel(commands.Cog):
    """
    📦 Mod Panel Cog: Quick moderation actions for Slot Keepers and Admins.
    """

    def __init__(self, bot):
        self.bot = bot

    def get_modpanel_help_embed(self, ctx_or_interaction):
        embed = discord.Embed(
            title="📦 Mod Panel Help",
            description="Quick moderation actions for Slot Keepers and Admins.\nUse `!modpanel` or `/modpanel`.",
            color=PINK
        )
        embed.add_field(
            name="Actions",
            value="Mute, Kick, Ban, Warn, Lock Channel, Slowmode",
            inline=False
        )
        set_pink_footer(embed, bot=self.bot.user if hasattr(self.bot, 'user') else None)
        return embed

    @commands.command(name="modpanel")
    async def modpanel_command(self, ctx):
        """
        📦 Opens the Mod Panel for quick moderation actions.
        """
        if not is_mod_or_admin(ctx.author):
            await ctx.send("❌ You do not have permission to use this command.", delete_after=5)
            modpanel_logger.warning(f"Permission denied for {ctx.author}")
            return
        embed = create_modpanel_embed(self.bot.user)
        members = [m for m in ctx.guild.members if not m.bot]
        if not members:
            await ctx.send("❌ No users available.", delete_after=5)
            modpanel_logger.warning(f"No users available for {ctx.author}")
            return
        view = ModPanelView(members)
        await ctx.send(embed=embed, view=view)
        modpanel_logger.info(f"Mod panel opened by {ctx.author}")

    @app_commands.command(name="modpanel", description="📦 Opens the Mod Panel for quick moderation actions.")
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    async def modpanel_slash(self, interaction: discord.Interaction):
        if not is_mod_or_admin(interaction.user):
            await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
            modpanel_logger.warning(f"Permission denied for {interaction.user}")
            return
        embed = create_modpanel_embed(self.bot.user)
        members = [m for m in interaction.guild.members if not m.bot]
        if not members:
            await interaction.response.send_message("❌ No users available.", ephemeral=True)
            modpanel_logger.warning(f"No users available for {interaction.user}")
            return
        view = ModPanelView(members)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        modpanel_logger.info(f"Mod panel opened by {interaction.user}")

    # 🧩 Shared handler for modoverview logic
    async def handle_modoverview(self, ctx_or_interaction):
        if not is_mod_or_admin(ctx_or_interaction.author if hasattr(ctx_or_interaction, 'author') else ctx_or_interaction.user):
            message = "❌ You do not have permission to use this command."
            if hasattr(ctx_or_interaction, 'send'):
                await ctx_or_interaction.send(message, delete_after=5)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
            return
        mod_data = load_mod_data()
        embed = discord.Embed(
            title="📊 Moderation Overview",
            description="Overview of moderation actions taken.",
            color=PINK
        )
        actions = ["warnings", "kicks", "bans", "mutes"]
        for action in actions:
            data = mod_data.get(action, {})
            if data:
                top_users = sorted(data.items(), key=lambda x: x[1], reverse=True)[:5]  # Top 5
                text = "\n".join([f"<@{uid}>: {count}" for uid, count in top_users])
            else:
                text = "No actions recorded."
            embed.add_field(name=f"{action.capitalize()}", value=text, inline=True)
        set_pink_footer(embed, bot=self.bot.user)
        if hasattr(ctx_or_interaction, 'send'):
            await ctx_or_interaction.send(embed=embed)
        else:
            await ctx_or_interaction.response.send_message(embed=embed, ephemeral=True)
        modpanel_logger.info(f"Mod overview requested by {ctx_or_interaction.author if hasattr(ctx_or_interaction, 'author') else ctx_or_interaction.user}")

    @commands.command(name="modoverview")
    async def modoverview_command(self, ctx):
        """
        📊 Shows an overview of moderation actions for mods.
        """
        await self.handle_modoverview(ctx)

    @app_commands.command(name="modoverview", description="📊 Shows an overview of moderation actions for mods.")
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    async def modoverview_slash(self, interaction: discord.Interaction):
        await self.handle_modoverview(interaction)

async def setup(bot):
    await bot.add_cog(ModPanel(bot))