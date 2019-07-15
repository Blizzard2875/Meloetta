import asyncio
import copy
import inspect
import os
import re

from typing import Union

import discord
from discord.ext import commands

from bot.config import CONFIG

exec_test = re.compile(
    r"(?:^(?:(?:for)|(?:def)|(?:while)|(?:if)))|(?:^([a-z_][A-z0-9_\-\.]*)\s?(?:\+|-|\\|\*)?=)")


class CodeConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str):

        lines = argument.split(';')
        result = []

        for line in lines:
            if exec_test.match(line):
                result.append([line.strip(), exec_test.match(line).group(1)])
            else:
                result.append([line.strip(), None])

        return result


class Admin(commands.Cog):
    """Administrative commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        """You must be the bot owner to use this command."""
        return ctx.bot.is_owner(ctx.author)

    @commands.command(name="eval", hidden=True)
    async def eval(self, ctx: commands.Context, *, code: CodeConverter = []):
        """Evaluates python code.

        `code`: Python code to evaulate, new expressions are seperared with a `;`.
        """
        env = {
            'bot': self.bot,
            'ctx': ctx,
            'CONFIG': CONFIG
        }
        env.update(globals())

        results = []
        max_result_length = (
            2000 - (10 + sum(len(line) + 6 for line, is_exec in code))) // len(code)

        for line, is_exec in code:
            try:
                if is_exec is not None:
                    exec(line, env)
                    result = env.get(is_exec, None)
                    if inspect.isawaitable(result):
                        result = await result
                        env.update({is_exec: result})

                else:
                    result = eval(line, env)
                    if inspect.isawaitable(result):
                        result = await result

            except Exception as e:
                result = f"{type(e).__name__}: {e}"

            results.append([
                line,
                (str(result)[:max_result_length - 3] + "...") if len(str(result)) > max_result_length else str(result)])

        response_string = "```py\n" + \
            "\n".join([f">>> {line}\n{result}" for line, result in results]) + \
            "\n```"

        await ctx.send(response_string)

    @commands.command(name="sudo", hidden=True)
    async def sudo(self, ctx, user: Union[discord.Member, discord.User], *, command: str):
        """Run a command as another user."""
        msg = copy.copy(ctx.message)
        msg.author = user
        msg.content = ctx.prefix + command
        new_ctx = await self.bot.get_context(msg, cls=type(ctx))
        new_ctx.db = ctx.db
        await self.bot.invoke(new_ctx)


def setup(bot: commands.Bot):
    bot.add_cog(Admin(bot))
