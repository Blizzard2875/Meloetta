import asyncio
import os

import discord
from discord.ext import commands


class Git(commands.Cog):
    """Commands for managing the bot"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        """You must be the bot owner to use this command."""
        return self.bot.is_owner(ctx.author)

    @commands.command(name="load", hidden=True)
    async def load(self, ctx: commands.Context, cog: str):
        """Loads a cog."""
        cog = f"bot.cogs.{cog}"

        self.bot.load_extension(cog)
        await ctx.send(embed=discord.Embed(
            title=f"Succesfully loaded extension: {cog}",
            colour=0xf44336
        ))

    @commands.command(name="unload", hidden=True)
    async def unload(self, ctx: commands.Context, cog: str):
        """Unoads a cog."""
        cog = f"bot.cogs.{cog}"

        self.bot.unload_extension(cog)
        await ctx.send(embed=discord.Embed(
            title=f"Succesfully unloaded extension: {cog}",
            colour=0xf44336
        ))

    @commands.command(name="reload", hidden=True)
    async def reload(self, ctx: commands.Context, cog: str):
        """Reloads a cog."""
        cog = f"bot.cogs.{cog}"

        try:
            self.bot.reload_extension(cog)
        except commands.ExtensionNotLoaded:
            return await ctx.invoke(self.load, cog=cog)


        await ctx.send(embed=discord.Embed(
            title=f"Succesfully reloaded extension: {cog}",
            colour=0xf44336
        ))

    @commands.command(name="pull", hidden=True)
    async def pull(self, ctx: commands.Context):
        """Pulls the most recent version of the repository."""
        resp = os.popen("git pull").read()

        if len(resp) > 1024:
            resp = resp[:1020] + '...'

        embed = discord.Embed(
            title="Git pull...",
            description=f"```diff\n{resp}\n```",
            colour=0x009688,
        )

        if 'Pipfile.lock' in resp:
            embed.add_field(
                name="Pipflie.lock was modified!",
                value='Please ensure you install the latest packages before restarting.'
            )

        await ctx.send(embed=embed)

    @commands.command(name="restart", hidden=True)
    async def restart(self, ctx: commands.Context, *, arg: str = None):
        """Restarts the bot."""
        if arg == "pull":
            await ctx.invoke(self.pull)
        await self.bot.logout()


def setup(bot: commands.Bot):
    bot.add_cog(Git(bot))
