import discord
from discord.ext import commands

from bot.config import CONFIG as BOT_CONFIG

COG_CONFIG = BOT_CONFIG.initial_cogs[__name__[:__name__.rindex(".")]]


class Track(discord.PCMVolumeTransformer):
    def __init__(self, source, volume: float = COG_CONFIG.DEFAULT_VOLUME, **kwargs):
        super().__init__(discord.FFmpegPCMAudio(source, **kwargs), volume)

    def playing_embed(self) -> discord.Embed:
        return discord.Embed()

    def request_embed(self, user: discord.User) -> discord.Embed:
        return discord.Embed()


class MP3Track(Track):

    @classmethod
    async def convert(cls, ctx: commands.Converter, argument: str):
        raise commands.BadArgument("")


class YouTubeTrack(Track):

    @classmethod
    async def convert(cls, ctx: commands.Converter, argument: str):
        raise commands.BadArgument("")
