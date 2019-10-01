import asyncio
import datetime
import traceback
from io import BytesIO

from typing import Iterable, Union

import discord
from discord.ext import commands


def format_dt(dt: datetime.datetime):
    """Formats datetime strings.

    Args:
        dt: (datetime.datetime): The datetime object to format.
    """
    return dt.strftime('%F @ %T UTC')


def regional_indicator(c: str) -> str:
    """Returns a regional indicator emoji given a character."""
    return chr(0x1f1e6 - ord('A') + ord(c.upper()))


def keycap_digit(c: Union[int, str]) -> str:
    """Returns a keycap digit emoji given a character."""
    return (str(c).encode("utf-8") + b"\xe2\x83\xa3").decode("utf-8")


async def add_reactions(bot: commands.Bot, message: discord.Message, reactions: Iterable[discord.Emoji]):
    """Adds reactions to a message

    Args:
        message (discord.Message): The message to react to.
        reactions (): A set of reactions to add.
    """
    async def react():
        try:
            for reaction in reactions:
                await message.add_reaction(reaction)
        except Exception as e:
            bot.log.error(f'\t{type(e).__name__}: {e}')
            bot.log.error(traceback.format_exc())

    asyncio.ensure_future(react())


async def fetch_previous_message(message: discord.Message) -> discord.Message:
    """Returns the message before the supplied message in chat.

    Args:
        message (discord.Message): The message afterwards.

    """
    async for _ in message.channel.history(before=message, limit=1):
        return _


async def delete_message(message: discord.Message) -> bool:
    """Attempts to delete the provided message"""
    try:
        await message.delete()
        return True
    except (discord.Forbidden, discord.NotFound):
        return False


async def download_attachment(message: discord.Message, *, index: int = 0) -> BytesIO:
    """Downloads the attachment at the specified index"""
    attachment = BytesIO()
    await message.attachments[index].save(attachment)
    return attachment


async def confirm(ctx: commands.Context, *, emoji='👍'):
    """Confirms a command ran successfully"""
    await ctx.message.add_reaction(emoji)


async def prompt(ctx: commands.Context, message: discord.Message, *, timeout=60, delete_after=True) -> bool:
    """Prompts the user for confirmation.

    Args:
        ctx (commands.Context): The command context to use.
        message (discord.Message): The message to initiate the prompt with.

    Kwargs:
        timeout (float): How long in seconts to wait before timing out.
            Default is 60 seconds.
        delete_after (bool): Determines wether the prompt should be deleted afterwards.
            Defaults to True.

    """
    confirm = False

    def check(payload):
        if payload.message_id == message.id and payload.user_id == ctx.author.id:
            if str(payload.emoji) in ['👍', '👎']:
                return True
        return False

    for emoji in ['👍', '👎']:
        await message.add_reaction(emoji)

    try:
        payload = await ctx.bot.wait_for('raw_reaction_add', check=check, timeout=timeout)
        if str(payload.emoji) == '👍':
            confirm = True

    finally:
        if delete_after:
            await message.delete()

        return confirm
