import os

import psutil

import discord
from discord.ext import commands

from bot.utils import checks, tools


class Status(commands.Cog):
    """Bot status information."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='ping')
    @commands.check(checks.is_owner)
    async def ping(self, ctx: commands.Context):
        """Determines the bots current latency."""
        message = await ctx.send('Pong!')
        await message.edit(content=f'Pong! Latency: `{(message.created_at - ctx.message.created_at).total_seconds()}s`')

    @commands.command(name='status')
    @commands.check(checks.is_owner)
    async def status(self, ctx: commands.Context):
        """Sends some basic information about the bot."""

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
                name='Memory usage:', value=f'{round(memory_usage, 2)} MB'
            ).add_field(
                name='Cogs loaded:', value=len(self.bot.cogs)
            ).add_field(
                name='Lines of code:', value=lines_of_code or 'Unknown'
            ).add_field(
                name='Quick links:',
                value=f'[Source Code](https://github.com/rpokemon/Meloetta)',
                inline=False
            )
        )


def setup(bot: commands.Bot):
    bot.add_cog(Status(bot))
