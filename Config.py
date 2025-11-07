# ============================================================================
# Configuration file for HazeBot
# ============================================================================
# This file contains all global constants and settings used across the bot's
# cogs and modules. Settings are organized by category for easy maintenance.
# ============================================================================

import discord
import logging
from dotenv import load_dotenv
import os

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


# Helper functions
def get_guild_id():
    """Returns the current guild ID based on PROD_MODE"""
    return GUILD_ID


def get_data_dir():
    """Returns the current data directory based on PROD_MODE"""
    return DATA_DIR


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
    "CogManager": "🔧 [CogManager]",
    "Changelog": "📝 [Changelog]",
    "DailyMeme": "🎭 [DailyMeme]",
    "DiscordLogging": "📡 [DiscordLogging]",
    "Leaderboard": "🏆 [Leaderboard]",
    "MemeGenerator": "🎨 [MemeGenerator]",
    "ModPerks": "🛡️ [ModPerks]",
    "Preferences": "⚙️ [Preferences]",
    "Presence": "👤 [Presence]",
    "Profile": "👤 [Profile]",
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
    "TRANSCRIPT_CHANNEL_ID": 1428690310971785327,
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
    "TRANSCRIPT_CHANNEL_ID": 1429732029645324359,
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
