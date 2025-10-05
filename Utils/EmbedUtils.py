def set_pink_footer(embed, bot=None, user=None, text="Powered by Haze World 💖"):
    """
    Setzt einen pinken Footer für Embeds.
    - Wenn user angegeben: dessen Avatar wird genutzt.
    - Wenn kein user, aber bot angegeben: Bot-Avatar wird genutzt.
    - Wenn weder user noch bot: nur Text, kein Avatar.
    """
    if user is not None:
        embed.set_footer(text=text, icon_url=getattr(user.avatar, 'url', None))
    elif bot is not None:
        embed.set_footer(text=text, icon_url=getattr(bot.avatar, 'url', None))
    else:
        embed.set_footer(text=text)
    return embed