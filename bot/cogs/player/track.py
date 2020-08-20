import asyncio
import re

# from functools import partial
from difflib import SequenceMatcher
from pathlib import Path
from io import BytesIO
from typing import Dict, List, Tuple

# import aiohttp
import wavelink

import discord
from discord.ext import commands

from mutagen.mp3 import MP3

from bot.utils import tools

from bot.config import config as BOT_CONFIG
COG_CONFIG = BOT_CONFIG.EXTENSIONS[__name__[:__name__.rindex('.')]]


class Track:
    requester = None
    _embed_colour = discord.Colour.blurple()
    _track_type = 'Track'
    _track_class = wavelink.Track

    def __init__(self, url: str, requester: discord.User = None, track: wavelink.abc.Playable = None):
        self.url = url
        self.requester = requester
        self.track = track

    async def setup(self, bot) -> wavelink.Track:
        """Prepares a wavelink track object for playing."""
        if self.track is None:
            self.track = await wavelink.Node.get_best_node(bot).get_track(self._track_class, self.url)

            if self.track is None:
                raise commands.BadArgument('Error loading track.')

        return self.track

    @property
    def length(self) -> int:
        if self.track is not None:
            return self.track.length // 1000
        return 0

    @property
    def _title(self):
        return self.track.title

    @property
    def _author(self):
        return self.track.author

    @property
    def information(self) -> str:
        """Provides basic information on a track

        An example of this would be the title and artist.
        """
        return f"**{self._title}** by **{self._author}**"

    @property
    def status_information(self) -> str:
        """Provides basic information on a track for use in the discord status section

        An example of this would be the title and artist.
        """
        return f"{self._title} by {self._author}"

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
    async def get_user_choice(cls, ctx: commands.Context, search_query: str, entries: List[Tuple[str, str]]) -> int:
        embed = discord.Embed(
            colour=cls._embed_colour,
        ).set_author(
            name=f'{cls._track_type} search results - {search_query} - Requested by {ctx.author}'
        ).set_footer(text=f'Select a search result or {tools.regional_indicator("x")} to cancel.')

        for index, entry in enumerate(entries, 1):
            embed.add_field(
                name=f'{index} - {entry[0]}', value=entry[1], inline=False)

        search_message = (await ctx.send(embed=embed))
        reactions = [tools.keycap_digit(n) for n in range(1, 1 + len(entries))]
        reactions.append(tools.regional_indicator('x'))
        await tools.add_reactions(search_message, reactions)

        def check(reaction: discord.Reaction, user: discord.User):
            return reaction.message.id == search_message.id and user == ctx.author \
                and reaction.emoji in reactions

        try:
            reaction, _ = await ctx.bot.wait_for('reaction_add', check=check, timeout=60)
        except asyncio.TimeoutError:
            raise commands.BadArgument(
                'You did not choose a search result in time.')
        finally:
            await search_message.delete()

        if reaction.emoji == tools.regional_indicator('x'):
            raise commands.BadArgument('Selection cancelled.')

        return int(reaction.emoji[0]) - 1


class MP3Track(Track):
    _embed_colour = discord.Colour.dark_green()
    _track_type = 'MP3 file'
    _search_ready = asyncio.Event()
    _tracks: Dict[Path, str] = dict()

    def __init__(self, filename: str, requester: discord.User = None, track: wavelink.Track = None, **kwargs):
        super().__init__(COG_CONFIG.MP3_BASE_URL + filename, requester, track)
        self.metadata = dict()

        # Populate metadata
        tags = MP3(filename)

        for attribute, tag in (('title', 'TIT2'), ('artist', 'TPE1'), ('album', 'TALB'), ('date', 'TDRC')):
            data = tags.get(tag)
            if data is not None:
                self.metadata[attribute] = data[0]

        for attribute, tag in (('cover', 'APIC:'), ('cover', 'APIC')):
            data = tags.get(tag)
            if data is not None:
                self.metadata[attribute] = BytesIO(data.data)

    @property
    def _title(self):
        return self.metadata.get('title', 'Unknown')

    @property
    def _album(self):
        return self.metadata.get('album', 'Unknown')

    @property
    def _author(self):
        return self.metadata.get('artist', 'Unknown')

    @property
    def _date(self):
        return self.metadata.get('date', 'Unknown')

    @property
    def _cover(self):
        return self.metadata.get('cover', open(COG_CONFIG.DEFAULT_ALBUM_ARTWORK, 'rb'))

    # endregion

    @property
    def information(self) -> str:
        return f'{self._title} from {self._album}'

    @property
    def playing_message(self) -> Dict:
        self._cover.seek(0)
        return {
            'embed': discord.Embed(
                colour=discord.Colour.dark_green(),
                title=self._title,
                description=f'{self._album} - ({self._date})'
            ).set_author(
                name=self._author
            ).set_thumbnail(
                url='attachment://cover.jpg'
            ),
            'file': discord.File(self._cover, 'cover.jpg')
        }

    @classmethod
    async def convert(cls, ctx: commands.Context, argument: str):

        await cls._search_ready.wait()

        # Search through all tracks
        scores = {t: 0.0 for t in cls._tracks}
        for word in re.sub(r'[^\w\s]', '', argument).split():
            for track in cls._tracks:
                for _word in cls._tracks[track]:
                    scores[track] += SequenceMatcher(None, word.lower(), _word.lower()).ratio()

        for track in cls._tracks:
            scores[track] /= len(cls._tracks[track])
        search_results = sorted(scores, key=scores.get, reverse=True)

        # Raise error or pick search result
        tracks = [cls(str(track), requester=ctx.author) for track in search_results[:COG_CONFIG.MAX_SEARCH_RESULTS]]
        result = await cls.get_user_choice(ctx, argument, [(track._title, track._album) for track in tracks])

        return tracks[result]

    @classmethod
    def setup_search(cls):
        for track in Path(COG_CONFIG.DEFAULT_PLAYLIST_DIRECTORY).absolute().glob('**/*.mp3'):
            tags = MP3(str(track))
            cls._tracks[track] = re.sub(r'[^\w\s]', '', tags.get('TIT2')[0] + ' ' + tags.get('TALB')[0]).split(' ')

        cls._search_ready.set()


class StreamableTrack(Track):
    _track_type = 'Unknown Stream'

    @property
    def _url(self):
        return '#'

    @property
    def _thumbnail(self):
        return self.track.thumb

    @property
    def information(self) -> str:
        return f'**[{self._title}]({self._url})** by **{self._author}**'

    @property
    def playing_message(self) -> Dict:
        embed = discord.Embed(
            colour=self._embed_colour,
            description=f'[{self._title}]({self._url})'
        ).set_author(name=f'{self._author} - Requested By: {self.requester}')

        embed.set_thumbnail(url=self._thumbnail)

        return {
            'embed': embed
        }

    @classmethod
    async def convert(cls, ctx: commands.Converter, argument: str):
        async with ctx.typing():

            node = wavelink.Node.get_best_node(ctx.bot)
            tracks = await cls._track_class.search(node, argument)
            if not tracks:
                raise commands.BadArgument('No search results were found.')

            tracks = [cls(argument, ctx.author, track) for track in tracks[:COG_CONFIG.MAX_SEARCH_RESULTS]]
            if len(tracks) == 1:
                return tracks[0]

            choice = await cls.get_user_choice(ctx, argument, [(track._title, track._author) for track in tracks])
            return tracks[choice]


class YouTubeTrack(StreamableTrack):
    _embed_colour = discord.Colour.red()
    _track_type = 'YouTube video'
    _track_class = wavelink.YouTubeVideo

    video_url_check = re.compile(
        r'(?:youtube(?:-nocookie)?\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})')

    # region metadata

    @property
    def _url(self):
        return f'https://youtu.be/{self.track.identifier}'

    # endregion

    @classmethod
    async def convert(cls, ctx: commands.Converter, argument: str):
        # If user directly requested youtube video
        is_video = cls.video_url_check.search(argument)
        if is_video is not None:
            track = cls(argument, ctx.author)
            await track.setup(ctx.bot)
            return track

        return await super().convert(ctx, argument)


class SoundCloudTrack(StreamableTrack):
    _embed_colour = discord.Colour.orange()
    _track_type = 'SoundCloud track'
    _track_class = wavelink.SoundCloudTrack

    @property
    def _url(self):
        return self.track.uri


class AttachmentTrack(StreamableTrack):
    _embed_colour = discord.Colour.blue()
    _track_type = 'Local file'

    @property
    def _title(self):
        if self.track is not None:
            if not self.track.title.isdigit():
                return self.track.title
        return 'File'

    @property
    def _author(self):
        if self.track is not None:
            if self.track.author != 'Unknown artist':
                return self.track.author
        return self.requester.name

    @classmethod
    async def convert(cls, ctx: commands.Context, argument: str):
        raise NotImplementedError
