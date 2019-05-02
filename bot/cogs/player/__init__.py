import discord
from discord.ext import commands

from bot.config import CONFIG as BOT_CONFIG

COG_CONFIG = BOT_CONFIG.COGS[__name__]

class Player(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        
        # TODO: Initialise initial bot instances
        pass

def setup(bot: commands.Bot):
    bot.add_cog(Player(bot))