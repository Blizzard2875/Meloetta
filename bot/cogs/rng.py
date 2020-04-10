import random
import hashlib
import re

# import discord
from discord.ext import commands


class Random(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='rate')
    async def rate(self, ctx: commands.Context, *, thing: commands.clean_content):
        """Rates something out of 10

        `thing`: The thing to rate.
        """
        rating = int(hashlib.md5(re.sub(r'\W+', '', thing.lower()).encode('utf-8')).hexdigest(), 16) % 11
        await ctx.send(f'I rate {thing} a {rating}/10.')

    @commands.command(name='choose')
    async def choose(self, ctx, *choices: commands.clean_content):
        """Chooses between multiple options.

        `choices`: The list of choices to choose from, separated by a space. Multiple word options should be surrounded in quotes.
        """
        if len(choices) < 2:
            return await ctx.send('Not enough choices to pick from.')

        await ctx.send(random.choice(choices))


def setup(bot: commands.Bot):
    bot.add_cog(Random(bot))
