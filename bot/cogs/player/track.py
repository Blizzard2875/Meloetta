import asyncio
import re

from fuzzywuzzy import fuzz
from pathlib import Path
from io import BytesIO
from typing import Dict, List, Tuple

import aiohttp
import youtube_dl

import discord
from discord.ext import commands

from mutagen.mp3 import MP3

from bot.utils import tools

from bot.config import config as BOT_CONFIG
COG_CONFIG = BOT_CONFIG.EXTENSIONS[__name__[:__name__.rindex('.')]]


class Track(discord.PCMVolumeTransformer):
    length = 0
    requester = None
    _embed_colour = discord.Colour.blurple()
    _track_type = 'Track'

    def __init__(self, source, volume: float = COG_CONFIG.DEFAULT_VOLUME, requester: discord.User = None, **kwargs):
        super().__init__(discord.FFmpegPCMAudio(source, **kwargs), volume)
        self.requester = requester
        self._frames = 0

    def read(self):
        self._frames += 1
        return super().read()

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

        if reaction.emoji == tools.regional_indicator('x'):
            raise commands.BadArgument('Selection cancelled.')

        await search_message.delete()
        return int(reaction.emoji[0]) - 1


tracks = {}
for track in Path(COG_CONFIG.DEFAULT_PLAYLIST_DIRECTORY).glob("**/*.mp3"):
    tags = MP3(track)
    tracks[track] = re.sub(r"[^\w\s]", "", tags.get('TIT2')[0] + ' ' + tags.get('TALB')[0]).split(' ')


class MP3Track(Track):
    _embed_colour = discord.Colour.dark_green()
    _track_type = 'MP3 file'

    _title = _artist = _album = _date = 'Unknown'
    _cover = open(COG_CONFIG.DEFAULT_ALBUM_ARTWORK, 'rb')

    def __init__(self, source, volume: float = COG_CONFIG.DEFAULT_VOLUME, requester: discord.User = None, **kwargs):
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
        return f'**{self._title}** by **{self._artist}**'

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
                    scores[track] += fuzz.ratio(word.lower(), _word.lower())
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

    youtube_api_url = f'https://www.googleapis.com/{COG_CONFIG.YOUTUBE_API.SERVICE_NAME}/{COG_CONFIG.YOUTUBE_API.VERSION}'

    video_url_check = re.compile(
        r'(?:youtube(?:-nocookie)?\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})')
    ydl_options = {
        'format': 'bestaudio/best',
        'geo_bypass': True,
        'geo_bypass_country': 'US'
    }

    def __init__(self, video_id: str, volume: float = COG_CONFIG.DEFAULT_VOLUME, requester: discord.User = None, **kwargs):

        with youtube_dl.YoutubeDL(self.ydl_options) as ydl:
            info = ydl.extract_info(
                'https://youtube.com/watch?v=' + video_id, download=False)

            if 'entries' in info:
                info = info['entries'][0]

            self.length = round(info['duration'])

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
            is_video = cls.video_url_check.search(argument)
            if is_video is not None:
                return cls(is_video.groups()[0], requester=ctx.author)

            # Otherwise search for video
            async with aiohttp.ClientSession() as session:
                search_url = f'{cls.youtube_api_url}/search?q={argument}\
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

            return cls(search_results[result]['id']['videoId'], requester=ctx.author)


class AttachmentTrack(Track):
    _embed_colour = discord.Colour.blue()
    _track_type = 'Local file'

    def __init__(self, attachment: discord.File, volume: float = COG_CONFIG.DEFAULT_VOLUME, requester: discord.User = None, **kwargs):

        super().__init__(attachment.proxy_url, volume, requester,
                         before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', options='-bufsize 7680k', **kwargs)
