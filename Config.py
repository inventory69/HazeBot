# Configuration file for HazeWorldBot
# This file contains all global constants and settings used across the bot's cogs and modules.

import discord
import logging

# === General Bot Settings ===
LogLevel = logging.INFO  # Set the logging level (INFO, DEBUG, WARNING, ERROR, CRITICAL)
CommandPrefix = "!"  # Prefix for text-based commands (e.g., !help)
BotName = "Haze World Bot"  # Display name of the bot
Intents = discord.Intents.default()  # Default intents
Intents.members = True  # Enable access to member information (e.g., for role checks)
Intents.message_content = (
    True  # Enable access to message content (required for command parsing)
)
PresenceUpdateInterval = (
    3600  # Time in seconds between bot presence updates (e.g., status changes)
)
PINK = discord.Color(0xAD1457)  # Hot Pink color used for embeds and UI elements
FuzzyMatchingThreshold = 0.6  # Similarity threshold for fuzzy command matching (0.0 to 1.0, higher = stricter)
MessageCooldown = 5  # Cooldown in seconds between user messages to prevent spam

# === Roles and Permissions ===
ADMIN_ROLE_ID = 1424466881862959294  # Role ID for Admins (full permissions)
MODERATOR_ROLE_ID = 1427219729960931449  # Role ID for Slot Keepers (Moderators)
NORMAL_ROLE_ID = 1424161475718807562  # Role ID for Lootlings (regular members)
MEMBER_ROLE_ID = 1424161475718807562  # Alias for NORMAL_ROLE_ID, used in Welcome
CHANGELOG_ROLE_ID = 1426314743278473307  # Role ID for Changelog Notifications

INTEREST_ROLE_IDS = [
    1424465865297887345,  # Chat & Memes
    1424465951792828477,  # Creative Vibes
    1424466003102007359,  # Gaming & Chill
    1424466081547817183,  # Ideas & Projects
    1424466456866852956,  # Development
    1424466150330466434,  # Tech & Support
    1424466239618810019,  # Just Browsing
]
INTEREST_ROLES = {
    "Chat & Memes": 1424465865297887345,
    "Creative Vibes": 1424465951792828477,
    "Gaming & Chill": 1424466003102007359,
    "Ideas & Projects": 1424466081547817183,
    "Development": 1424466456866852956,
    "Tech & Support": 1424466150330466434,
    "Just Browsing": 1424466239618810019,
}

# === Commands ===
SLASH_COMMANDS = [
    "help",
    "status",
    "rlstats",
    "setrlaccount",
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
    "todo-show",
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
]  # Commands restricted to Admins only
MOD_COMMANDS = [
    "clear",
    "mod",
    "modpanel",
    "modoverview",
    "moddetails",
    "optins",
    "todo-update",
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
RL_ACCOUNTS_FILE = "Data/rl_accounts.json"
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
MOD_DATA_FILE = "Data/mod_data.json"

# === Leaderboard ===
ACTIVITY_FILE = "Data/activity.json"

# === Ticket System ===
TICKETS_CATEGORY_ID = 1426113555974979625

# === Welcome ===
WELCOME_RULES_CHANNEL_ID = 1424724535923703968
WELCOME_PUBLIC_CHANNEL_ID = 1424164269775392858
PERSISTENT_VIEWS_FILE = (
    "Data/persistent_views.json"  # File for persistent welcome card views
)
ACTIVE_RULES_VIEWS_FILE = (
    "Data/active_rules_views.json"  # File for active rules acceptance views
)
