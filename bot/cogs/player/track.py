import asyncio
import datetime
import functools
import re

from difflib import SequenceMatcher
from pathlib import Path
from io import BytesIO
from typing import Dict, List, Tuple

import youtube_dl

from mutagen.mp3 import MP3

import discord
from discord.ext import commands

from bot.config import CONFIG as BOT_CONFIG

COG_CONFIG = BOT_CONFIG.COGS[__name__[:__name__.rindex('.')]]


def numeric_emoji(n: int) -> str:
    return (str(n).encode("utf-8") + b"\xe2\x83\xa3").decode("utf-8")


async def add_numberic_reactions(message: discord.Message, num_reactions: int):
    for index in range(1, 1+num_reactions):
        await message.add_reaction(numeric_emoji(index))


class Track(discord.PCMVolumeTransformer):
    length = 0
    requester = None
    _embed_colour = discord.Colour.blurple()
    _track_type = 'Track'

    def __init__(self, source, volume: float = COG_CONFIG.DEFAULT_VOLUME, requester: discord.User = None,  **kwargs):
        super().__init__(discord.FFmpegPCMAudio(source, **kwargs), volume)
        self.requester = requester

    @property
    def information(self) -> str:
        """Provides basic information on a track

        An example of this would be the title and atrist.
        """
        return self._track_type

    @property
    def status_information(self) -> str:
        """Provides basic information on a track for use in the discord status section

        An example of this would be the title and atrist.
        """
        return self._track_type

    @property
    def playing_message(self) -> Dict:
        """A discord embed with more detailed information to be displayed when a track is playing."""
        return {
            'embed': discord.Embed(
                colour=self._embed_colour,
                description=self.information
            )
        }

    @property
    def request_message(self) -> Dict:
        """A discord Embed with basic information to be displayed when a track is requested."""
        return {
            'embed': discord.Embed(
                colour=self._embed_colour,
                description=f'Adding {self.information} to the queue...'
            ).set_author(
                name=f'{self._track_type} - Requested by {self.requester}'
            )
        }

    @classmethod
    async def convert(cls, ctx: commands.Converter, argument: str):
        raise NotImplementedError

    @classmethod
    async def get_user_choice(cls, ctx: commands.Context, search_query: str, entries: List[Tuple[str]]) -> int:
        embed = discord.Embed(
            colour=cls._embed_colour,
        ).set_author(
            name=f'{cls._track_type} search results - {search_query} - Requested by {ctx.author}'
        )

        for index, entry in enumerate(entries, 1):
            embed.add_field(
                name=f'{index} - {entry[0]}', value=entry[1], inline=False)

        search_message = (await ctx.send(embed=embed))
        asyncio.ensure_future(add_numberic_reactions(
            search_message, len(entries)))

        def check(reaction: discord.Reaction, user: discord.User):
            return reaction.message.id == search_message.id and user == ctx.author and reaction.emoji in (numeric_emoji(n) for n in range(1, 1+len(entries)))

        try:
            reaction, _ = await ctx.bot.wait_for('reaction_add', check=check, timeout=60)
        except asyncio.TimeoutError:
            raise commands.BadArgument(
                "You did not choose a search result in time.")

        await search_message.delete()
        return int(reaction.emoji[0]) - 1


tracks = {}
for track in Path(COG_CONFIG.DEFAULT_PLAYLIST_DIRECTORY).glob("**/*.mp3"):
    tags = MP3(track)
    tracks[track] = re.sub(r"[^\w\s]", "", tags.get('TIT2')[0] + ' ' +
                           tags.get('TALB')[0]).split(' ')


class MP3Track(Track):
    _embed_colour = discord.Colour.dark_green()
    _track_type = 'MP3 file'

    _title = _artist = _album = _date = 'Unknown'
    _cover = open(COG_CONFIG.DEFAULT_ALBUM_ARTWORK, 'rb')

    def __init__(self, source, volume: float = COG_CONFIG.DEFAULT_VOLUME, requester: discord.User = None,  **kwargs):
        super().__init__(source, volume, requester, **kwargs)

        tags = MP3(source)

        self.length = tags.info.length

        for attribute, tag in (('_title', 'TIT2'), ('_artist', 'TPE1'), ('_album', 'TALB'), ('_date', 'TDRC'), ('_cover', 'APIC:'), ('_cover', 'APIC')):
            data = tags.get(tag)
            if data is not None:
                if attribute != '_cover':
                    self.__setattr__(attribute, data[0])
                else:
                    self.__setattr__(attribute, BytesIO(data.data))

    @property
    def information(self) -> str:
        return f'**{self._title}** by {self._artist}**'

    @property
    def status_information(self) -> str:
        return f"{self._title} from {self._album}"

    @property
    def playing_message(self) -> Dict:
        self._cover.seek(0)
        return {
            'embed': discord.Embed(
                colour=discord.Colour.dark_green(),
                title=self._title,
                description=f'{self._album} - ({self._date})'
            ).set_author(
                name=self._artist
            ).set_thumbnail(
                url='attachment://cover.jpg'
            ),
            'file': discord.File(self._cover, 'cover.jpg')
        }

    @classmethod
    async def convert(cls, ctx: commands.Context, argument: str):

        # Search through all tracks
        scores = {t: 0 for t in tracks}
        for word in re.sub(r"[^\w\s]", "", argument).split():
            for track in tracks:
                for _word in tracks[track]:
                    scores[track] += SequenceMatcher(None, word, _word).ratio()
        for track in tracks:
            scores[track] /= len(tracks[track])
        search_results = sorted(scores, key=scores.get, reverse=True)

        # Raise error or pick search result
        _tracks = [cls(track, requester=ctx.author) for track in search_results[:COG_CONFIG.MAX_SEARCH_RESULTS]]
        result = await cls.get_user_choice(ctx, argument, [(track._title, (track._album)) for track in _tracks])

        return _tracks[result]


class YouTubeTrack(Track):
    _embed_colour = discord.Colour.red()
    _track_type = 'YouTube video'

    video_url_check = re.compile(
        r'(?:youtube(?:-nocookie)?\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})')
    ydl_options = {
        'format': 'bestaudio/best',
    }

    def __init__(self, video_url: str, volume: float = COG_CONFIG.DEFAULT_VOLUME, requester: discord.User = None, **kwargs):

        with youtube_dl.YoutubeDL(self.ydl_options) as ydl:
            info = ydl.extract_info(video_url, download=False)

            if 'entries' in info:
                info = info['entries'][0]

            self.length = info['duration']

            self._title = info['title']
            self._url = info['webpage_url']

            self._uploader = info['uploader']
            self._uploader_url = info['channel_url']

            self._thumbnail = info['thumbnail']

        super().__init__(
            info['url'], volume, requester, before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', options='-bufsize 7680k', **kwargs)

    @property
    def information(self) -> str:
        return f'**[{self._title}]({self._url})** by **[{self._uploader}]({self._uploader_url})**'

    @property
    def status_information(self) -> str:
        return f'{self._title} by {self._uploader}'

    @property
    def playing_message(self) -> Dict:
        return {
            'embed': discord.Embed(
                colour=self._embed_colour,
                description=f'[{self._title}]({self._url})'
            ).set_author(
                name=self._uploader, url=self._uploader_url
            ).set_thumbnail(
                url=self._thumbnail
            )
        }

    @property
    def request_message(self) -> Dict:
        message = super().request_message
        message['embed'].set_thumbnail(
            url=self._thumbnail
        )
        return message

    @classmethod
    async def convert(cls, ctx: commands.Converter, argument: str):
        async with ctx.typing():

            # If user directly requested youtube video
            if cls.video_url_check.search(argument) is not None:
                return cls(argument, requester=ctx.author)

            # Otherwise search for video
            with youtube_dl.YoutubeDL() as ydl:
                search_results = (ydl.extract_info(
                    f'ytsearch{COG_CONFIG.MAX_SEARCH_RESULTS}:{argument}', download=False, ie_key='YoutubeSearch'))['entries']

            # Raise error or pick search result
            if len(search_results) == 0:
                raise commands.BadArgument("No search results were found.")
            elif len(search_results) == 1:
                result = 0
            else:
                result = await cls.get_user_choice(ctx, argument, [(entry['title'], entry['uploader']) for entry in search_results[:COG_CONFIG.MAX_SEARCH_RESULTS]])

            return cls(search_results[result]['webpage_url'], requester=ctx.author)
