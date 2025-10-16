import discord
from discord.ext import commands
from discord import app_commands
import os
import logging
import json
from datetime import datetime
from typing import Dict, List, Any
from Config import (
    PINK,
    ADMIN_ROLE_ID,
    MODERATOR_ROLE_ID,
    MOD_DATA_FILE,
    CHANGELOG_ROLE_ID,
)
from Utils.EmbedUtils import set_pink_footer
from Utils.CacheUtils import cache_instance as cache

# === File Logger for this cog only ===
LOG_DIR = "Logs"
os.makedirs(LOG_DIR, exist_ok=True)
modpanel_logger = logging.getLogger("modpanel")
modpanel_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(
    os.path.join(LOG_DIR, "modpanel.log"), encoding="utf-8"
)
file_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s %(levelname)s │ %(message)s", datefmt="[%Y-%m-%d %H:%M:%S]"
    )
)
modpanel_logger.handlers.clear()  # Clear any existing handlers
modpanel_logger.addHandler(file_handler)


# === Mod data ===
async def load_mod_data() -> Dict[str, Any]:
    """Load mod data with caching for better performance."""
    async def _load():
        if not os.path.exists(MOD_DATA_FILE):
            return {"warnings": {}, "kicks": {}, "bans": {}, "mutes": {}}
        with open(MOD_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Ensure all keys exist
            data.setdefault("warnings", {})
            data.setdefault("kicks", {})
            data.setdefault("bans", {})
            data.setdefault("mutes", {})
            return data

    # Cache for 30 seconds since mod data changes frequently but we want some caching
    return await cache.get_or_set("mod_data", _load, ttl=30)


def save_mod_data(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(MOD_DATA_FILE), exist_ok=True)
    with open(MOD_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


# Helper to add mod action with reason
async def add_mod_action(action: str, user_id: int, reason: str, mod: discord.User) -> None:
    mod_data = await load_mod_data()
    actions_data = mod_data.get(action, {})
    user_id_str = str(user_id)
    if user_id_str not in actions_data:
        actions_data[user_id_str] = {"count": 0, "actions": []}
    actions_data[user_id_str]["count"] += 1
    actions_data[user_id_str]["actions"].append(
        {"reason": reason, "timestamp": datetime.now().isoformat(), "mod": str(mod)}
    )
    mod_data[action] = actions_data
    save_mod_data(mod_data)
    # Clear cache since data changed
    await cache.delete("mod_data")


def create_modpanel_embed(bot_user: discord.User) -> discord.Embed:
    embed = discord.Embed(
        title="📦 Mod Panel",
        description="Quick moderation actions for Slot Keepers and Admins.",
        color=PINK,
    )
    embed.add_field(
        name="Actions",
        value=("• Mute\n• Kick\n• Ban\n• Warn\n• Lock Channel\n• Slowmode"),
        inline=False,
    )
    set_pink_footer(embed, bot=bot_user)
    return embed


def is_mod_or_admin(member: discord.Member) -> bool:
    return any(role.id in [ADMIN_ROLE_ID, MODERATOR_ROLE_ID] for role in member.roles)


class UserSelect(discord.ui.Select):
    def __init__(self, members: List[discord.Member]):
        options = [
            discord.SelectOption(
                label=f"{m.display_name}#{m.discriminator}", value=str(m.id)
            )
            for m in members
        ]
        super().__init__(
            placeholder="Select a user...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        member_id = int(self.values[0])
        member = interaction.guild.get_member(member_id)
        if not member:
            await interaction.response.send_message(
                "❌ User not found.", ephemeral=True
            )
            modpanel_logger.warning(
                f"User not found: {member_id} by {interaction.user}"
            )
            return
        if not is_mod_or_admin(interaction.user):
            await interaction.response.send_message(
                "❌ You do not have permission.", ephemeral=True
            )
            modpanel_logger.warning(f"Permission denied for {interaction.user}")
            return
        await interaction.response.send_message(
            f"Selected user: {member.mention}\nChoose an action below:",
            view=ModActionView(member),
            ephemeral=True,
        )
        modpanel_logger.info(f"User selected: {member} by {interaction.user}")


class WarnModal(discord.ui.Modal):
    def __init__(self, member: discord.Member):
        super().__init__(title=f"Warn {member.display_name}")
        self.member = member
        self.reason = discord.ui.TextInput(
            label="Reason",
            placeholder="Enter reason (optional)",
            required=False,
            max_length=200,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            reason_text = (
                self.reason.value if self.reason.value else "No reason provided"
            )
            # Load mod data
            mod_data = await load_mod_data()
            warnings_data = mod_data.get("warnings", {})
            user_id = str(self.member.id)
            if user_id not in warnings_data:
                warnings_data[user_id] = {"count": 0, "warnings": []}
            warnings_data[user_id]["count"] += 1
            warnings_data[user_id]["warnings"].append(
                {
                    "reason": reason_text,
                    "timestamp": datetime.now().isoformat(),
                    "mod": str(interaction.user),
                }
            )
            # Save mod data
            mod_data["warnings"] = warnings_data
            save_mod_data(mod_data)
            # Clear cache since data changed
            await cache.delete("mod_data")
            # Post the warning in the channel
            await interaction.channel.send(
                f"⚠️ {self.member.mention} has been warned. Reason: {reason_text} (Warning #{warnings_data[user_id]['count']})"
            )
            await interaction.response.send_message(
                f"⚠️ Warned {self.member.mention}. Reason: {reason_text} (Total warnings: {warnings_data[user_id]['count']})",
                ephemeral=True,
            )
            modpanel_logger.info(
                f"Warned {self.member} by {interaction.user}. Reason: {reason_text}. Total: {warnings_data[user_id]['count']}"
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            modpanel_logger.error(f"Error warning {self.member}: {e}")


class KickModal(discord.ui.Modal):
    def __init__(self, member: discord.Member):
        super().__init__(title=f"Kick {member.display_name}")
        self.member = member
        self.reason = discord.ui.TextInput(
            label="Reason",
            placeholder="Enter reason (optional)",
            required=False,
            max_length=200,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            reason_text = (
                self.reason.value if self.reason.value else "No reason provided"
            )
            await self.member.kick(reason=reason_text)
            await add_mod_action("kicks", self.member.id, reason_text, interaction.user)
            await interaction.response.send_message(
                f"👢 Kicked {self.member.mention}. Reason: {reason_text}",
                ephemeral=True,
            )
            modpanel_logger.info(
                f"Kicked {self.member} by {interaction.user}. Reason: {reason_text}"
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            modpanel_logger.error(f"Error kicking {self.member}: {e}")


class BanModal(discord.ui.Modal):
    def __init__(self, member: discord.Member):
        super().__init__(title=f"Ban {member.display_name}")
        self.member = member
        self.reason = discord.ui.TextInput(
            label="Reason",
            placeholder="Enter reason (optional)",
            required=False,
            max_length=200,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            reason_text = (
                self.reason.value if self.reason.value else "No reason provided"
            )
            await self.member.ban(reason=reason_text)
            await add_mod_action("bans", self.member.id, reason_text, interaction.user)
            await interaction.response.send_message(
                f"🔨 Banned {self.member.mention}. Reason: {reason_text}",
                ephemeral=True,
            )
            modpanel_logger.info(
                f"Banned {self.member} by {interaction.user}. Reason: {reason_text}"
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            modpanel_logger.error(f"Error banning {self.member}: {e}")


class MuteModal(discord.ui.Modal):
    def __init__(self, member: discord.Member):
        super().__init__(title=f"Mute {member.display_name}")
        self.member = member
        self.reason = discord.ui.TextInput(
            label="Reason",
            placeholder="Enter reason (optional)",
            required=False,
            max_length=200,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            reason_text = (
                self.reason.value if self.reason.value else "No reason provided"
            )
            await self.member.edit(mute=True, reason=reason_text)
            await add_mod_action("mutes", self.member.id, reason_text, interaction.user)
            await interaction.response.send_message(
                f"🔇 Muted {self.member.mention}. Reason: {reason_text}", ephemeral=True
            )
            modpanel_logger.info(
                f"Muted {self.member} by {interaction.user}. Reason: {reason_text}"
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            modpanel_logger.error(f"Error muting {self.member}: {e}")


class ModActionView(discord.ui.View):
    def __init__(self, member: discord.Member):
        super().__init__(timeout=60)
        self.member = member

    @discord.ui.button(label="Mute", style=discord.ButtonStyle.gray, emoji="🔇")
    async def mute(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(MuteModal(self.member))

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.red, emoji="👢")
    async def kick(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(KickModal(self.member))

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.red, emoji="🔨")
    async def ban(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(BanModal(self.member))

    @discord.ui.button(label="Warn", style=discord.ButtonStyle.blurple, emoji="⚠️")
    async def warn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(WarnModal(self.member))


class ModPanelView(discord.ui.View):
    def __init__(self, members: List[discord.Member]):
        super().__init__(timeout=None)
        self.add_item(UserSelect(members))

    @discord.ui.button(
        label="Lock Channel", style=discord.ButtonStyle.gray, emoji="🔒", row=1
    )
    async def lock(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        try:
            overwrite = interaction.channel.overwrites_for(
                interaction.guild.default_role
            )
            overwrite.send_messages = False
            await interaction.channel.set_permissions(
                interaction.guild.default_role, overwrite=overwrite
            )
            await interaction.response.send_message(
                "🔒 Channel locked.", ephemeral=True
            )
            modpanel_logger.info(f"Channel locked by {interaction.user}")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            modpanel_logger.error(f"Error locking channel: {e}")

    @discord.ui.button(
        label="Slowmode", style=discord.ButtonStyle.gray, emoji="🐢", row=1
    )
    async def slowmode(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        try:
            await interaction.channel.edit(slowmode_delay=30)
            await interaction.response.send_message(
                "🐢 Slowmode set to 30 seconds.", ephemeral=True
            )
            modpanel_logger.info(f"Slowmode set by {interaction.user}")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            modpanel_logger.error(f"Error setting slowmode: {e}")


class ModMainView(discord.ui.View):
    def __init__(self, bot: commands.Bot, members: List[discord.Member]):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.bot = bot
        self.members = members
        # Add select for users
        self.add_item(UserSelectForDetails(members))

    @discord.ui.button(label="Mod Panel", style=discord.ButtonStyle.primary, emoji="📦")
    async def mod_panel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        embed = create_modpanel_embed(self.bot.user)
        view = ModPanelView(self.members)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        modpanel_logger.info(f"Mod panel opened from /mod by {interaction.user}")

    @discord.ui.button(
        label="Mod Overview", style=discord.ButtonStyle.secondary, emoji="📊"
    )
    async def mod_overview(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        # Use handle_modoverview
        cog = self.bot.get_cog("ModPanel")
        if cog:
            await cog.handle_modoverview(interaction)
        else:
            await interaction.response.send_message("❌ Cog not found.", ephemeral=True)

    @discord.ui.button(label="Opt-Ins", style=discord.ButtonStyle.secondary, emoji="📋")
    async def opt_ins(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        # Use handle_optins
        cog = self.bot.get_cog("ModPanel")
        if cog:
            await cog.handle_optins(interaction)
        else:
            await interaction.response.send_message("❌ Cog not found.", ephemeral=True)


class UserSelectForDetails(discord.ui.Select):
    def __init__(self, members: List[discord.Member]):
        options = [
            discord.SelectOption(
                label=f"{m.display_name}#{m.discriminator}", value=str(m.id)
            )
            for m in members[:25]  # Limit to 25 options
        ]
        super().__init__(
            placeholder="Select a user for details...",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        member_id = int(self.values[0])
        member = interaction.guild.get_member(member_id)
        if not member:
            await interaction.response.send_message(
                "❌ User not found.", ephemeral=True
            )
            return
        # Use handle_moddetails
        cog = interaction.client.get_cog("ModPanel")
        if cog:
            await cog.handle_moddetails(interaction, member)
        else:
            await interaction.response.send_message("❌ Cog not found.", ephemeral=True)


class ModPanel(commands.Cog):
    """
    📦 Mod Panel Cog: Quick moderation actions for Slot Keepers and Admins.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_modpanel_help_embed(self, ctx_or_interaction: Any) -> discord.Embed:
        embed = discord.Embed(
            title="📦 Mod Panel Help",
            description="Quick moderation actions for Slot Keepers and Admins.\nUse `!modpanel` or `/modpanel`.",
            color=PINK,
        )
        embed.add_field(
            name="Actions",
            value="Mute, Kick, Ban, Warn, Lock Channel, Slowmode",
            inline=False,
        )
        set_pink_footer(embed, bot=self.bot.user if hasattr(self.bot, "user") else None)
        return embed

    # 🧩 Shared handler for modpanel logic
    async def handle_modpanel(self, ctx_or_interaction: Any) -> None:
        if not is_mod_or_admin(
            ctx_or_interaction.author
            if hasattr(ctx_or_interaction, "author")
            else ctx_or_interaction.user
        ):
            message = "❌ You do not have permission to use this command."
            if hasattr(ctx_or_interaction, "send"):
                await ctx_or_interaction.send(message, delete_after=5)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
            return
        embed = create_modpanel_embed(self.bot.user)
        members = [
            m
            for m in (
                ctx_or_interaction.guild
                if hasattr(ctx_or_interaction, "guild")
                else ctx_or_interaction.guild
            ).members
            if not m.bot
        ]
        if not members:
            message = "❌ No users available."
            if hasattr(ctx_or_interaction, "send"):
                await ctx_or_interaction.send(message, delete_after=5)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
            return
        view = ModPanelView(members)
        if hasattr(ctx_or_interaction, "send"):
            await ctx_or_interaction.send(embed=embed, view=view)
        else:
            await ctx_or_interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )
        modpanel_logger.info(
            f"Mod panel opened by {ctx_or_interaction.author if hasattr(ctx_or_interaction, 'author') else ctx_or_interaction.user}"
        )

    @commands.command(name="modpanel")
    async def modpanel_command(self, ctx: commands.Context) -> None:
        """
        📦 Opens the Mod Panel for quick moderation actions.
        """
        await self.handle_modpanel(ctx)

    @app_commands.command(
        name="modpanel",
        description="📦 Opens the Mod Panel for quick moderation actions.",
    )
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    async def modpanel_slash(self, interaction: discord.Interaction) -> None:
        await self.handle_modpanel(interaction)

    # 🧩 Shared handler for mod logic
    async def handle_mod(self, ctx_or_interaction: Any) -> None:
        if not is_mod_or_admin(
            ctx_or_interaction.author
            if hasattr(ctx_or_interaction, "author")
            else ctx_or_interaction.user
        ):
            message = "❌ You do not have permission to use this command."
            if hasattr(ctx_or_interaction, "send"):
                await ctx_or_interaction.send(message, delete_after=5)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
            return
        embed = discord.Embed(
            title="📋 Mod Tools",
            description="Quick access to moderation tools.\nSelect a user for details or use the buttons below.",
            color=PINK,
        )
        set_pink_footer(embed, bot=self.bot.user)
        members = [
            m
            for m in (
                ctx_or_interaction.guild
                if hasattr(ctx_or_interaction, "guild")
                else ctx_or_interaction.guild
            ).members
            if not m.bot
        ]
        if not members:
            message = "❌ No users available."
            if hasattr(ctx_or_interaction, "send"):
                await ctx_or_interaction.send(message, delete_after=5)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
            return
        view = ModMainView(self.bot, members)
        if hasattr(ctx_or_interaction, "send"):
            await ctx_or_interaction.send(embed=embed, view=view)
        else:
            await ctx_or_interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )
        modpanel_logger.info(
            f"Mod tools opened by {ctx_or_interaction.author if hasattr(ctx_or_interaction, 'author') else ctx_or_interaction.user}"
        )

    @commands.command(name="mod")
    async def mod_command(self, ctx: commands.Context) -> None:
        """
        📋 General mod command with quick access to mod tools.
        """
        await self.handle_mod(ctx)

    @app_commands.command(
        name="mod", description="📋 General mod command with quick access to mod tools."
    )
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    async def mod_slash(self, interaction: discord.Interaction) -> None:
        await self.handle_mod(interaction)

    # 🧩 Shared handler for modoverview logic
    async def handle_modoverview(self, ctx_or_interaction: Any) -> None:
        if not is_mod_or_admin(
            ctx_or_interaction.author
            if hasattr(ctx_or_interaction, "author")
            else ctx_or_interaction.user
        ):
            message = "❌ You do not have permission to use this command."
            if hasattr(ctx_or_interaction, "send"):
                await ctx_or_interaction.send(message, delete_after=5)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
            return
        mod_data = await load_mod_data()
        embed = discord.Embed(
            title="📊 Moderation Overview",
            description="Overview of moderation actions taken.",
            color=PINK,
        )
        actions = ["warnings", "kicks", "bans", "mutes"]
        for action in actions:
            data = mod_data.get(action, {})
            if data:
                if action == "warnings":
                    # Sort by count descending, limit to top 3 for brevity
                    top_users = sorted(
                        data.items(), key=lambda x: x[1]["count"], reverse=True
                    )[:3]
                    text_lines = []
                    for uid, wdata in top_users:
                        count = wdata["count"]
                        # Show only the latest reason for compactness
                        latest_warning = (
                            wdata["warnings"][-1]
                            if wdata["warnings"]
                            else {
                                "reason": "No reason",
                                "mod": "Unknown",
                                "timestamp": "Unknown",
                            }
                        )
                        reason = latest_warning["reason"]
                        text_lines.append(
                            f"<@{uid}>: {count} warning(s) - Latest: {reason}"
                        )
                    text = "\n".join(text_lines)
                else:
                    # For kicks, bans, mutes: limit to top 3, show latest reason
                    top_users = sorted(
                        data.items(), key=lambda x: x[1]["count"], reverse=True
                    )[:3]
                    text_lines = []
                    for uid, adata in top_users:
                        count = adata["count"]
                        latest_action = (
                            adata["actions"][-1]
                            if adata["actions"]
                            else {
                                "reason": "No reason",
                                "mod": "Unknown",
                                "timestamp": "Unknown",
                            }
                        )
                        reason = latest_action["reason"]
                        text_lines.append(
                            f"<@{uid}>: {count} {action}(s) - Latest: {reason}"
                        )
                    text = "\n".join(text_lines)
            else:
                text = "No actions recorded."
            embed.add_field(
                name=f"{action.capitalize()}",
                value=text or "No actions recorded.",
                inline=True,
            )  # Use inline=True for side-by-side layout
        set_pink_footer(embed, bot=self.bot.user)
        if hasattr(ctx_or_interaction, "send"):
            await ctx_or_interaction.send(embed=embed)
        else:
            await ctx_or_interaction.response.send_message(embed=embed, ephemeral=True)
        modpanel_logger.info(
            f"Mod overview requested by {ctx_or_interaction.author if hasattr(ctx_or_interaction, 'author') else ctx_or_interaction.user}"
        )

    @commands.command(name="modoverview")
    async def modoverview_command(self, ctx: commands.Context) -> None:
        """
        📊 Shows an overview of moderation actions for mods.
        """
        await self.handle_modoverview(ctx)

    @app_commands.command(
        name="modoverview",
        description="📊 Shows an overview of moderation actions for mods.",
    )
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    async def modoverview_slash(self, interaction: discord.Interaction) -> None:
        await self.handle_modoverview(interaction)

    # 🧩 Shared handler for moddetails logic
    async def handle_moddetails(self, ctx_or_interaction: Any, user: discord.User) -> None:
        if not is_mod_or_admin(
            ctx_or_interaction.author
            if hasattr(ctx_or_interaction, "author")
            else ctx_or_interaction.user
        ):
            message = "❌ You do not have permission to use this command."
            if hasattr(ctx_or_interaction, "send"):
                await ctx_or_interaction.send(message, delete_after=5)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
            return
        mod_data = await load_mod_data()
        embed = discord.Embed(
            title=f"📊 Moderation Details for {user.display_name}",
            description=f"Detailed moderation actions for {user.mention}.",
            color=PINK,
        )
        actions = ["warnings", "kicks", "bans", "mutes"]
        for action in actions:
            data = mod_data.get(action, {}).get(str(user.id), {})
            if data and data.get("count", 0) > 0:
                if action == "warnings":
                    warnings_list = data.get("warnings", [])
                    text_lines = [
                        f"- {w['reason']} (by {w['mod']} at {w['timestamp'][:16]})"
                        for w in warnings_list
                    ]
                    text = "\n".join(text_lines)
                else:
                    actions_list = data.get("actions", [])
                    text_lines = [
                        f"- {a['reason']} (by {a['mod']} at {a['timestamp'][:16]})"
                        for a in actions_list
                    ]
                    text = "\n".join(text_lines)
                embed.add_field(
                    name=f"{action.capitalize()} ({data['count']})",
                    value=text,
                    inline=False,
                )
            else:
                embed.add_field(
                    name=f"{action.capitalize()}",
                    value="No actions recorded.",
                    inline=False,
                )
        set_pink_footer(embed, bot=self.bot.user)
        if hasattr(ctx_or_interaction, "send"):
            await ctx_or_interaction.send(embed=embed)
        else:
            await ctx_or_interaction.response.send_message(embed=embed, ephemeral=True)
        modpanel_logger.info(
            f"Mod details requested for {user} by {ctx_or_interaction.author if hasattr(ctx_or_interaction, 'author') else ctx_or_interaction.user}"
        )

    @commands.command(name="moddetails")
    async def moddetails_command(self, ctx: commands.Context, user: discord.User) -> None:
        """
        📊 Shows detailed moderation actions for a specific user.
        Usage: !moddetails @user
        """
        await self.handle_moddetails(ctx, user)

    @app_commands.command(
        name="moddetails",
        description="📊 Shows detailed moderation actions for a specific user.",
    )
    @app_commands.describe(user="The user to get details for")
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    async def moddetails_slash(
        self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        await self.handle_moddetails(interaction, user)

    # !optins (Prefix) - For mods/admins to view opt-ins
    @commands.command(name="optins")
    async def optins_command(self, ctx: commands.Context) -> None:
        """
        📊 Shows an overview of user opt-ins (e.g., changelog notifications).
        """
        await self.handle_optins(ctx)

    # /optins (Slash) - For mods/admins to view opt-ins
    @app_commands.command(
        name="optins",
        description="📊 Shows an overview of user opt-ins (e.g., changelog notifications).",
    )
    @app_commands.guilds(discord.Object(id=int(os.getenv("DISCORD_GUILD_ID"))))
    async def optins_slash(self, interaction: discord.Interaction) -> None:
        await self.handle_optins(interaction)

    # 🧩 Shared handler for optins logic
    async def handle_optins(self, ctx_or_interaction: Any) -> None:
        if not is_mod_or_admin(
            ctx_or_interaction.author
            if hasattr(ctx_or_interaction, "author")
            else ctx_or_interaction.user
        ):
            message = "❌ You do not have permission to use this command."
            if hasattr(ctx_or_interaction, "send"):
                await ctx_or_interaction.send(message, delete_after=5)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
            return
        guild = (
            ctx_or_interaction.guild
            if hasattr(ctx_or_interaction, "guild")
            else ctx_or_interaction.guild
        )
        changelog_role = guild.get_role(CHANGELOG_ROLE_ID)
        if not changelog_role:
            message = "❌ Changelog role not found."
            if hasattr(ctx_or_interaction, "send"):
                await ctx_or_interaction.send(message, delete_after=5)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
            return
        users_with_role = [
            member for member in guild.members if changelog_role in member.roles
        ]
        if not users_with_role:
            description = "No users have opted into changelog notifications."
        else:
            user_list = "\n".join(
                [
                    f"<@{member.id}> ({member.display_name})"
                    for member in users_with_role
                ]
            )
            description = f"Users opted into changelog notifications:\n{user_list}"
        embed = discord.Embed(
            title="📊 Opt-Ins Overview", description=description, color=PINK
        )
        set_pink_footer(embed, bot=self.bot.user)
        if hasattr(ctx_or_interaction, "send"):
            await ctx_or_interaction.send(embed=embed)
        else:
            await ctx_or_interaction.response.send_message(embed=embed, ephemeral=True)
        modpanel_logger.info(
            f"Opt-ins overview requested by {ctx_or_interaction.author if hasattr(ctx_or_interaction, 'author') else ctx_or_interaction.user}"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModPanel(bot))
