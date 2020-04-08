from typing import Union

import discord
from discord.ext import commands


def is_administrator(ctx: Union[discord.Message, commands.Context]) -> bool:
    return commands.has_guild_permissions(administrator=True)(ctx)


async def is_owner(ctx: Union[discord.Message, commands.Context]) -> bool:
    is_owner = await ctx.bot.is_owner(ctx.author)
    if not is_owner:
        raise commands.NotOwner(
            'You must be the bot owner to use this command.')
    return True


def is_guild(ctx: Union[discord.Message, commands.Context]) -> bool:
    if ctx.guild is None:
        raise commands.NoPrivateMessage(
            'You must use this command in a server.')
    return True


def is_direct_message(ctx: commands.Context) -> bool:
    if not isinstance(ctx.channel, discord.DMChannel):
        raise commands.PrivateMessageOnly(
            'You must use this command in a direct message.')
    return True


def has_administrator_permission(ctx: commands.Context) -> bool:
    is_guild(ctx)
    commands.has_guild_permissions(administrator=True)(ctx)
    commands.bot_has_permissions(administrator=True)(ctx)
    return True
