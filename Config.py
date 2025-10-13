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
SLASH_COMMANDS = ["help", "status", "rlstats", "setrlaccount", "ticket", "preferences"]  # Liste der Befehle mit Slash-Version
ADMIN_COMMANDS = ["clear", "say", "generatechangelog"]  # List of admin-only commands
FuzzyMatchingThreshold = 0.6  # Threshold for fuzzy command matching (0.0 to 1.0)
MessageCooldown = 5  # Cooldown in seconds between user messages