"""
Level System Helper Functions for Flask API
============================================
Provides XP tracking for API endpoints (used by Flutter app)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def award_xp_from_api(bot, user_id: str, username: str, xp_type: str, amount: int = None) -> Optional[dict]:
    """
    Award XP to a user from API endpoints
    
    Args:
        bot: Discord bot instance
        user_id: Discord User ID (as string)
        username: Discord Username
        xp_type: Activity type (from XP_CONFIG keys)
        amount: Optional XP override
    
    Returns:
        Dict with xp_gained, total_xp, level, leveled_up or None
    """
    try:
        if not bot:
            logger.warning("⚠️ Bot instance not available for XP tracking")
            return None
        
        # Get LevelSystem cog
        level_cog = bot.get_cog("LevelSystem")
        if not level_cog:
            logger.warning("⚠️ LevelSystem cog not loaded")
            return None
        
        # Use bot's event loop to run async function
        import asyncio
        loop = bot.loop
        
        future = asyncio.run_coroutine_threadsafe(
            level_cog.add_xp(user_id, username, xp_type, amount),
            loop
        )
        
        result = future.result(timeout=5)
        
        if result and result.get("leveled_up"):
            logger.info(f"🎉 {username} leveled up to {result['level']} via API!")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Failed to award XP from API: {e}")
        return None
