from discord.ext import commands


class Context(commands.Context):
    ...

    async def check(self, emoji: str = '\N{WHITE HEAVY CHECK MARK}'):
        await self.message.add_reaction(emoji)
