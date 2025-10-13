import discord
import logging

LogLevel = logging.INFO
CommandPrefix = "!"
BotName = "Haze World Bot"
Intents = discord.Intents.default()
Intents.members = True
Intents.message_content = True
PresenceUpdateInterval = 3600  # 1 hour in seconds
PINK = discord.Color(0xAD1457)  # Hot Pink für Embeds
ADMIN_ROLE_ID = 1424466881862959294
MODERATOR_ROLE_ID = 1427219729960931449
NORMAL_ROLE_ID = 1424161475718807562
SLASH_COMMANDS = ["help", "status", "rlstats", "setrlaccount", "ticket", "preferences", "roleinfo"]  # Liste der Befehle mit Slash-Version
ADMIN_COMMANDS = ["clear", "modpanel", "say", "generatechangelog"]  # List of admin-only commands
MOD_COMMANDS = ["clear", "modpanel"]  # List of mod-only commands
FuzzyMatchingThreshold = 0.6  # Threshold for fuzzy command matching (0.0 to 1.0)
MessageCooldown = 5  # Cooldown in seconds between user messages