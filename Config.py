# ============================================================================
# Configuration file for HazeBot
# ============================================================================
# This file contains all global constants and settings used across the bot's
# cogs and modules. Settings are organized by category for easy maintenance.
# ============================================================================

import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# ============================================================================
# ENVIRONMENT & MODE CONFIGURATION
# ============================================================================

# Production mode switch (set via .env file)
PROD_MODE = os.getenv("PROD_MODE", "false").lower() == "true"

# Bot token selection based on PROD_MODE
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN" if PROD_MODE else "TEST_DISCORD_BOT_TOKEN")

# Guild ID selection based on PROD_MODE
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID" if PROD_MODE else "DISCORD_TEST_GUILD_ID", "0"))

# Guild Name (optional, for display in admin interface)
GUILD_NAME = os.getenv("DISCORD_GUILD_NAME" if PROD_MODE else "DISCORD_TEST_GUILD_NAME", None)

# Data directory selection based on PROD_MODE
DATA_DIR = "Data" if PROD_MODE else "TestData"

# Analytics storage backend: "sqlite" or "json" (legacy)
# SQLite provides better performance, indexing, and query capabilities
# JSON is kept for backward compatibility
ANALYTICS_BACKEND = os.getenv("ANALYTICS_BACKEND", "sqlite").lower()
USE_SQLITE_ANALYTICS = ANALYTICS_BACKEND == "sqlite"

# Timezone configuration for consistent datetime display
TIMEZONE = os.getenv("TIMEZONE", "Europe/Berlin")

# API Server Port (used by APIServer cog and status monitoring)
API_PORT = int(os.getenv("API_PORT", "5070"))

# Uptime Kuma Monitoring (OPTIONAL)
# If set, /status command will show detailed monitoring data from Uptime Kuma
# If not set, /status will only show basic bot status (latency, guilds, uptime)
UPTIME_KUMA_URL = os.getenv("UPTIME_KUMA_URL")  # None if not set
# Disable Uptime Kuma in Test Mode to avoid network errors
UPTIME_KUMA_ENABLED = bool(UPTIME_KUMA_URL) and PROD_MODE

# Monitor Categories for grouping in status embed
UPTIME_KUMA_MONITORS = {
    "core": ["Health Check", "Auth Ping", "WebSocket"],
    "features": ["Tickets", "Discord OAuth", "Analytics"],
    "frontend": ["Frontend", "Admin"],
}


# Helper functions
def get_guild_id():
    """Returns the current guild ID based on PROD_MODE"""
    return GUILD_ID


def get_data_dir():
    """Returns the current data directory based on PROD_MODE"""
    return DATA_DIR


def get_local_now():
    """Returns current datetime in the configured timezone"""
    return datetime.now(ZoneInfo(TIMEZONE))


def get_utc_now():
    """Returns current datetime in UTC (for Discord embeds and API responses)"""
    return datetime.now(ZoneInfo("UTC"))


def local_to_utc(dt):
    """Convert a naive or local datetime to UTC"""
    if dt.tzinfo is None:
        # Assume it's in the configured timezone
        dt = dt.replace(tzinfo=ZoneInfo(TIMEZONE))
    return dt.astimezone(ZoneInfo("UTC"))


def utc_to_local(dt):
    """Convert a UTC datetime to the configured timezone"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo(TIMEZONE))


# ============================================================================
# XP/LEVEL SYSTEM CONFIGURATION
# ============================================================================

# XP Configuration
XP_CONFIG = {
    # Activity XP
    "message_sent": 2,  # Nachricht gesendet (mit Cooldown)
    "image_sent": 5,  # Bild gesendet
    "ticket_created": 10,  # Ticket erstellt
    "game_request": 8,  # Game Request gesendet
    # Meme Activities (REBALANCED - 12. Dez 2025)
    "meme_fetch": 2,  # Meme gefetched (from source/random) - REDUCED from 5
    "meme_post": 5,  # Gefetchtes Meme gepostet - NEW
    "meme_generate": 10,  # Custom Meme generiert - REDUCED from 15
    "meme_generate_post": 8,  # Generiertes Meme gepostet - NEW
    # Legacy XP types (kept for backward compatibility)
    "meme_fetched": 2,  # Alias for meme_fetch
    "meme_generated": 10,  # Alias for meme_generate
    # Rocket League XP
    "rl_account_linked": 20,  # RL Account verknüpft
    "rl_stats_checked": 5,  # RL Stats abgerufen
    # Mod Activities (Extra XP)
    "ticket_resolved": 25,  # Ticket geschlossen (Mod only)
    "ticket_claimed": 15,  # Ticket claimed (Mod only)
    # Level Calculation
    "base_xp_per_level": 100,  # Base XP für Level 1→2
    "xp_multiplier": 1.5,  # Multiplier pro Level (exponentiell)
    # Cooldowns (Spam-Prevention)
    "message_cooldown": 60,  # Sekunden zwischen XP für Messages
    "meme_fetch_cooldown": 30,  # Sekunden zwischen XP für Meme Fetches - NEW
    "daily_xp_cap": 500,  # Max XP pro Tag (optional, 0 = disabled)
}

# Level Tier Names (Inventory Style)
LEVEL_TIERS = {
    "legendary": {
        "min_level": 50,
        "name": "🗝️ Vault Keeper",
        "color": 0xFF0000,  # Rot (Legendary)
        "description": "Guardian of Legendary Treasures",
    },
    "epic": {
        "min_level": 30,
        "name": "💎 Crystal Hoarder",
        "color": 0xFF00FF,  # Pink (Epic)
        "description": "Collector of Epic Gems",
    },
    "rare": {
        "min_level": 20,
        "name": "🏺 Artifact Seeker",
        "color": 0x9B59B6,  # Lila (Rare)
        "description": "Hunter of Rare Relics",
    },
    "uncommon": {
        "min_level": 10,
        "name": "🎁 Chest Opener",
        "color": 0x3498DB,  # Blau (Uncommon)
        "description": "Finder of Hidden Chests",
    },
    "common": {
        "min_level": 1,
        "name": "🪙 Token Collector",
        "color": 0x2ECC71,  # Grün (Common)
        "description": "Starting the Journey",
    },
}

# Level Icon URLs (Twemoji) - Used in Flutter Admin Panel
LEVEL_ICONS = {
    "legendary": "https://twemoji.maxcdn.com/v/latest/svg/1f451.svg",  # 👑 Crown
    "epic": "https://twemoji.maxcdn.com/v/latest/svg/1f31f.svg",  # 🌟 Star
    "rare": "https://twemoji.maxcdn.com/v/latest/svg/1f48e.svg",  # 💎 Gem
    "uncommon": "https://twemoji.maxcdn.com/v/latest/svg/1f6e1.svg",  # 🛡️ Shield
    "common": "https://twemoji.maxcdn.com/v/latest/svg/1f3c5.svg",  # 🏅 Medal
}

# Level Tier Emojis - Used in Discord Bot
LEVEL_TIER_EMOJIS = {
    "legendary": "👑",  # Crown
    "epic": "⭐",  # Star
    "rare": "💎",  # Gem
    "uncommon": "🛡️",  # Shield
    "common": "🏅",  # Medal
}


def calculate_level(total_xp: int) -> int:
    """Berechnet Level basierend auf Total XP (exponentiell)"""
    level = 1
    xp_needed = XP_CONFIG["base_xp_per_level"]
    current_xp = total_xp

    while current_xp >= xp_needed:
        current_xp -= xp_needed
        level += 1
        xp_needed = int(xp_needed * XP_CONFIG["xp_multiplier"])

    return level


def calculate_xp_for_next_level(current_level: int) -> int:
    """Berechnet XP needed für nächstes Level"""
    xp_needed = XP_CONFIG["base_xp_per_level"]

    for i in range(1, current_level):
        xp_needed = int(xp_needed * XP_CONFIG["xp_multiplier"])

    return xp_needed


def calculate_total_xp_for_level(level: int) -> int:
    """Berechnet total XP needed um ein bestimmtes Level zu erreichen"""
    if level <= 1:
        return 0

    total = 0
    for i in range(1, level):
        total += calculate_xp_for_next_level(i)

    return total


def get_level_tier(level: int) -> dict:
    """Returns tier info for a given level (including name, color, and emoji)"""
    tier_key = None
    if level >= 50:
        tier_key = "legendary"
    elif level >= 30:
        tier_key = "epic"
    elif level >= 20:
        tier_key = "rare"
    elif level >= 10:
        tier_key = "uncommon"
    else:
        tier_key = "common"

    tier_info = LEVEL_TIERS[tier_key].copy()
    tier_info["emoji"] = LEVEL_TIER_EMOJIS[tier_key]

    # Convert color int to hex string for Frontend compatibility
    if isinstance(tier_info["color"], int):
        tier_info["color"] = f"#{tier_info['color']:06X}"

    return tier_info


# ============================================================================
# GENERAL BOT SETTINGS
# ============================================================================

BotName = "Haze World Bot"
CommandPrefix = "!"
PresenceUpdateInterval = 3600  # seconds between presence updates
MessageCooldown = 5  # seconds between user messages
FuzzyMatchingThreshold = 0.6  # similarity threshold (0.0-1.0)

# Discord Intents
Intents = discord.Intents.default()
Intents.members = True
Intents.message_content = True
Intents.presences = True  # Required for member status and activities

# Color Scheme
PINK = discord.Color(0xAD1457)

# Embed Footer Text
EMBED_FOOTER_TEXT = "Powered by Haze World 💖"

# Role Display Names
ROLE_NAMES = {
    "user": "🎒 Lootling",
    "mod": "📦 Slot Keeper",
    "admin": "🧊 Inventory Master",
}


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Global log level
LogLevel = logging.INFO

# Per-Cog Log Levels (override global level for specific cogs)
COG_LOG_LEVELS = {
    "RocketLeague": logging.DEBUG,
    # "DailyMeme": logging.WARNING,
    # "Welcome": logging.ERROR,
}

# Cog prefixes for logging (emoji + label)
COG_PREFIXES = {
    "AnalyticsManager": "📊 [AnalyticsManager]",
    "APIServer": "🌐 [APIServer]",
    "CogManager": "🔧 [CogManager]",
    "Changelog": "📝 [Changelog]",
    "DailyMeme": "🎭 [DailyMeme]",
    "DiscordLogging": "📡 [DiscordLogging]",
    "GamingHub": "🎮 [GamingHub]",
    "Leaderboard": "🏆 [Leaderboard]",
    "MemeGenerator": "🎨 [MemeGenerator]",
    "ModPerks": "🛡️ [ModPerks]",
    "Preferences": "⚙️ [Preferences]",
    "Presence": "👤 [Presence]",
    "Profile": "👤 [Profile]",
    "LevelSystem": "⭐ [LevelSystem]",
    "RocketLeague": "🚀 [RocketLeague]",
    "RoleInfo": "📋 [RoleInfo]",
    "ServerGuide": "🌟 [ServerGuide]",
    "SupportButtons": "🎫 [SupportButtons]",
    "TicketSystem": "🎫 [TicketSystem]",
    "TodoList": "✅ [TodoList]",
    "Utility": "🔧 [Utility]",
    "Warframe": "🎮 [Warframe]",
    "Welcome": "👋 [Welcome]",
}


# ============================================================================
# DISCORD SERVER IDS (Production & Test)
# ============================================================================

# Production IDs (Main Discord Server)
PROD_IDS = {
    # Roles
    "ADMIN_ROLE_ID": 1424466881862959294,
    "MODERATOR_ROLE_ID": 1427219729960931449,
    "NORMAL_ROLE_ID": 1424161475718807562,
    "MEMBER_ROLE_ID": 1424161475718807562,
    "CHANGELOG_ROLE_ID": 1426314743278473307,
    "MEME_ROLE_ID": 1433415594463596567,
    "LEVEL_NOTIFICATION_ROLE_ID": 1299450758823325807,  # Level-Up Notification Role (Prod)
    # Level Tier Roles (automatisch bei Level-Up zugewiesen)
    "LEVEL_TIER_ROLES": {
        "common": 1448603657514782842,  # Token Collector (Level 1-9)
        "uncommon": 1448603596676661300,  # Chest Opener (Level 10-19)
        "rare": 1448603554951594014,  # Artifact Seeker (Level 20-29)
        "epic": 1448603521430716487,  # Crystal Hoarder (Level 30-49)
        "legendary": 1448603426459091007,  # Vault Keeper (Level 50+)
    },
    # Interest Roles
    "INTEREST_ROLE_IDS": [
        1424465865297887345,  # Chat & Memes
        1424465951792828477,  # Creative Vibes
        1424466003102007359,  # Gaming & Chill
        1424466081547817183,  # Ideas & Projects
        1424466456866852956,  # Development
        1424466150330466434,  # Tech & Support
        1424466239618810019,  # Just Browsing
    ],
    "INTEREST_ROLES": {
        "Chat & Memes": 1424465865297887345,
        "Creative Vibes": 1424465951792828477,
        "Gaming & Chill": 1424466003102007359,
        "Ideas & Projects": 1424466081547817183,
        "Development": 1424466456866852956,
        "Tech & Support": 1424466150330466434,
        "Just Browsing": 1424466239618810019,
    },
    # Channels
    "CHANGELOG_CHANNEL_ID": 1424859282284871752,
    "LOG_CHANNEL_ID": 1433187806347526244,
    "WELCOME_RULES_CHANNEL_ID": 1424724535923703968,
    "WELCOME_PUBLIC_CHANNEL_ID": 1424164269775392858,
    "TODO_CHANNEL_ID": 1424862421650247730,
    "RL_CHANNEL_ID": 1425472657293443236,
    "MEME_CHANNEL_ID": 1433414228840284252,
    "SERVER_GUIDE_CHANNEL_ID": 1428693601268928582,
    "STATUS_CHANNEL_ID": 1446501233476243536,
    "TRANSCRIPT_CHANNEL_ID": 1428690310971785327,
    "GAMING_CHANNEL_ID": 1425472657293443236,  # TODO: Replace with actual gaming channel ID
    "LEVEL_UP_CHANNEL_ID": 1424490032051388538,  # Level-Up Gratulations Channel
    "COMMUNITY_POSTS_CHANNEL_ID": 1424490032051388538,  # Community Posts Channel
    # Categories
    "TICKETS_CATEGORY_ID": 1426113555974979625,
}

# Test IDs (Test Discord Server)
TEST_IDS = {
    # Roles
    "ADMIN_ROLE_ID": 1429722580608225340,
    "MODERATOR_ROLE_ID": 1429724374746923061,
    "NORMAL_ROLE_ID": 1429722417428692992,
    "MEMBER_ROLE_ID": 1429722417428692992,
    "CHANGELOG_ROLE_ID": 1429726011771060344,
    "MEME_ROLE_ID": 1433416262062702686,
    "LEVEL_NOTIFICATION_ROLE_ID": 1448431457121865779,  # Level-Up Notification Role (Test)
    # Level Tier Roles (automatisch bei Level-Up zugewiesen)
    "LEVEL_TIER_ROLES": {
        "common": 1448602128070479872,  # Token Collector (Level 1-9)
        "uncommon": 1448602170017452114,  # Chest Opener (Level 10-19)
        "rare": 1448602356877885493,  # Artifact Seeker (Level 20-29)
        "epic": 1448602446258765835,  # Crystal Hoarder (Level 30-49)
        "legendary": 1448602504383299726,  # Vault Keeper (Level 50+)
    },
    # Interest Roles
    "INTEREST_ROLE_IDS": [
        1429725562074566656,
        1429725652667596840,
        1429725708003049543,
        1429725752047173745,
        1429725801443758131,
        1429725837078560859,
        1429725869743538237,
    ],
    "INTEREST_ROLES": {
        "Chat & Memes": 1429725562074566656,
        "Creative Vibes": 1429725652667596840,
        "Gaming & Chill": 1429725708003049543,
        "Ideas & Projects": 1429725752047173745,
        "Development": 1429725801443758131,
        "Tech & Support": 1429725837078560859,
        "Just Browsing": 1429725869743538237,
    },
    # Channels
    "CHANGELOG_CHANNEL_ID": 1429724050305056819,
    "LOG_CHANNEL_ID": 1433187651191701688,
    "WELCOME_RULES_CHANNEL_ID": 1429722359534718976,
    "WELCOME_PUBLIC_CHANNEL_ID": 1429722992857976854,
    "TODO_CHANNEL_ID": 1429724097570541618,
    "RL_CHANNEL_ID": 1429804818481938463,
    "MEME_CHANNEL_ID": 1433416191204003960,
    "SERVER_GUIDE_CHANNEL_ID": 1429723224320770078,
    "STATUS_CHANNEL_ID": 1446935976193818635,
    "TRANSCRIPT_CHANNEL_ID": 1429732029645324359,
    "GAMING_CHANNEL_ID": 1429804818481938463,  # TODO: Replace with actual gaming channel ID
    "LEVEL_UP_CHANNEL_ID": 1448418996457046228,  # Test Level-Up Channel
    "COMMUNITY_POSTS_CHANNEL_ID": 1450218300683456553,  # Test Community Posts Channel
    # Categories
    "TICKETS_CATEGORY_ID": 1429723767445389352,
}

# Select active IDs based on PROD_MODE
CURRENT_IDS = PROD_IDS if PROD_MODE else TEST_IDS


# ============================================================================
# ROLES & PERMISSIONS
# ============================================================================

ADMIN_ROLE_ID = CURRENT_IDS["ADMIN_ROLE_ID"]
MODERATOR_ROLE_ID = CURRENT_IDS["MODERATOR_ROLE_ID"]
NORMAL_ROLE_ID = CURRENT_IDS["NORMAL_ROLE_ID"]
MEMBER_ROLE_ID = CURRENT_IDS["MEMBER_ROLE_ID"]
CHANGELOG_ROLE_ID = CURRENT_IDS["CHANGELOG_ROLE_ID"]

INTEREST_ROLE_IDS = CURRENT_IDS["INTEREST_ROLE_IDS"]
INTEREST_ROLES = CURRENT_IDS["INTEREST_ROLES"]


# ============================================================================
# CHANNELS & CATEGORIES
# ============================================================================

# General Channels
LOG_CHANNEL_ID = CURRENT_IDS["LOG_CHANNEL_ID"]
CHANGELOG_CHANNEL_ID = CURRENT_IDS["CHANGELOG_CHANNEL_ID"]

# Feature Channels
TODO_CHANNEL_ID = CURRENT_IDS["TODO_CHANNEL_ID"]
RL_CHANNEL_ID = CURRENT_IDS["RL_CHANNEL_ID"]
MEME_CHANNEL_ID = CURRENT_IDS.get("MEME_CHANNEL_ID")
MEME_ROLE_ID = CURRENT_IDS.get("MEME_ROLE_ID")
SERVER_GUIDE_CHANNEL_ID = CURRENT_IDS.get("SERVER_GUIDE_CHANNEL_ID")
STATUS_CHANNEL_ID = CURRENT_IDS.get("STATUS_CHANNEL_ID")
GAMING_CHANNEL_ID = CURRENT_IDS.get("GAMING_CHANNEL_ID")

# Level System
LEVEL_UP_CHANNEL_ID = CURRENT_IDS["LEVEL_UP_CHANNEL_ID"]
LEVEL_NOTIFICATION_ROLE_ID = CURRENT_IDS["LEVEL_NOTIFICATION_ROLE_ID"]
LEVEL_TIER_ROLES = CURRENT_IDS["LEVEL_TIER_ROLES"]

# Community Posts
COMMUNITY_POSTS_CHANNEL_ID = CURRENT_IDS["COMMUNITY_POSTS_CHANNEL_ID"]

# Welcome System
WELCOME_RULES_CHANNEL_ID = CURRENT_IDS["WELCOME_RULES_CHANNEL_ID"]
WELCOME_PUBLIC_CHANNEL_ID = CURRENT_IDS["WELCOME_PUBLIC_CHANNEL_ID"]

# Ticket System
TICKETS_CATEGORY_ID = CURRENT_IDS["TICKETS_CATEGORY_ID"]
TRANSCRIPT_CHANNEL_ID = CURRENT_IDS["TRANSCRIPT_CHANNEL_ID"]


# ============================================================================
# COMMANDS CONFIGURATION
# ============================================================================

# Slash Commands (available as /command)
SLASH_COMMANDS = [
    "help",
    "status",
    "meme",
    "creatememe",
    "rlstats",
    "setrlaccount",
    "unlinkrlaccount",
    "rocket",
    "ticket",
    "preferences",
    "roleinfo",
    "profile",
    "mod",
    "modpanel",
    "modoverview",
    "moddetails",
    "leaderboard",
    "optins",
    "todo-update",
    "warframe",
    "warframemarket",
]

# Admin-only Commands
ADMIN_COMMANDS = [
    "clear",
    "mod",
    "modpanel",
    "modoverview",
    "moddetails",
    "say",
    "changelog",
    "update_changelog_view",
    "optins",
    "todo-update",
    "adminrlstats",
    "restorecongratsview",
    "create-button",
    "server-guide",
    "load",
    "unload",
    "reload",
    "listcogs",
    "logs",
    "viewlogs",
    "coglogs",
    "sync",
    "refreshtemplates",
    "togglediscordlogs",
    "testdiscordlog",
    "testmeme",
    "memesubreddits",
    "addsubreddit",
    "removesubreddit",
    "resetsubreddits",
    "lemmycommunities",
    "addlemmy",
    "removelemmy",
    "resetlemmy",
    "memesources",
    "enablesource",
    "disablesource",
    "resetsources",
    "dailyconfig",
]

# Moderator Commands
MOD_COMMANDS = [
    "clear",
    "mod",
    "modpanel",
    "modoverview",
    "moddetails",
    "optins",
    "todo-update",
    "adminrlstats",
    "testmeme",
    "memesubreddits",
    "addsubreddit",
    "removesubreddit",
    "resetsubreddits",
    "lemmycommunities",
    "addlemmy",
    "removelemmy",
    "resetlemmy",
    "memesources",
    "enablesource",
    "disablesource",
    "resetsources",
    "dailyconfig",
]


# ============================================================================
# SERVER GUIDE CONFIGURATION
# ============================================================================

SERVER_GUIDE_CONFIG = {
    "title": "Welcome to the Chillventory! 🌟",
    "banner_url": "https://cdn.discordapp.com/attachments/1424848960333414581/1433070391051550871/welcometochillventory.png?ex=69035a4e&is=690208ce&hm=5d57c1ca0b18e9bc3c839530d0211ca3da952e3af0fb4b4d45712d2d20dddfdd",
    "fields": [
        {
            "name": "🎯 Get Started",
            "value": (
                "Click the buttons below to access our most important features!\n\n"
                "• **Help** – View all available commands\n"
                "• **Ticket** – Create a support ticket\n"
                "• **Profile** – Check your server profile\n"
                "• **Rocket League** – Track your RL ranks\n"
                "• **Warframe** – Market & game status (Beta)\n"
                "• **Preferences** – Configure your opt-ins & settings\n"
                "• **Meme** – Get memes posted to the meme channel"
            ),
            "inline": False,
        },
        {
            "name": "💡 Quick Tips",
            "value": (
                "Use `/help` anytime to discover more commands.\n"
                "Need assistance? Create a ticket and our team will help you!"
            ),
            "inline": False,
        },
    ],
    "footer_template": "Powered by {guild_name} 💖",
}


# ============================================================================
# STATUS DASHBOARD CONFIGURATION
# ============================================================================

STATUS_DASHBOARD_CONFIG = {
    "enabled": True,
    "update_interval_minutes": 5,  # How often to update the status embed
    "show_monitoring": True,  # Show Uptime Kuma data if available
}


# ============================================================================
# WELCOME SYSTEM
# ============================================================================

PERSISTENT_VIEWS_FILE = f"{DATA_DIR}/persistent_views.json"
ACTIVE_RULES_VIEWS_FILE = f"{DATA_DIR}/active_rules_views.json"

# Server Rules Text
RULES_TEXT = (
    "🌿 **1. Be kind and respectful to everyone.**\n"
    "✨ **2. No spam, flooding, or excessive self-promotion.**\n"
    "🔞 **3. NSFW content is permitted only inside a clearly labeled, age-verified channel.**\n"
    "🚫 **4. Illegal content and hate speech are strictly forbidden anywhere on the server.**\n"
    "🧑‍💼 **5. Follow the instructions of staff and moderators.**\n"
    "💖 **6. Keep the atmosphere calm, considerate, and positive.**\n\n"
    "By clicking 'Accept Rules' you agree to these guidelines and "
    "unlock full access to the server. Welcome to the lounge — enjoy your stay!"
)

# Welcome Messages (use {name} for username placeholder)
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
    "{name} discovered the hidden lounge of positivity — badge unlocked, mission: unwind. 🌟",
]

# Welcome Button Reply Messages (use {user} and {new_member} for mentions)
WELCOME_BUTTON_REPLIES = [
    "🎊 **LEGENDARY DROP!** {user} just summoned {new_member} into the chillventory vault! 📦",
    "✨ {user} equipped {new_member} with *Infinite Good Vibes +99* — welcome buff activated! 💫",
    "📦 **New inventory slot unlocked!** {user} warmly stores {new_member} in the premium lounge section! 🛋️",
    "🌟 Achievement unlocked: {user} successfully welcomed {new_member}! Friendship XP +100 🎮",
    "🛋️ **Sofa reservation confirmed!** {user} rolls out the red carpet for {new_member}! 🎭",
    "🎨 {user} adds a splash of positivity paint to {new_member}'s welcome canvas! Masterpiece! 🖼️",
    "🌿 **Rare plant spotted!** {user} places {new_member} in the zen garden of eternal chill! 🧘",
    "🎉 {user} throws legendary confetti bombs for {new_member}! The lounge is now 200% more sparkly! ✨",
    "🔥 **Epic combo!** {user} + {new_member} = Maximum vibes unlocked! The inventory is blessed! 🙏",
    "💎 {user} just found a rare gem: {new_member}! Added to the collection of awesome people! 💖",
    "🚀 **Mission success!** Agent {user} has secured {new_member} for the chill squad! Welcome aboard! 🎯",
    "🧘 {user} transmits good energy waves to {new_member}! Harmony level: MAXIMUM! 🌊",
]


# ============================================================================
# ROCKET LEAGUE CONFIGURATION
# ============================================================================

RL_ACCOUNTS_FILE = f"{DATA_DIR}/rl_accounts.json"
RL_CONGRATS_VIEWS_FILE = f"{DATA_DIR}/rl_congrats_views.json"

# Rocket League API Configuration
RL_CURRENT_SEASON = 35  # Current Rocket League Competitive Season (Update when new season starts)

# Rank Check Configuration
RL_RANK_CHECK_INTERVAL_HOURS = 3  # How often to check for rank changes
# Cache duration (2h 55min) - slightly less than check interval to avoid race conditions
RL_RANK_CACHE_TTL_SECONDS = 10500

# Rank Tier Order (lowest to highest)
RL_TIER_ORDER = [
    "Unranked",
    "Bronze I",
    "Bronze II",
    "Bronze III",
    "Silver I",
    "Silver II",
    "Silver III",
    "Gold I",
    "Gold II",
    "Gold III",
    "Platinum I",
    "Platinum II",
    "Platinum III",
    "Diamond I",
    "Diamond II",
    "Diamond III",
    "Champion I",
    "Champion II",
    "Champion III",
    "Grand Champion I",
    "Grand Champion II",
    "Grand Champion III",
    "Supersonic Legend",
]

# Rank Emojis
RANK_EMOJIS = {
    "Supersonic Legend": "<:ssl:1425389967030489139>",
    "Grand Champion III": "<:gc3:1425389956796518420>",
    "Grand Champion II": "<:gc2:1425389941810266162>",
    "Grand Champion I": "<:gc1:1425389930225471499>",
    "Champion III": "<:c3:1425389912651464824>",
    "Champion II": "<:c2:1425389901670776842>",
    "Champion I": "<:c1:1425389889796706374>",
    "Diamond III": "<:d3:1425389878673149962>",
    "Diamond II": "<:d2:1425389867197665361>",
    "Diamond I": "<:d1:1425389856229691462>",
    "Platinum III": "<:p3:1425389845328433213>",
    "Platinum II": "<:p2:1425389833706278923>",
    "Platinum I": "<:p1:1425389821706113055>",
    "Gold III": "<:g3:1425389810968690749>",
    "Gold II": "<:g2:1425389799463981217>",
    "Gold I": "<:g1:1425389788885811380>",
    "Silver III": "<:s3:1425389776852221982>",
    "Silver II": "<:s2:1425389768425996341>",
    "Silver I": "<:s1:1425389757940367411>",
    "Bronze III": "<:b3:1425389747282382919>",
    "Bronze II": "<:b2:1425389735819350056>",
    "Bronze I": "<:b1:1425389725652615209>",
    "Unranked": "<:unranked:1425389712276721725>",
}

# Rank Promotion Message Configuration
RL_RANK_PROMOTION_CONFIG = {
    "notification_prefix": "{user} 🚀 Rank Promotion Notification!",
    "embed_title": "🎉 Rank Promotion! 🎉",
    "embed_description": "Congratulations {user}! Your {playlist} rank has improved to {emoji} {rank}!",
}

# Congrats Button Reply Messages (use {user} and {ranked_user} for mentions)
RL_CONGRATS_REPLIES = [
    "Inventory alert: {user} congratulates {ranked_user} on the rank up! 📦",
    "{user} throws confetti for {ranked_user}'s epic rank promotion! 🎊",
    "New achievement unlocked: {user} cheers for {ranked_user}! 🏆",
    "{user} adds extra vibes to {ranked_user}'s rank up celebration! ✨",
    "Chillventory update: {user} says congrats to {ranked_user}! 😎",
    "{user} shares positivity confetti for {ranked_user}'s promotion! 🎉",
    "Rank stash expanded: {user} greets {ranked_user}'s new tier! 🌟",
    "{user} discovers {ranked_user} in the champion inventory! 🏅",
    "Realm of ranks welcomes {ranked_user}'s upgrade via {user}! 🚀",
    "{user} throws a party for {ranked_user}'s rank advancement! 🎈",
]


# ============================================================================
# DAILY MEME CONFIGURATION
# ============================================================================

MEME_SUBREDDITS_FILE = f"{DATA_DIR}/meme_subreddits.json"
MEME_LEMMY_FILE = f"{DATA_DIR}/meme_lemmy_communities.json"

# Default Reddit Subreddits
DEFAULT_MEME_SUBREDDITS = [
    "memes",
    "dankmemes",
    "me_irl",
    "wholesomememes",
    "AdviceAnimals",
    "MemeEconomy",
    "PrequelMemes",
    "gaming",
    "ProgrammerHumor",
    "okbuddyretard",
]

# Default Lemmy Communities (instance@community format)
DEFAULT_MEME_LEMMY = [
    "lemmy.world@memes",
    "lemmy.world@meirl",
    "lemmy.world@dankmemes",
    "lemmy.world@adhdmemes",
    "lemmy.world@autism",
    "lemmy.ml@memes",
]

# Active Meme Sources
# Available: "reddit", "lemmy"
# Removed: "4chan" (unstable URLs), "9gag" (low quality), "imgur" (inconsistent)
MEME_SOURCES = [
    "reddit",
    "lemmy",
]

# Meme Generator Configuration (Imgflip API)
IMGFLIP_USERNAME = os.getenv("IMGFLIP_USERNAME", "")
IMGFLIP_PASSWORD = os.getenv("IMGFLIP_PASSWORD", "")
MEME_TEMPLATES_CACHE_FILE = f"{DATA_DIR}/meme_templates.json"
MEME_TEMPLATES_CACHE_DURATION = 86400  # 24 hours


# ============================================================================
# OTHER COG DATA FILES
# ============================================================================

MOD_DATA_FILE = f"{DATA_DIR}/mod_data.json"
ACTIVITY_FILE = f"{DATA_DIR}/activity.json"
