from typing import Optional

import discord
from discord.ext import commands

import Config


def set_pink_footer(
    embed: discord.Embed,
    bot: Optional[commands.Bot] = None,
    user: Optional[discord.User] = None,
    text: Optional[str] = None,
) -> discord.Embed:
    """
    Sets a pink footer for embeds.
    - If user is specified: uses their avatar.
    - If no user but bot is specified: uses bot avatar.
    - If neither user nor bot: only text, no avatar.
    - text: Optional custom text, defaults to Config.EMBED_FOOTER_TEXT
    """
    if text is None:
        text = Config.EMBED_FOOTER_TEXT

    if user is not None:
        embed.set_footer(text=text, icon_url=getattr(user.avatar, "url", None))
    elif bot is not None:
        embed.set_footer(text=text, icon_url=getattr(bot.avatar, "url", None))
    else:
        embed.set_footer(text=text)
    return embed
