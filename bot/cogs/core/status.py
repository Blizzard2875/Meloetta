import os

import psutil

import discord
from discord.ext import commands

from bot.utils import checks, tools

from bot.config import config as BOT_CONFIG


class Status(commands.Cog):
    """Bot status information."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='ping')
    async def ping(self, ctx):
        """Determines the bots current latency."""
        message = await ctx.send('Pong!')
        await message.edit(content=f'Pong! Latency: `{(message.created_at - ctx.message.created_at).total_seconds()}s`')

    @commands.command(name='info')
    async def info(self, ctx):
        """Sends some basic information about the bot."""
        prefix = BOT_CONFIG.PREFIXES[0]

        await ctx.send(
            embed=discord.Embed(
                title=f"I am {self.bot.user}, a bot made by {self.bot.owner}",
                description=f'I am a music bot, I play Pokémon music at random on loop, my prefix is `{prefix}`, you can request me with `{prefix}start`.',
                colour=self.bot.user.colour
            ).set_thumbnail(
                url=self.bot.user.avatar_url
            )
        )

    @commands.command(name='status')
    @commands.check(checks.is_owner)
    async def status(self, ctx):
        """Sends some debug information."""

        # Get lines of code
        lines_of_code = os.popen(
            r'find . -name "*.py" -exec cat {} \; | wc -l').read()

        # Get memory usage
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / 1024 ** 2

        await ctx.send(
            embed=discord.Embed(
                title=f'{self.bot.user.name} v{self.bot.__version__} Status',
                colour=self.bot.user.colour
            ).set_thumbnail(
                url=self.bot.user.avatar_url
            ).add_field(
                name='Users:', value=len(self.bot.users)
            ).add_field(
                name='Guilds:', value=len(self.bot.guilds)
            ).add_field(
                name='Started at:', value=tools.format_dt(self.bot._start_time)
            ).add_field(
                name='Memory usage:', value=f'{memory_usage:.2f} MB'
            ).add_field(
                name='Cogs loaded:', value=len(self.bot.cogs)
            ).add_field(
                name='Lines of code:', value=lines_of_code or 'Unknown'
            )
        )


def setup(bot: commands.Bot):
    bot.add_cog(Status(bot))
