#!/usr/bin/env python3
"""
Manual Level-Up Notification Script
Sends a Level 1 → 2 celebration embed for .inventory
"""

import asyncio
import discord
from discord.ext import commands
import os
import sys
from pathlib import Path

# Add parent directory to path to import Config
sys.path.insert(0, str(Path(__file__).parent.parent))

import Config

# Bot setup (minimal intents needed)
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Bot connected as {bot.user}")
    
    # Get channel
    channel = bot.get_channel(Config.LEVEL_UP_CHANNEL_ID)
    if not channel:
        print(f"❌ Level-Up channel not found: {Config.LEVEL_UP_CHANNEL_ID}")
        await bot.close()
        return
    
    # User info
    user_id = "283733417575710721"
    username = ".inventory"
    old_level = 1
    new_level = 2
    total_xp = 103
    
    # Tier info for Level 2 (common tier)
    tier_name = "🪙 Token Collector"
    tier_description = "Starting the Journey"
    color = 0x2ECC71  # Green
    
    # Build embed
    title = "⭐ Inventory Upgraded! Level 2 ⭐"
    description = f"**{username}** has leveled up!\n\n**New Rank:** {tier_name}\n*{tier_description}*"
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow()
    )
    
    # Fields
    embed.add_field(name="📊 Level", value=f"{old_level} → **{new_level}**", inline=True)
    embed.add_field(name="✨ Total XP", value=f"{total_xp:,}", inline=True)
    
    # Calculate XP needed for next level
    xp_for_next_level = Config.calculate_xp_for_next_level(new_level)
    xp_for_current_level = Config.calculate_total_xp_for_level(new_level)
    xp_remaining = (xp_for_current_level + xp_for_next_level) - total_xp
    
    embed.add_field(name="🎯 Next Level", value=f"{xp_remaining:,} XP more needed", inline=True)
    
    # Icon
    embed.set_thumbnail(url="https://twemoji.maxcdn.com/v/latest/svg/1f3c5.svg")  # 🏅 Medal
    
    # Footer
    embed.set_footer(text="Keep collecting! 🎒✨")
    
    # Send to channel
    try:
        await channel.send(content=f"<@{user_id}>", embed=embed)
        print(f"✅ Level-Up notification sent to channel!")
    except Exception as e:
        print(f"❌ Failed to send message: {e}")
    
    # Close bot
    await bot.close()


# Run bot
if __name__ == "__main__":
    print("🚀 Starting manual level-up notification...")
    bot.run(Config.BOT_TOKEN)
