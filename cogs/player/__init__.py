from .player import Player, VoteType
from .utils import YoutubeSearchResultsMenu

from contextlib import suppress
from functools import wraps
from typing import Optional, Union

import discord
from discord.ext import commands, menus

import wavelink

from bot import Bot, Context
from utils.paginator import EmbedPaginator

from bot.config import CONFIG
COG_CONFIG = CONFIG.EXTENSIONS[__name__]


def is_not_connected(ctx: Context):
    guild_id = getattr(ctx.guild, 'id', -1)
    if ctx.guild.voice_client is not None or ctx.bot.wavelink.get_player(guild_id).is_connected:
        raise commands.CheckFailure(
            'A player is already connected in this guild.')
    return True


def is_connected(ctx: Context):
    guild_id = getattr(ctx.guild, 'id', -1)
    if not ctx.bot.wavelink.get_player(guild_id, cls=Player).is_connected:
        raise commands.CheckFailure('A player is not connected in this guild.')
    return True


def is_listening(ctx: Context):
    guild_id = getattr(ctx.guild, 'id', -1)
    if ctx.author not in ctx.bot.wavelink.get_player(guild_id, cls=Player).listeners:
        raise commands.CheckFailure(
            'You are currently not listening to the bot.')
    return True


def vote(vote_type: VoteType, permission: Optional[str] = None):

    def wrapper(func):

        @commands.check(is_connected)
        @commands.check(is_listening)
        @wraps(func)
        async def command(self, ctx: Context):
            player: Player = self.client.get_player(ctx.guild.id, cls=Player)

            if getattr(ctx.channel.permissions_for(ctx.author), permission, False):
                await player.controls[vote_type]()

            elif not await player.vote(vote_type, ctx.author):
                return await ctx.send(embed=discord.Embed(
                    description='Vote recorded...'
                ))

            await ctx.check()

        return command

    return wrapper


class MusicPlayer(commands.Cog, wavelink.WavelinkMixin):
    client: wavelink.Client

    def __init__(self, bot: Bot):
        self.bot = bot
        self.client = bot.wavelink

        self.bot.loop.create_task(self.start_wavelink())

    async def start_wavelink(self):
        await self.bot.wait_until_ready()

        with suppress(wavelink.NodeOccupied):
            await self.client.initiate_node(
                host=COG_CONFIG.LAVALINK.HOSTNAME,
                port=2333,
                rest_uri=f'http://{COG_CONFIG.LAVALINK.HOSTNAME}:2333',
                password=COG_CONFIG.LAVALINK.PASSWORD,
                identifier='meloetta',
                region='us_east'
            )

    # region: event listeners

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        player = self.client.get_player(member.guild.id, cls=Player)
        if not player.is_connected:
            return
        if before.channel == after.channel:
            return
        if player.channel not in (before.channel, after.channel):
            return

        await player.update_listeners()

    @wavelink.WavelinkMixin.listener('on_track_stuck')
    @wavelink.WavelinkMixin.listener('on_track_exception')
    @wavelink.WavelinkMixin.listener('on_track_end')
    async def on_player_stop(self, node: wavelink.Node, payload):
        await payload.player.next()

    # endregion

    # region: commands

    @commands.command(name='join', aliases=['start', 'connect'])
    @commands.check(is_not_connected)
    async def join(self, ctx: Context, *, channel: discord.VoiceChannel = None):
        """Start the player in a channel."""
        channel = channel or getattr(ctx.author.voice, 'channel', None)
        if channel is None:
            raise commands.BadArgument('No channel to join.')

        player = self.client.get_player(ctx.guild.id, cls=Player)
        await player.connect(channel.id)
        await player.set_volume(COG_CONFIG.DEFAULT_VOLUME)
        await player.next()

    @commands.command(name='pause')
    @vote(VoteType.PAUSE, 'mute_members')
    async def pause(self, ctx: Context):
        """Pause the player."""

    @commands.command(name='resume')
    @vote(VoteType.RESUME, 'mute_members')
    async def resume(self, ctx: Context):
        """Resume the player."""

    @commands.command(name='skip')
    @vote(VoteType.SKIP, 'manage_messages')
    async def skip(self, ctx: Context):
        """Skip the currently playing track."""

    @commands.command(name='repeat')
    @vote(VoteType.REPEAT)
    async def repeat(self, ctx: Context):
        """Repeat the currently playing track."""

    @commands.command(name='shuffle')
    @vote(VoteType.SHUFFLE)
    async def shuffle(self, ctx: Context):
        """Shuffle the request queue."""

    @commands.command(name='leave', aliases=['stop', 'disconnect'])
    @vote(VoteType.STOP, 'move_members')
    async def leave(self, ctx: Context):
        """Stop the player and leave the voice channel."""

    @commands.group(name='play', aliases=['request'], invoke_without_command=True)
    async def play(self, ctx: Context, *, query: str):
        """Play a requested track from YouTube."""
        tracks = await self.client.get_tracks(f'ytsearch:{query}')

        if not tracks:
            raise commands.BadArgument('Could not find any search results.')

        if len(tracks) == 1:
            track = tracks[0]
        else:
            menu = YoutubeSearchResultsMenu(
                query, tracks[:COG_CONFIG.MAX_SEARCH_RESULTS])
            track = await menu.start(ctx)
            if track is None:
                # TODO: Not this error type
                raise commands.BadArgument('Selection cancelled.')

        player = self.client.get_player(ctx.guild.id, cls=Player)

        if player.is_connected:
            is_listening(ctx)

        await player.request(track, ctx.author)

        if not player.is_connected:
            await self.join(ctx)

    @play.command(name='url', aliases=['file'])
    @commands.has_guild_permissions(manage_server=True)
    async def play_url(self, ctx: Context, *, url: Union[discord.Attachment, str]):
        """Play a requested track from a URL."""
        if isinstance(url, discord.Attachment):
            url = url.proxy_url

        tracks = await self.client.get_tracks(url)
        if tracks is None:
            raise commands.BadArgument('Invalid URL has been passed.')

        player = self.client.get_player(ctx.guild.id, cls=Player)

        if player.is_connected:
            is_listening(ctx)

        await player.request(tracks[0], ctx.author)

        if not player.is_connected:
            await self.join(ctx)

    @commands.command(name='now_playing', aliases=['playing', 'np'])
    @commands.check(is_connected)
    async def now_playing(self, ctx: Context):
        """Displays the currently playing track."""
        player = self.client.get_player(ctx.guild.id, cls=Player)
        request = player.current

        embed = discord.Embed(
            title='Now Playing',
        )

        if request is not None:
            embed.add_field(
                name=f'{request.title} - Requested by: {request.requester}',
                value=f'[link]({request.uri}) - {request.author}',
                inline=False
            )
        else:
            embed.description = f'There is currently no track playing, use `{ctx.prefix}play` to request tracks.'

        await ctx.send(embed=embed)

    @commands.command(name='queue')
    @commands.check(is_connected)
    async def queue(self, ctx: Context):
        """Displays the current queue."""
        player = self.client.get_player(ctx.guild.id, cls=Player)

        embed = EmbedPaginator(
            colour=discord.Colour.blue(),
            title='Current request queue:',
            max_fields=10
        )

        for i, request in enumerate(player._queue._queue, 1):
            embed.add_field(
                name=f'{i}: {request.title} - Requested by: {request.requester}',
                value=f'[link]({request.uri}) - {request.author}',
                inline=False
            )

        if not embed.fields:
            embed.description = f'There are currently no requests in the queue, use `{ctx.prefix}play` to request tracks.'

        menu = menus.MenuPages(embed)
        await menu.start(ctx)

    @commands.command(name='volume')
    @commands.check(is_connected)
    async def volume(self, ctx: Context, volume: int):
        """Sets the player volume."""
        if not 0 <= volume <= 100:
            raise commands.BadArgument('Volume must be between 0 and 100.')

        player = self.client.get_player(ctx.guild.id, cls=Player)
        await player.set_volume(volume)
        await ctx.check()

    # endregion


def setup(bot: Bot):

    # Check for player botvars
    if not hasattr(bot, 'wavelink'):
        bot.wavelink = wavelink.Client(bot=bot)

    bot.add_cog(MusicPlayer(bot))
