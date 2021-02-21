from .player import Player, Request, VoteType
from .utils import YoutubeSearchResultsMenu

from functools import wraps
from typing import Optional

import discord
from discord.ext import commands

import wavelink

from bot import Bot, Context

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
            player: Player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

            if ctx.channel.permissions_for(ctx.author).getattr(permission, False):
                await player.controls[vote_type]()

            await player.vote(vote_type, ctx.author)

        return command

    return wrapper


class MusicPlayer(commands.Cog, wavelink.WavelinkMixin):
    def __init__(self, bot: Bot):
        self.bot = bot

        self.bot.loop.create_task(self.start_wavelink())

    async def start_wavelink(self):
        await self.bot.wait_until_ready()

        await self.bot.wavelink.initiate_node(
            host=COG_CONFIG.LAVALINK.HOSTNAME,
            port=2333,
            rest_uri=f"http://{COG_CONFIG.LAVALINK.HOSTNAME}:2333",
            password=COG_CONFIG.LAVALINK.PASSWORD,
            identifier='meloetta',
            region='us_east'
        )

    # region: event listeners

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        player: Player = self.bot.wavelink.get_player(member.guild.id, cls=Player)
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
        await payload.player.foo  # TODO: What?

    # endregion

    # region: commands

    @commands.command(name='join', aliases=['start', 'connect'])
    @commands.check(is_not_connected)
    async def join(self, ctx: Context, *, channel: discord.VoiceChannel = None):
        """TODO: """
        channel = channel or getattr(ctx.author.voice, 'channel', None)
        if channel is None:
            raise commands.BadArgument('No channel to join.')

        player: Player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        await player.connect(channel.id)
        await player.set_volume(COG_CONFIG.DEFAULT_VOLUME)
        await player.next()

    @commands.command(name='pause')
    @vote(VoteType.PAUSE, 'mute_members')
    async def pause(self, ctx: Context):
        """TODO: """

    @commands.command(name='resume')
    @vote(VoteType.RESUME, 'mute_members')
    async def resume(self, ctx: Context):
        """TODO: """

    @commands.command(name='skip')
    @vote(VoteType.SKIP, 'manage_messages')
    async def resume(self, ctx: Context):
        """TODO: """

    @commands.command(name='repeat')
    @vote(VoteType.REPEAT)
    async def repeat(self, ctx: Context):
        """TODO: """

    @commands.command(name='shuffle')
    @vote(VoteType.SHUFFLE)
    async def shuffle(self, ctx: Context):
        """TODO: """

    @commands.command(name='leave', aliases=['stop', 'disconnect'])
    @vote(VoteType.STOP, 'move_members')
    async def leave(self, ctx: Context):
        """TODO: """

    @commands.command(name='play')
    async def play(self, ctx: Context, *, query: str):
        tracks = await self.bot.wavelink.get_tracks(f'ytsearch:{query}')

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

        player: Player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        
        if player.is_connected:
            is_listening(ctx)

        await player.request(track, ctx.author)

        if not player.is_connected:
            await self.join(ctx)

    @commands.command(name='now_playing', aliases=['playing', 'np'])
    @commands.check(is_connected)
    async def now_playing(self, ctx: Context):
        player: Player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        track: Request = player.current

        embed = discord.Embed(
            title='Now Playing',
            description=f'{track.title} - Requested by: {track.requester}'
        )

        await ctx.send(embed=embed)

    @commands.command(name='volume')
    @commands.check(is_connected)
    async def volume(self, ctx: Context, volume: int):
        if not 0 <= volume <= 100:
            raise commands.BadArgument('Volume must be between 0 and 100.')

        player: Player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        await player.set_volume(volume)

    # endregion


def setup(bot: Bot):

    # Check for player botvars
    if not hasattr(bot, 'wavelink'):
        bot.wavelink = wavelink.Client(bot=bot)

    bot.add_cog(MusicPlayer(bot))
