import datetime
import functools
import re

from io import BytesIO

import youtube_dl

from mutagen.mp3 import MP3

import discord
from discord.ext import commands

from bot.config import CONFIG as BOT_CONFIG

COG_CONFIG = BOT_CONFIG.COGS[__name__[:__name__.rindex(".")]]


class Track(discord.PCMVolumeTransformer):
    _length = 0

    def __init__(self, source, volume: float = COG_CONFIG.DEFAULT_VOLUME, **kwargs):
        super().__init__(discord.FFmpegPCMAudio(source, **kwargs), volume)

    async def send_playing_embed(self, channel: discord.TextChannel, progress=False):
        raise NotImplementedError

    async def send_request_embed(self, channel: discord.TextChannel, requester: discord.User):
        raise NotImplementedError

    @classmethod
    async def convert(cls, ctx: commands.Converter, argument: str):
        raise NotImplementedError


class MP3Track(Track):
    _title = _artist = _album = _date = "Unknown"
    _cover = open(COG_CONFIG.DEFAULT_ALBUM_ARTWORK, 'rb')

    def __init__(self, source, volume: float = COG_CONFIG.DEFAULT_VOLUME, **kwargs):
        super().__init__(source, volume, **kwargs)

        tags = MP3(source)

        self._length = tags.info.length

        for attribute, tag in (('_title', 'TIT2'), ('_artist', 'TPE1'), ('_album', 'TALB'), ('_date', 'TDRC'), ('_cover', 'APIC:'), ('_cover', 'APIC')):
            data = tags.get(tag)
            if data is not None:
                if attribute != "_cover":
                    self.__setattr__(attribute, data[0])
                else:
                    self.__setattr__(attribute, BytesIO(data.data))

    async def send_playing_embed(self, channel: discord.TextChannel):
        await channel.send(
            embed=discord.Embed(
                colour=discord.Colour.dark_green(),
                title=self._title,
                description=f"{self._album} - ({self._date})"
            ).set_author(
                name=self._artist
            ).set_thumbnail(
                url="attachment://cover.jpg"
            ),
            file=discord.File(self._cover, 'cover.jpg')
        )


class YouTubeTrack(Track):
    video_url_check = re.compile(
        r"(?:youtube(?:-nocookie)?\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})")
    ydl_options = {
        "format": "bestaudio/best",
    }

    def __init__(self, video_url, volume: float = COG_CONFIG.DEFAULT_VOLUME, **kwargs):

        with youtube_dl.YoutubeDL(self.ydl_options) as ydl:
            info = ydl.extract_info(video_url, download=False)

            if "entries" in info:
                info = info["entries"][0]

            self._length = info["duration"]

            self._title = info["title"]
            self._url = info["webpage_url"]

            self._uploader = info["uploader"]
            self._uploader_url = info["channel_url"]

            self._thumbnail = info["thumbnail"]

        super().__init__(
            info["url"], volume, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options="-bufsize 7680k", **kwargs)

    async def send_playing_embed(self, channel: discord.TextChannel, *, progress=False):
        await channel.send(
            embed=discord.Embed(
                colour=discord.Colour.red(),
                description=f"[{self._title}]({self._url})"
            ).set_author(
                name=self._uploader, url=self._uploader_url
            ).set_thumbnail(
                url=self._thumbnail
            )
        )

    async def send_request_embed(self, channel: discord.TextChannel, requester: discord.User):
        await channel.send(
            embed=discord.Embed(
                colour=discord.Colour.red(),
                description=f"Adding **[{self._title}]({self._url})** by **[]()** to the queue..."
            ).set_author(
                name=f"YouTube video - Requested by {requester}"
            ).set_thumbnail(
                url=self._thumbnail
            )
        )

    @classmethod
    async def convert(cls, ctx: commands.Converter, argument: str):
        async with ctx.typing():

             # If user directly requested youtube video
            if cls.video_url_check.search(argument) is not None:
                return YouTubeTrack(argument)

            raise commands.BadArgument("Searching is currently not supported.")
