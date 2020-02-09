import asyncio
import re

from functools import partial
from pathlib import Path
from io import BytesIO
from typing import Dict, List, Tuple

import aiohttp
import youtube_dl

import discord
from discord.ext import commands

from fuzzywuzzy import fuzz
from mutagen.mp3 import MP3

from bot.utils import tools

from bot.config import config as BOT_CONFIG
COG_CONFIG = BOT_CONFIG.EXTENSIONS[__name__[:__name__.rindex('.')]]


class Track(discord.PCMVolumeTransformer):
    length = 0
    requester = None
    _embed_colour = discord.Colour.blurple()
    _track_type = 'Track'

    def __init__(self, source, length: float, metadata: Dict, volume: float = COG_CONFIG.DEFAULT_VOLUME, requester: discord.User = None, **kwargs):
        self.source = source
        self.length = length
        self.metadata = metadata

        self.requester = requester
        self._frames = 0
        self.kwargs = kwargs
        super().__init__(discord.FFmpegPCMAudio(self.source, **self.kwargs), volume)

    @classmethod
    def get_source(cls) -> Tuple[str, float, dict]:
        raise NotImplementedError

    def read(self):
        self._frames += 1
        return super().read()

    def copy(self, requester, volume):
        return self.__class__(self.source, self.length, self.metadata, volume, requester, **self.kwargs)

    @property
    def play_time(self) -> int:
        """Returns the current track play time in seconds."""
        return round(self._frames / 50)

    @property
    def information(self) -> str:
        """Provides basic information on a track

        An example of this would be the title and artist.
        """
        return self._track_type

    @property
    def status_information(self) -> str:
        """Provides basic information on a track for use in the discord status section

        An example of this would be the title and artist.
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

        await search_message.delete()
        if reaction.emoji == tools.regional_indicator('x'):
            raise commands.BadArgument('Selection cancelled.')

        return int(reaction.emoji[0]) - 1


class MP3Track(Track):
    _embed_colour = discord.Colour.dark_green()
    _track_type = 'MP3 file'
    _search_ready = asyncio.Event()
    _tracks = dict()

    @classmethod
    def get_source(cls, filename: str) -> Tuple[str, float, dict]:
        tags = MP3(filename)
        meta = dict()

        for attribute, tag in (('title', 'TIT2'), ('artist', 'TPE1'), ('album', 'TALB'), ('date', 'TDRC')):
            data = tags.get(tag)
            if data is not None:
                meta[attribute] = data[0]

        for attribute, tag in (('cover', 'APIC:'), ('cover', 'APIC')):
            data = tags.get(tag)
            if data is not None:
                meta[attribute] = BytesIO(data.data)

        return (filename, tags.info.length, meta)

    # region metadata

    @property
    def _title(self):
        return self.metadata.get('title', 'Unknown')

    @property
    def _album(self):
        return self.metadata.get('album', 'Unknown')

    @property
    def _artist(self):
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
        return f'**{self._title}** by **{self._artist}**'

    @property
    def status_information(self) -> str:
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
                name=self._artist
            ).set_thumbnail(
                url='attachment://cover.jpg'
            ),
            'file': discord.File(self._cover, 'cover.jpg')
        }

    @classmethod
    async def convert(cls, ctx: commands.Context, argument: str):

        await cls._search_ready.wait()

        # Search through all tracks
        scores = {t: 0 for t in cls._tracks}
        for word in re.sub(r'[^\w\s]', '', argument).split():
            for track in cls._tracks:
                for _word in cls._tracks[track]:
                    scores[track] += fuzz.ratio(word.lower(), _word.lower())

        for track in cls._tracks:
            scores[track] /= len(cls._tracks[track])
        search_results = sorted(scores, key=scores.get, reverse=True)

        # Raise error or pick search result
        _tracks = [cls(*cls.get_source(track), requester=ctx.author) for track in search_results[:COG_CONFIG.MAX_SEARCH_RESULTS]]
        result = await cls.get_user_choice(ctx, argument, [(track._title, (track._album)) for track in _tracks])

        return _tracks[result]

    @classmethod
    def setup_search(cls):
        for track in Path(COG_CONFIG.DEFAULT_PLAYLIST_DIRECTORY).glob('**/*.mp3'):
            tags = MP3(track)
            cls._tracks[track] = re.sub(r'[^\w\s]', '', tags.get('TIT2')[0] + ' ' + tags.get('TALB')[0]).split(' ')

        cls._search_ready.set()


class YouTubeTrack(Track):
    _embed_colour = discord.Colour.red()
    _track_type = 'YouTube video'

    youtube_api_url = f'https://www.googleapis.com/{COG_CONFIG.YOUTUBE_API.SERVICE_NAME}/{COG_CONFIG.YOUTUBE_API.VERSION}'

    video_url_check = re.compile(
        r'(?:youtube(?:-nocookie)?\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})')
    ytdl_options = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',  # ipv6 addresses cause issues sometimes
        'geo_bypass': True,
        'geo_bypass_country': 'US'
    }

    def __init__(self, source, length: float, metadata: Dict, volume: float = COG_CONFIG.DEFAULT_VOLUME, requester: discord.User = None, **kwargs):
        options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-bufsize 7680k'
        }
        options.update(**kwargs)

        super().__init__(source, length, metadata, volume, requester, **options)

    @classmethod
    def get_source(cls, video_id: str) -> Tuple[str, float, dict]:

        with youtube_dl.YoutubeDL(cls.ytdl_options) as ytdl:
            info = ytdl.extract_info('https://youtube.com/watch?v=' + video_id, download=False)

        return (info['url'], round(info['duration']), info)

    # region metadata

    @property
    def _title(self):
        return self.metadata.get('title', 'Unknown')

    @property
    def _url(self):
        return self.metadata.get('webpage_url', '#')

    @property
    def _uploader(self):
        return self.metadata.get('uploader', 'Unknown')

    @property
    def _uploader_url(self):
        return self.metadata.get('channel_url', '#')

    @property
    def _thumbnail(self):
        return self.metadata.get('thumbnail', '#')

    # endregion

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
                name=f'{self._uploader} - Requested By: {self.requester}', url=self._uploader_url
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
    async def _convert(cls, ctx, video_id):
        try:
            to_run = partial(cls.get_source, video_id)
            source = await ctx.bot.loop.run_in_executor(None, to_run)
            return cls(*source, requester=ctx.author)

        except youtube_dl.DownloadError as e:
            if '429' in str(e):
                raise commands.BadArgument('Error downloading Youtube video: Too many requests.')
            elif str(e) == 'ERROR: This video is not available.\nSorry about that.':
                raise commands.BadArgument('Error downloading YouTube video: Cannot download video.')
            else:
                raise e

    @classmethod
    async def convert(cls, ctx: commands.Converter, argument: str):
        async with ctx.typing():

            # If user directly requested youtube video
            is_video = cls.video_url_check.search(argument)
            if is_video is not None:
                return await cls._convert(ctx, is_video.groups()[0])

            # Otherwise search for video
            async with aiohttp.ClientSession() as session:
                search_url = f'{cls.youtube_api_url}/search?type=video&videoSyndicated=true&q={argument}\
&part=snippet&maxResults={COG_CONFIG.MAX_SEARCH_RESULTS}&key={COG_CONFIG.YOUTUBE_API.KEY}&alt=json'

                async with session.get(search_url) as response:
                    search_results = (await response.json())['items']

            # Raise error or pick search result
            if len(search_results) == 0:
                raise commands.BadArgument('No search results were found.')
            elif len(search_results) == 1:
                result = 0
            else:
                result = await cls.get_user_choice(ctx, argument, [(entry['snippet']['title'], entry['snippet']['channelTitle']) for entry in search_results])

            return await cls._convert(ctx, search_results[result]['id']['videoId'])


class AttachmentTrack(Track):
    _embed_colour = discord.Colour.blue()
    _track_type = 'Local file'

    def __init__(self, source, length: float, metadata: Dict, volume: float = COG_CONFIG.DEFAULT_VOLUME, requester: discord.User = None, **kwargs):
        options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-bufsize 7680k'
        }
        options.update(**kwargs)

        super().__init__(source, length, metadata, volume, requester, **options)

    @classmethod
    def get_source(self, attachment: discord.File) -> Tuple[str, float, dict]:
        return (attachment.proxy_url, 1, None)
