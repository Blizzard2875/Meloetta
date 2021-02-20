import discord
from discord.ext import commands

import wavelink

from bot import Bot, Context


class Player(commands.Cog, wavelink.WavelinkMixin):
    def __init__(self, bot: Bot):
        self.bot = bot


def setup(self, bot: Bot):

    # Check for player botvars
    if not hasattr(bot, 'wavelink'):
        bot.wavelink = wavelink.Client(bot)

    bot.add_cog(Player(bot))
