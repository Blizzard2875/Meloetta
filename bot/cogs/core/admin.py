import copy
import io
import textwrap
import traceback

from contextlib import redirect_stdout
from typing import Union

import discord
from discord.ext import commands

from bot.utils import checks, tools

from bot.config import config as BOT_CONFIG

# Extra imports for eval
import asyncio
import datetime
import inspect
import os
import re


class Code:

    @classmethod
    async def convert(cls, ctx: commands.Context, argument: str):
        if argument.startswith('```') and argument.endswith('```'):
            return '\n'.join(argument.split('\n')[1:-1])
        return argument.strip('` \n')


class Admin(commands.Cog):
    """Administrative commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last_result = None  # For eval env

    async def cog_check(self, ctx: commands.Context) -> bool:
        return await checks.is_owner(ctx)

    @commands.command(name="nuke")
    async def nuke(self, ctx: commands.Context, limit: int, *, user: discord.Member = None):
        """Deletes a set number of messages from the channel.

        `limit`: the number of messages to delete
        `user[Optional]`: If specified will only delete messages from this user
        """
        prompt_message = await ctx.send(f"Are you sure you want to delete {limit} messages from <#{ctx.channel.id}>?")
        if (await tools.prompt(ctx, prompt_message)):
            def user_check(message: discord.Message):
                if user is not None:
                    return user == message.author
                return True

            await ctx.message.delete()
            await ctx.channel.purge(limit=limit, check=user_check)

    @commands.command(name='eval')
    async def eval(self, ctx: commands.Context, *, body: Code):
        """Evaluates python code.

        `code`: Python code to evaluate.
        """
        env = {
            'CONFIG': BOT_CONFIG,
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': self._last_result
        }

        env.update(globals())

        stdout = io.StringIO()

        try:
            exec(f'async def func():\n{textwrap.indent(body, "  ")}', env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()

            if ret is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                self._last_result = ret
                await ctx.send(f'```py\n{value}{ret}\n```')

    @commands.command(name="sudo")
    async def sudo(self, ctx, user: Union[discord.Member, discord.User], *, command: str):
        """Run a command as another user."""
        msg = copy.copy(ctx.message)
        msg.author = user
        msg.content = ctx.prefix + command
        new_ctx = await self.bot.get_context(msg)
        try:
            await self.bot.invoke(new_ctx)
        except commands.CommandInvokeError as e:
            raise e.original


def setup(bot: commands.Bot):
    bot.add_cog(Admin(bot))
