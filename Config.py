import discord

CommandPrefix = "!"
BotName = "Haze World Bot"
Intents = discord.Intents.default()
Intents.members = True
Intents.message_content = True
PINK = discord.Color(0xAD1457)  # Hot Pink für Embeds

SLASH_COMMANDS = ["help", "status", "rlstats", "setrlaccount", "ticket"]