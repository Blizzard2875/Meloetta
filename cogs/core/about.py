import discord
from discord.ext import commands

from bot import Bot, Context


class About(commands.Cog):

    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.command(name='about', aliases=['info'])
    async def about(self, ctx: Context):
        owners = ','.join(owner.mention for owner in self.bot.owners)

        embed = discord.Embed(
            colour=ctx.me.colour,
            description=f'{ctx.me.name} is a music bot developed by {owners}'
        ).set_author(name=f'About {ctx.me}', icon_url=ctx.me.avatar_url)

        await ctx.send(embed=embed)


def setup(bot: Bot):
    bot.add_cog(About(bot))
