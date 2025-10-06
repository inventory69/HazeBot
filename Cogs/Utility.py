from discord.ext import commands
import discord
from Config import BotName, PINK
from Utils.EmbedUtils import set_pink_footer
from Utils.Logger import log_clear

ADMIN_ROLE_ID = 1424466881862959294  # Admin role ID

class Utility(commands.Cog):
    """
    🛠️ Utility Cog: Provides standard commands like help and status.
    Modular and easy to extend!
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_command(self, ctx):
        """
        📖 Shows all available commands with their descriptions.
        Only admin-only commands are shown to users with the Admin role.
        """
        embed = discord.Embed(
            title=f"{BotName} Help",
            description="Here are all available commands:",
            color=PINK
        )
        for cog_name, cog in self.bot.cogs.items():
            commands_list = []
            for cmd in cog.get_commands():
                # Check if command is admin-only (by docstring or name)
                is_admin_only = cmd.name in ["clear", "say"]  # Add more admin-only commands here
                if is_admin_only and not any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles):
                    continue  # Skip admin-only commands for non-admins
                if not cmd.hidden:
                    commands_list.append(cmd)
            if commands_list:
                value = "\n".join([f"**!{cmd.name}** – {cmd.help or 'No description'}" for cmd in commands_list])
                embed.add_field(name=cog_name, value=value, inline=False)
        embed.set_footer(text="Powered by Haze World 💖", icon_url=getattr(self.bot.user.avatar, 'url', None))
        await ctx.send(embed=embed)

    @commands.command(name="status")
    async def status(self, ctx):
        """
        💖 Shows bot status and basic info in pink.
        """
        embed = discord.Embed(
            title=f"{BotName} Status",
            description="The bot is online and fabulous! 💖",
            color=PINK
        )
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)} ms")
        embed.add_field(name="Guilds", value=f"{len(self.bot.guilds)}")
        set_pink_footer(embed, bot=self.bot.user)  # Use bot avatar in footer
        await ctx.send(embed=embed)

    @commands.command(name="clear")
    async def clear(self, ctx, amount: int = 10):
        """
        Deletes the last X messages in the channel (default: 10).
        Only allowed for users with the Admin role.
        """
        # Check if user has the Admin role by ID
        if not any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles):
            embed = discord.Embed(
                description="🚫 You do not have permission to use this command.",
                color=discord.Color.red()
            )
            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed, delete_after=5)
            return

        # Purge messages (+1 to also delete the command message itself)
        deleted = await ctx.channel.purge(limit=amount + 1)
        embed = discord.Embed(
            description=f"🧹 {len(deleted)-1} messages have been deleted.",
            color=PINK
        )
        set_pink_footer(embed, bot=self.bot.user)
        msg = await ctx.send(embed=embed)
        await msg.delete(delay=30)  # Delete confirmation after 3 seconds
        log_clear(ctx.channel, ctx.author, len(deleted)-1)

    @commands.command(name="say")
    async def say(self, ctx, *, message: str):
        """
        Allows an admin to send a message as the bot in the current channel.
        Usage: !say --embed your message here
        If --embed is included directly after !say, the message will be sent as an embed.
        """
        # Check if user has the Admin role by ID
        if not any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles):
            embed = discord.Embed(
                description="🚫 You do not have permission to use this command.",
                color=discord.Color.red()
            )
            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed, delete_after=5)
            return

        await ctx.message.delete()

        # Check for --embed flag at the start of the message
        if message.startswith("--embed "):
            message = message[8:].strip()
            embed = discord.Embed(
                description=message,
                color=PINK
            )
            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed)
        else:
            await ctx.send(message)

async def setup(bot):
    """
    Setup function to add the Utility cog.
    """
    await bot.add_cog(Utility(bot))