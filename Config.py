# Configuration file for HazeWorldBot
# This file contains all global constants and settings used across the bot's cogs and modules.

import discord
import logging
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# === General Bot Settings ===
LogLevel = logging.INFO  # Set the logging level (INFO, DEBUG, WARNING, ERROR, CRITICAL)
CommandPrefix = "!"  # Prefix for text-based commands (e.g., !help)
BotName = "Haze World Bot"  # Display name of the bot
Intents = discord.Intents.default()  # Default intents
Intents.members = True  # Enable access to member information (e.g., for role checks)
Intents.message_content = True  # Enable access to message content (required for command parsing)
PresenceUpdateInterval = 3600  # Time in seconds between bot presence updates (e.g., status changes)
PINK = discord.Color(0xAD1457)  # Hot Pink color used for embeds and UI elements
FuzzyMatchingThreshold = 0.6  # Similarity threshold for fuzzy command matching (0.0 to 1.0, higher = stricter)
MessageCooldown = 5  # Cooldown in seconds between user messages to prevent spam

# === Environment-based Configuration ===
PROD_MODE = os.getenv("PROD_MODE", "false").lower() == "true"

# Bot token selection based on PROD_MODE
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN" if PROD_MODE else "TEST_DISCORD_BOT_TOKEN")

# Guild ID selection based on PROD_MODE
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID" if PROD_MODE else "DISCORD_TEST_GUILD_ID", "0"))

# Data directory selection based on PROD_MODE
DATA_DIR = "Data" if PROD_MODE else "TestData"


# Helper function to get current guild ID (for use in other files)
def get_guild_id():
    """Returns the current guild ID based on PROD_MODE"""
    return GUILD_ID


# Helper function to get current data directory (for use in other files)
def get_data_dir():
    """Returns the current data directory based on PROD_MODE"""
    return DATA_DIR


# Production IDs (Main Discord Server)
PROD_IDS = {
    "ADMIN_ROLE_ID": 1424466881862959294,
    "MODERATOR_ROLE_ID": 1427219729960931449,
    "NORMAL_ROLE_ID": 1424161475718807562,
    "MEMBER_ROLE_ID": 1424161475718807562,
    "CHANGELOG_ROLE_ID": 1426314743278473307,
    "CHANGELOG_CHANNEL_ID": 1424859282284871752,
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
    "TICKETS_CATEGORY_ID": 1426113555974979625,
    "TRANSCRIPT_CHANNEL_ID": 1428690310971785327,
    "WELCOME_RULES_CHANNEL_ID": 1424724535923703968,
    "WELCOME_PUBLIC_CHANNEL_ID": 1424164269775392858,
    "TODO_CHANNEL_ID": 1424862421650247730,
    "RL_CHANNEL_ID": 1425472657293443236,
}

# Test IDs (Test Discord Server)
TEST_IDS = {
    "ADMIN_ROLE_ID": 1429722580608225340,
    "MODERATOR_ROLE_ID": 1429724374746923061,
    "NORMAL_ROLE_ID": 1429722417428692992,
    "MEMBER_ROLE_ID": 1429722417428692992,
    "CHANGELOG_ROLE_ID": 1429726011771060344,
    "CHANGELOG_CHANNEL_ID": 1429724050305056819,
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
    "TICKETS_CATEGORY_ID": 1429723767445389352,
    "TRANSCRIPT_CHANNEL_ID": 1429732029645324359,
    "WELCOME_RULES_CHANNEL_ID": 1429722359534718976,
    "WELCOME_PUBLIC_CHANNEL_ID": 1429722992857976854,
    "TODO_CHANNEL_ID": 1429724097570541618,
    "RL_CHANNEL_ID": 1429804818481938463,
}

# Select IDs based on PROD_MODE
CURRENT_IDS = PROD_IDS if PROD_MODE else TEST_IDS

# === Roles and Permissions ===
ADMIN_ROLE_ID = CURRENT_IDS["ADMIN_ROLE_ID"]
MODERATOR_ROLE_ID = CURRENT_IDS["MODERATOR_ROLE_ID"]
NORMAL_ROLE_ID = CURRENT_IDS["NORMAL_ROLE_ID"]
MEMBER_ROLE_ID = CURRENT_IDS["MEMBER_ROLE_ID"]
CHANGELOG_ROLE_ID = CURRENT_IDS["CHANGELOG_ROLE_ID"]
CHANGELOG_CHANNEL_ID = CURRENT_IDS["CHANGELOG_CHANNEL_ID"]

INTEREST_ROLE_IDS = CURRENT_IDS["INTEREST_ROLE_IDS"]
INTEREST_ROLES = CURRENT_IDS["INTEREST_ROLES"]

# === Commands ===
SLASH_COMMANDS = [
    "help",
    "status",
    "rlstats",
    "setrlaccount",
    "unlinkrlaccount",
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
]  # Commands that have slash (/) versions
ADMIN_COMMANDS = [
    "clear",
    "mod",
    "modpanel",
    "modoverview",
    "moddetails",
    "say",
    "changelog",
    "optins",
    "todo-update",
    "adminrlstats",
    "create-button",
]  # Commands restricted to Admins only
MOD_COMMANDS = [
    "clear",
    "mod",
    "modpanel",
    "modoverview",
    "moddetails",
    "optins",
    "todo-update",
    "adminrlstats",
]  # Commands restricted to Moderators (Slot Keepers) only

# === Rocket League ===
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
RL_ACCOUNTS_FILE = f"{DATA_DIR}/rl_accounts.json"
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

# === Mod Perks ===
MOD_DATA_FILE = f"{DATA_DIR}/mod_data.json"

# === Leaderboard ===
ACTIVITY_FILE = f"{DATA_DIR}/activity.json"

# === Ticket System ===
TICKETS_CATEGORY_ID = CURRENT_IDS["TICKETS_CATEGORY_ID"]
TRANSCRIPT_CHANNEL_ID = CURRENT_IDS["TRANSCRIPT_CHANNEL_ID"]

# === Welcome ===
WELCOME_RULES_CHANNEL_ID = CURRENT_IDS["WELCOME_RULES_CHANNEL_ID"]
WELCOME_PUBLIC_CHANNEL_ID = CURRENT_IDS["WELCOME_PUBLIC_CHANNEL_ID"]
PERSISTENT_VIEWS_FILE = f"{DATA_DIR}/persistent_views.json"  # File for persistent welcome card views
ACTIVE_RULES_VIEWS_FILE = f"{DATA_DIR}/active_rules_views.json"  # File for active rules acceptance views
RL_CONGRATS_VIEWS_FILE = f"{DATA_DIR}/rl_congrats_views.json"  # File for persistent congrats views

# === Todo List ===
TODO_CHANNEL_ID = CURRENT_IDS["TODO_CHANNEL_ID"]

# === Rocket League ===
RL_CHANNEL_ID = CURRENT_IDS["RL_CHANNEL_ID"]
