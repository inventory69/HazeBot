"""
LevelSystem Cog for HazeBot
============================
Tracks user activity and assigns XP/Levels with Inventory-themed ranks.

Features:
- Activity-based XP (memes, messages, images, tickets, games)
- Exponential level progression
- Role-based notification preferences
- Level-up celebration embeds
- Mod promotion feature
- Leaderboard & history tracking
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import Config
from Config import (
    GUILD_ID,
    LEVEL_ICONS,
    LEVEL_NOTIFICATION_ROLE_ID,
    LEVEL_UP_CHANNEL_ID,
    MODERATOR_ROLE_ID,
    XP_CONFIG,
    calculate_level,
    get_guild_id,
    get_level_tier,
)

logger = logging.getLogger(__name__)


class LevelSystem(commands.Cog):
    """
    ⭐ Level System: Activity-based XP and leveling with Inventory-themed ranks
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = Path(Config.DATA_DIR) / "user_levels.db"
        self._cooldowns = {}  # user_id: last_message_time
        self._init_database()

    def _init_database(self):
        """Initialize database with schema"""
        try:
            # Ensure Data directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Read and execute SQL schema
            schema_path = Path(Config.DATA_DIR) / "init_user_levels.sql"
            if schema_path.exists():
                with open(schema_path, 'r') as f:
                    schema_sql = f.read()
                cursor.executescript(schema_sql)
                # Database initialized silently (no log during cog load)
            else:
                # Fallback: Create tables inline
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_xp (
                        user_id TEXT PRIMARY KEY,
                        username TEXT NOT NULL,
                        total_xp INTEGER DEFAULT 0,
                        current_level INTEGER DEFAULT 1,
                        memes_generated INTEGER DEFAULT 0,
                        memes_fetched INTEGER DEFAULT 0,
                        messages_sent INTEGER DEFAULT 0,
                        images_sent INTEGER DEFAULT 0,
                        tickets_created INTEGER DEFAULT 0,
                        tickets_resolved INTEGER DEFAULT 0,
                        game_requests INTEGER DEFAULT 0,
                        last_xp_gain TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS level_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        old_level INTEGER NOT NULL,
                        new_level INTEGER NOT NULL,
                        total_xp INTEGER NOT NULL,
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES user_xp(user_id)
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS mod_promotions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        promoted_by TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        message_id TEXT
                    )
                """)
                
                # Database tables created silently (no log during cog load)
            
            # Migration: Add new RL columns if they don't exist
            try:
                cursor.execute("ALTER TABLE user_xp ADD COLUMN rl_accounts_linked INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cursor.execute("ALTER TABLE user_xp ADD COLUMN rl_stats_checked INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Migration: Add game_request column if it doesn't exist
            try:
                cursor.execute("ALTER TABLE user_xp ADD COLUMN game_request INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            raise

    def _get_or_create_user(self, user_id: str, username: str) -> dict:
        """Get user data or create new entry"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM user_xp WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            
            if row:
                conn.close()
                return dict(row)
            
            # Create new user
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
                INSERT INTO user_xp (user_id, username, total_xp, current_level, created_at, updated_at)
                VALUES (?, ?, 0, 1, ?, ?)
            """, (user_id, username, now, now))
            
            conn.commit()
            conn.close()
            
            logger.info(f"➕ Created new user: {username} ({user_id})")
            
            return {
                "user_id": user_id,
                "username": username,
                "total_xp": 0,
                "current_level": 1,
                "memes_generated": 0,
                "memes_fetched": 0,
                "messages_sent": 0,
                "images_sent": 0,
                "tickets_created": 0,
                "tickets_resolved": 0,
                "game_requests": 0,
                "last_xp_gain": None,
                "created_at": now,
                "updated_at": now
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting/creating user: {e}")
            return None

    def _check_cooldown(self, user_id: str) -> bool:
        """Check if user is on cooldown for message XP"""
        if user_id not in self._cooldowns:
            return True
        
        last_time = self._cooldowns[user_id]
        cooldown = XP_CONFIG["message_cooldown"]
        
        if (datetime.now(timezone.utc) - last_time).total_seconds() >= cooldown:
            return True
        
        return False

    def _update_cooldown(self, user_id: str):
        """Update cooldown timestamp"""
        self._cooldowns[user_id] = datetime.now(timezone.utc)

    async def add_xp(self, user_id: str, username: str, xp_type: str, amount: int = None) -> Optional[dict]:
        """
        Add XP to user and check for level-up
        
        Args:
            user_id: Discord User ID
            username: Discord Username
            xp_type: Type of activity (from XP_CONFIG keys)
            amount: Optional XP override
        
        Returns:
            Dict with xp_gained, total_xp, level, leveled_up or None if on cooldown
        """
        try:
            # Get/Create User
            user_data = self._get_or_create_user(user_id, username)
            if not user_data:
                return None
            
            # Cooldown Check (für Messages)
            if xp_type == "message_sent":
                if not self._check_cooldown(user_id):
                    return None  # Still on cooldown
                self._update_cooldown(user_id)
            
            # Calculate XP
            xp_amount = amount if amount is not None else XP_CONFIG.get(xp_type, 0)
            
            if xp_amount == 0:
                logger.warning(f"⚠️ Unknown XP type: {xp_type}")
                return None
            
            # Update User Data
            old_level = user_data["current_level"]
            new_xp = user_data["total_xp"] + xp_amount
            new_level = calculate_level(new_xp)
            
            # Update Database
            self._update_user_xp(user_id, xp_type, xp_amount, new_xp, new_level)
            
            # Level Up Event
            if new_level > old_level:
                await self._handle_level_up(user_id, username, old_level, new_level, new_xp)
            
            logger.info(f"✅ {username} gained {xp_amount} XP ({xp_type}) → Level {new_level} ({new_xp} total XP)")
            
            return {
                "xp_gained": xp_amount,
                "total_xp": new_xp,
                "level": new_level,
                "leveled_up": new_level > old_level
            }
            
        except Exception as e:
            logger.error(f"❌ Error adding XP: {e}")
            return None

    def _update_user_xp(self, user_id: str, xp_type: str, xp_amount: int, new_xp: int, new_level: int):
        """Update user XP in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Map xp_type (from XP_CONFIG) to database column name
            column_mapping = {
                "meme_generated": "memes_generated",
                "meme_fetched": "memes_fetched",
                "message_sent": "messages_sent",
                "image_sent": "images_sent",
                "ticket_created": "tickets_created",
                "ticket_resolved": "tickets_resolved",
                "ticket_claimed": "tickets_claimed",
                "game_request": "game_request",
                "rl_account_linked": "rl_accounts_linked",
                "rl_stats_checked": "rl_stats_checked"
            }
            
            activity_column = column_mapping.get(xp_type)
            now = datetime.now(timezone.utc).isoformat()
            
            # Update total_xp, level, timestamps
            # Only increment activity column if xp_type is mapped to a column
            if activity_column:
                # Update with activity column increment
                cursor.execute(f"""
                    UPDATE user_xp
                    SET total_xp = ?,
                        current_level = ?,
                        {activity_column} = {activity_column} + 1,
                        last_xp_gain = ?,
                        updated_at = ?
                    WHERE user_id = ?
                """, (new_xp, new_level, now, now, user_id))
            else:
                # Update without activity column (for manual/bonus XP)
                cursor.execute("""
                    UPDATE user_xp
                    SET total_xp = ?,
                        current_level = ?,
                        last_xp_gain = ?,
                        updated_at = ?
                    WHERE user_id = ?
                """, (new_xp, new_level, now, now, user_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Error updating user XP: {e}")

    async def _handle_level_up(self, user_id: str, username: str, old_level: int, new_level: int, total_xp: int):
        """Handle level-up event with embed notification"""
        try:
            # Get channel
            channel = self.bot.get_channel(LEVEL_UP_CHANNEL_ID)
            if not channel:
                logger.warning(f"⚠️ Level-Up channel {LEVEL_UP_CHANNEL_ID} not found")
                return
            
            # Get guild and member
            guild = self.bot.get_guild(GUILD_ID)
            if not guild:
                return
            
            member = guild.get_member(int(user_id))
            if not member:
                logger.warning(f"⚠️ Member {user_id} not found in guild")
                return
            
            # Update level tier role (automatic assignment)
            await self._update_level_tier_role(member, new_level)
            
            # Check if user wants notifications
            level_role = guild.get_role(LEVEL_NOTIFICATION_ROLE_ID)
            user_wants_notification = level_role and level_role in member.roles
            
            # Create embed
            embed = self._create_level_up_embed(username, old_level, new_level, total_xp)
            
            # Send with or without ping
            content = f"<@{user_id}>" if user_wants_notification else None
            
            await channel.send(content=content, embed=embed)
            
            # Save to history
            self._save_level_history(user_id, old_level, new_level, total_xp)
            
            logger.info(f"🎉 Level-up posted: {username} → Level {new_level}")
            
        except Exception as e:
            logger.error(f"❌ Error handling level-up: {e}")
    
    async def _update_level_tier_role(self, member: discord.Member, level: int):
        """
        Update user's level tier role based on their level
        
        - Removes old tier roles
        - Assigns new tier role based on level
        - Only if LEVEL_TIER_ROLES is configured
        """
        try:
            # Get tier roles config
            from Config import LEVEL_TIER_ROLES
            
            if not LEVEL_TIER_ROLES:
                return
            
            # Determine new tier based on level
            if level >= 50:
                new_tier = "legendary"
            elif level >= 30:
                new_tier = "epic"
            elif level >= 20:
                new_tier = "rare"
            elif level >= 10:
                new_tier = "uncommon"
            else:
                new_tier = "common"
            
            # Get all tier role IDs
            all_tier_role_ids = set(LEVEL_TIER_ROLES.values())
            
            # Get new tier role
            new_tier_role_id = LEVEL_TIER_ROLES.get(new_tier)
            if not new_tier_role_id:
                logger.warning(f"⚠️ Tier role ID not found for tier: {new_tier}")
                return
            
            new_tier_role = member.guild.get_role(new_tier_role_id)
            if not new_tier_role:
                logger.warning(f"⚠️ Tier role not found in guild: {new_tier_role_id}")
                return
            
            # Remove old tier roles (except the new one)
            roles_to_remove = []
            for role in member.roles:
                if role.id in all_tier_role_ids and role.id != new_tier_role_id:
                    roles_to_remove.append(role)
            
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Level tier update")
                logger.info(f"🗑️ Removed old tier roles from {member.name}: {[r.name for r in roles_to_remove]}")
            
            # Add new tier role if not already present
            if new_tier_role not in member.roles:
                await member.add_roles(new_tier_role, reason=f"Reached {new_tier} tier (Level {level})")
                logger.info(f"⭐ Assigned tier role to {member.name}: {new_tier_role.name} (Level {level})")
            else:
                logger.info(f"✅ {member.name} already has tier role: {new_tier_role.name}")
                
        except Exception as e:
            logger.error(f"❌ Failed to update tier role for {member.name}: {e}")

    def _create_level_up_embed(self, username: str, old_level: int, new_level: int, total_xp: int) -> discord.Embed:
        """Create level-up celebration embed"""
        # Get tier info
        tier_info = get_level_tier(new_level)
        tier_name = tier_info["name"]
        color = tier_info["color"]
        tier_description = tier_info["description"]
        
        # Check milestone
        is_milestone = new_level % 5 == 0
        
        # Title
        if is_milestone:
            title = f"🎉 MILESTONE! Level {new_level} Reached! 🎉"
        else:
            title = f"⭐ Inventory Upgraded! Level {new_level} ⭐"
        
        # Description
        description = (
            f"**{username}** has leveled up!\n\n"
            f"**New Rank:** {tier_name}\n"
            f"*{tier_description}*"
        )
        
        # Create embed
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Fields
        embed.add_field(
            name="📊 Level",
            value=f"{old_level} → **{new_level}**",
            inline=True
        )
        
        embed.add_field(
            name="✨ Total XP",
            value=f"{total_xp:,}",
            inline=True
        )
        
        # Next Level XP - calculate remaining XP needed
        from Config import calculate_total_xp_for_level
        
        xp_for_next_level = calculate_total_xp_for_level(new_level + 1)
        xp_remaining = xp_for_next_level - total_xp
        
        embed.add_field(
            name="🎯 Next Level",
            value=f"{xp_remaining:,} XP more needed",
            inline=True
        )
        
        # Icon
        tier_key = "common"
        if new_level >= 50:
            tier_key = "legendary"
        elif new_level >= 30:
            tier_key = "epic"
        elif new_level >= 20:
            tier_key = "rare"
        elif new_level >= 10:
            tier_key = "uncommon"
        
        embed.set_thumbnail(url=LEVEL_ICONS[tier_key])
        
        # Footer
        embed.set_footer(text="Keep collecting! 🎒✨")
        
        return embed

    def _save_level_history(self, user_id: str, old_level: int, new_level: int, total_xp: int):
        """Save level-up to history"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now(timezone.utc).isoformat()
            
            cursor.execute("""
                INSERT INTO level_history (user_id, old_level, new_level, total_xp, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, old_level, new_level, total_xp, now))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Error saving level history: {e}")

    # Message Listener for automatic XP
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Give XP for messages (with cooldown)"""
        # Ignore bots
        if message.author.bot:
            return
        
        # Ignore DMs
        if not message.guild:
            return
        
        # Only process in our guild
        if message.guild.id != GUILD_ID:
            return
        
        try:
            # XP for message
            await self.add_xp(
                user_id=str(message.author.id),
                username=message.author.name,
                xp_type="message_sent"
            )
            
            # Extra XP for image
            if message.attachments:
                has_image = any(
                    att.content_type and att.content_type.startswith('image/')
                    for att in message.attachments
                )
                if has_image:
                    await self.add_xp(
                        user_id=str(message.author.id),
                        username=message.author.name,
                        xp_type="image_sent"
                    )
        except Exception as e:
            logger.error(f"❌ Error processing message XP: {e}")

    # =========================================================================
    # MOD PROMOTION FEATURE
    # =========================================================================

    async def handle_promote_mod(self, ctx_or_interaction, user: discord.Member):
        """Shared handler for mod promotion"""
        try:
            # Check if already mod
            if hasattr(ctx_or_interaction, 'guild'):
                guild = ctx_or_interaction.guild
                author = ctx_or_interaction.author if hasattr(ctx_or_interaction, 'author') else ctx_or_interaction.user
            else:
                guild = ctx_or_interaction.guild
                author = ctx_or_interaction.user
            
            mod_role = guild.get_role(MODERATOR_ROLE_ID)
            if not mod_role:
                msg = "❌ Moderator role not found in server!"
                if hasattr(ctx_or_interaction, 'response'):
                    await ctx_or_interaction.response.send_message(msg, ephemeral=True)
                else:
                    await ctx_or_interaction.send(msg)
                return
            
            if mod_role in user.roles:
                msg = f"❌ {user.mention} is already a moderator!"
                if hasattr(ctx_or_interaction, 'response'):
                    await ctx_or_interaction.response.send_message(msg, ephemeral=True)
                else:
                    await ctx_or_interaction.send(msg)
                return
            
            # Check bot permissions
            bot_member = guild.get_member(self.bot.user.id)
            if not bot_member:
                msg = "❌ Bot member not found in server!"
                if hasattr(ctx_or_interaction, 'response'):
                    await ctx_or_interaction.response.send_message(msg, ephemeral=True)
                else:
                    await ctx_or_interaction.send(msg)
                return
            
            # Check if bot has Manage Roles permission
            if not bot_member.guild_permissions.manage_roles:
                msg = "❌ Bot is missing `Manage Roles` permission!"
                if hasattr(ctx_or_interaction, 'response'):
                    await ctx_or_interaction.response.send_message(msg, ephemeral=True)
                else:
                    await ctx_or_interaction.send(msg)
                return
            
            # Check role hierarchy (bot's role must be above moderator role)
            if bot_member.top_role <= mod_role:
                msg = (
                    f"❌ **Cannot promote**: Bot's role position is too low!\n\n"
                    f"**Current Setup**:\n"
                    f"• Bot's highest role: {bot_member.top_role.mention} (Position: {bot_member.top_role.position})\n"
                    f"• Moderator role: {mod_role.mention} (Position: {mod_role.position})\n\n"
                    f"**Fix Required**:\n"
                    f"1. Open **Server Settings** → **Roles**\n"
                    f"2. Drag **{bot_member.top_role.name}** **above** **{mod_role.name}**\n"
                    f"3. Save changes and try again\n\n"
                    f"*The bot can only assign roles that are below its own role in the hierarchy.*"
                )
                if hasattr(ctx_or_interaction, 'response'):
                    await ctx_or_interaction.response.send_message(msg, ephemeral=True)
                else:
                    await ctx_or_interaction.send(msg)
                logger.warning(
                    f"⚠️ Cannot promote {user.name}: Bot role ({bot_member.top_role.name}) "
                    f"is not above Moderator role ({mod_role.name})"
                )
                return
            
            # Defer if interaction
            if hasattr(ctx_or_interaction, 'response'):
                await ctx_or_interaction.response.defer(ephemeral=True)
            
            # Add moderator role
            await user.add_roles(mod_role)
            logger.info(f"🛡️ {user.name} promoted to Moderator by {author.name}")
            
            # Save to database
            self._save_mod_promotion(
                user_id=str(user.id),
                promoted_by=str(author.id)
            )
            
            # Send celebration embed
            channel = self.bot.get_channel(LEVEL_UP_CHANNEL_ID)
            if channel:
                embed = self._create_mod_promotion_embed(user, author)
                message = await channel.send(
                    content=user.mention,  # Ping the promoted user
                    embed=embed
                )
                
                # Update database with message ID
                self._update_mod_promotion_message(str(user.id), str(message.id))
                
                logger.info(f"👑 Mod promotion celebration posted for {user.name}")
            
            # Confirm to admin
            msg = f"✅ {user.mention} has been promoted to **Moderator**! 🎉"
            if hasattr(ctx_or_interaction, 'followup'):
                await ctx_or_interaction.followup.send(msg, ephemeral=True)
            else:
                await ctx_or_interaction.send(msg)
            
        except Exception as e:
            logger.error(f"❌ Error promoting mod: {e}")
            msg = f"❌ Failed to promote moderator: {str(e)}"
            if hasattr(ctx_or_interaction, 'followup'):
                await ctx_or_interaction.followup.send(msg, ephemeral=True)
            elif hasattr(ctx_or_interaction, 'response'):
                await ctx_or_interaction.response.send_message(msg, ephemeral=True)
            else:
                await ctx_or_interaction.send(msg)

    # Prefix Command (!promotemod)
    @commands.command(name="promotemod")
    @commands.has_permissions(administrator=True)
    async def promote_mod_prefix(self, ctx: commands.Context, user: discord.Member):
        """Promote a user to moderator (Prefix command)"""
        await self.handle_promote_mod(ctx, user)

    # Slash Command (/promotemod)
    @app_commands.command(name="promotemod", description="👑 Promote a user to moderator (Admin only)")
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(user="The user to promote to moderator")
    async def promote_mod_slash(self, interaction: discord.Interaction, user: discord.Member):
        """Promote a user to moderator (Slash command)"""
        await self.handle_promote_mod(interaction, user)

    def _create_mod_promotion_embed(self, user: discord.Member, promoted_by: discord.Member) -> discord.Embed:
        """Create special mod promotion embed"""
        embed = discord.Embed(
            title="👑 MODERATOR PROMOTION 👑",
            description=(
                f"**{user.mention}** has been promoted to **Moderator**!\n\n"
                f"Welcome to the team! 🎉"
            ),
            color=0xFFD700,  # Gold
            timestamp=datetime.now(timezone.utc)
        )
        
        # User avatar
        embed.set_thumbnail(url=user.display_avatar.url)
        
        # Fields
        embed.add_field(
            name="👤 New Moderator",
            value=user.mention,
            inline=True
        )
        
        embed.add_field(
            name="🛡️ Promoted by",
            value=promoted_by.mention,
            inline=True
        )
        
        embed.add_field(
            name="📅 Date",
            value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>",
            inline=False
        )
        
        # Footer
        embed.set_footer(
            text="Good luck on the team!",
            icon_url=user.guild.icon.url if user.guild.icon else None
        )
        
        return embed

    def _save_mod_promotion(self, user_id: str, promoted_by: str):
        """Save mod promotion to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now(timezone.utc).isoformat()
            
            cursor.execute("""
                INSERT INTO mod_promotions (user_id, promoted_by, timestamp)
                VALUES (?, ?, ?)
            """, (user_id, promoted_by, now))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Error saving mod promotion: {e}")

    def _update_mod_promotion_message(self, user_id: str, message_id: str):
        """Update mod promotion with message ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Use subquery instead of ORDER BY in UPDATE (SQLite limitation)
            cursor.execute("""
                UPDATE mod_promotions
                SET message_id = ?
                WHERE rowid = (
                    SELECT rowid
                    FROM mod_promotions
                    WHERE user_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                )
            """, (message_id, user_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Error updating mod promotion message: {e}")
    
    # =========================================================================
    # MANUAL XP TESTING COMMANDS
    # =========================================================================

    async def handle_add_xp(self, ctx_or_interaction, user: discord.Member, amount: int, xp_type: str = "manual_bonus"):
        """Shared handler for adding XP manually"""
        try:
            # Defer if interaction
            if hasattr(ctx_or_interaction, 'response'):
                await ctx_or_interaction.response.defer(ephemeral=True)
            
            # Add XP
            result = await self.add_xp(
                user_id=str(user.id),
                username=user.name,
                xp_type=xp_type,
                amount=amount
            )
            
            author = ctx_or_interaction.author if hasattr(ctx_or_interaction, 'author') else ctx_or_interaction.user
            
            if result:
                level_info = f"Level {result['level']}"
                if result['leveled_up']:
                    level_info += " (⬆️ **LEVEL UP!**)"
                
                msg = (
                    f"✅ Added **{amount} XP** to {user.mention}\n"
                    f"📊 Total XP: {result['total_xp']}\n"
                    f"🎯 {level_info}"
                )
                
                if hasattr(ctx_or_interaction, 'followup'):
                    await ctx_or_interaction.followup.send(msg, ephemeral=True)
                else:
                    await ctx_or_interaction.send(msg)
                
                logger.info(f"🔧 Admin {author.name} added {amount} XP to {user.name}")
            else:
                msg = f"❌ Failed to add XP to {user.mention}"
                if hasattr(ctx_or_interaction, 'followup'):
                    await ctx_or_interaction.followup.send(msg, ephemeral=True)
                else:
                    await ctx_or_interaction.send(msg)
                
        except Exception as e:
            logger.error(f"❌ Error in add_xp_manual: {e}")
            msg = f"❌ Error: {str(e)}"
            if hasattr(ctx_or_interaction, 'followup'):
                await ctx_or_interaction.followup.send(msg, ephemeral=True)
            elif hasattr(ctx_or_interaction, 'response'):
                await ctx_or_interaction.response.send_message(msg, ephemeral=True)
            else:
                await ctx_or_interaction.send(msg)

    # Prefix Command (!addxp)
    @commands.command(name="addxp")
    @commands.has_permissions(administrator=True)
    async def add_xp_prefix(
        self,
        ctx: commands.Context,
        user: discord.Member,
        amount: int,
        xp_type: str = "manual_bonus"
    ):
        """Manually add XP to a user (Prefix command)"""
        await self.handle_add_xp(ctx, user, amount, xp_type)

    # Slash Command (/addxp)
    @app_commands.command(name="addxp", description="⭐ [ADMIN] Manually add XP to a user for testing")
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        user="The user to add XP to",
        amount="Amount of XP to add",
        xp_type="XP type (default: manual_bonus)"
    )
    async def add_xp_slash(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int,
        xp_type: str = "manual_bonus"
    ):
        """Manually add XP to a user (Slash command)"""
        await self.handle_add_xp(interaction, user, amount, xp_type)


async def setup(bot: commands.Bot):
    """Setup function to add the LevelSystem cog"""
    await bot.add_cog(LevelSystem(bot))
