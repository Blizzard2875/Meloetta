from discord.ext import commands

class Psychic(commands.Cog):
    def __init__(self, bot): 
        self.bot = bot

    @commands.command(name='horoscope')
    async def horoscope(self, ctx):
        """Sends your horoscope.
        
        [Here's an example](https://cdn.discordapp.com/attachments/266993218439217152/632237916755591190/horoscope3.png)
        """
        await ctx.send('Its too fuzzy to tell.')


def setup(bot):
    bot.add_cog(Psychic(bot))