import asyncio
import datetime
import random

import discord
from discord.ext import commands, tasks

from bot.config import config as BOT_CONFIG

from bot.utils import checks, tools

from .session import Session
from .track import MP3Track, SoundCloudTrack, YouTubeTrack, AttachmentTrack

COG_CONFIG = BOT_CONFIG.EXTENSIONS[__name__]


async def session_is_not_running(ctx: commands.Context) -> bool:
    if ctx.cog._get_session(ctx.guild) is not None:
        raise commands.CheckFailure('A player is already running on this server.')
    return True


async def session_is_running(ctx: commands.Context) -> bool:
    if ctx.cog._get_session(ctx.guild) is None:
        raise commands.CheckFailure('A player is not running on this server.')
    return True


async def session_is_stoppable(ctx: commands.Context) -> bool:
    session = ctx.cog._get_session(ctx.guild)
    if session is None or not session.stoppable:
        raise commands.CheckFailure('This player session cannot be stopped.')
    return True

async def is_whitelisted_guild(ctx: commands.Context) -> bool:
    if ctx.guild not in COG_CONFIG.WHITELISTED_GUILDS:
        raise commands.CheckFailure('This feature is not available on this server.')
    return True

async def user_is_in_voice_channel(ctx: commands.Context) -> bool:
    if not isinstance(ctx.author, discord.Member) or ctx.author.voice is None:
        raise commands.CheckFailure(
            'You are currently not in a voice channel.')
    return True


async def user_is_listening(ctx: commands.Context) -> bool:
    session = ctx.cog._get_session(ctx.guild)
    if session is None or ctx.author.id not in session.listeners:
        raise commands.CheckFailure(
            'You are currently not listening to the bot.')
    return True


async def user_has_required_permissions(ctx: commands.Context) -> bool:
    session = ctx.cog._get_session(ctx.guild)
    if session is not None and not session.user_has_permission(ctx.author):
        raise commands.CheckFailure(
            f'Only users with the {session.config["requires_role"].mention} role can use this command.')
    return True


class Player(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._alone = asyncio.Event()
        self._restart.start()

    def cog_unload(self):
        self._restart.cancel()

    def _get_session(self, guild: discord.Guild) -> Session:
        return self.bot._player_sessions.get(guild)

    @commands.command(name='start', aliases=['join'])
    @commands.check(user_is_in_voice_channel)
    @commands.check(session_is_not_running)
    async def start(self, ctx):
        """Starts a new player session."""
        self.bot._player_sessions[ctx.guild] = Session(self.bot, ctx.author.voice.channel, run_forever=True)

    @commands.command(name='stop', aliases=['leave'])
    @commands.check(session_is_running)
    @commands.check(session_is_stoppable)
    async def stop(self, ctx):
        """Stops the currently running player session."""
        session = self._get_session(ctx.guild)

        if len(list(session.listeners)) == 0:
            session.stop()

        if ctx.author in session.stop_requests:
            raise commands.BadArgument('You have already requested to stop the player.')

        if ctx.author.id in session.listeners:
            session.stop_requests.append(ctx.author)

        stops_needed = len(list(session.listeners))
        if len(session.stop_requests) >= stops_needed:
            session.stop()
        else:
            await ctx.send(embed=discord.Embed(
                colour=discord.Colour.dark_green(),
                title='Stop Player',
                description=f'You currently need **{stops_needed - len(session.stop_requests)}** more votes to stop the player.'
            ))

    @commands.group(name='request', aliases=['play'], invoke_without_command=True)
    @commands.check(is_whitelisted_guild)
    @commands.check(user_is_in_voice_channel)
    @commands.check(user_has_required_permissions)
    @commands.cooldown(2, 30, commands.BucketType.user)
    async def request(self, ctx, *, request: YouTubeTrack):
        """Adds a YouTube video to the requests queue.

        request: YouTube search query.
        """
        try:
            if not isinstance(request, AttachmentTrack):
                await ctx.message.delete()
        except discord.Forbidden:
            pass

        session = self._get_session(ctx.guild)

        if session is None:
            session = self.bot._player_sessions[ctx.guild] = Session(self.bot, ctx.author.voice.channel)
            session.start()
        else:
            await user_is_listening(ctx)

        await ctx.send(**request.request_message)
        session.queue.add_request(request)

    @request.command(name='mp3', aliases=['local'])
    @commands.check(user_is_in_voice_channel)
    @commands.check(user_has_required_permissions)
    async def request_mp3(self, ctx, *, request: MP3Track):
        """Adds a local MP3 file to the requests queue.

        request: Local track search query.
        """
        if (await self.request.can_run(ctx)):
            await ctx.invoke(self.request, request=request)

    @request.command(name='youtube', aliases=['yt'])
    @commands.check(user_is_in_voice_channel)
    @commands.check(user_has_required_permissions)
    async def request_youtube(self, ctx, *, request: YouTubeTrack):
        """Adds a YouTube video to the requests queue.

        request: YouTube search query.
        """
        if (await self.request.can_run(ctx)):
            await ctx.invoke(self.request, request=request)

    @request.command(name='soundcloud', aliases=['sc'])
    @commands.check(user_is_in_voice_channel)
    @commands.check(user_has_required_permissions)
    async def request_soundcloud(self, ctx, *, request: SoundCloudTrack):
        """Adds a SoundCloud track to the requests queue.

        request: SoundCloud search query.
        """
        if (await self.request.can_run(ctx)):
            await ctx.invoke(self.request, request=request)

    @request.command(name='file')
    @commands.check(user_is_in_voice_channel)
    @commands.check(user_has_required_permissions)
    @commands.check(checks.is_administrator)
    async def request_file(self, ctx):
        """Adds a local file to the requests queue.

        `request`: The local file attached.
        """
        if not ctx.message.attachments:
            raise commands.BadArgument('You did not attach a file!')

        if (await self.request.can_run(ctx)):
            source = AttachmentTrack.get_source(ctx.message.attachments[0])
            await ctx.invoke(self.request, request=AttachmentTrack(*source, requester=ctx.author))

    @commands.command(name='skip')
    @commands.check(session_is_running)
    @commands.check(user_is_listening)
    async def skip(self, ctx):
        """Skips the currently playing track."""
        session = self._get_session(ctx.guild)

        if ctx.author in session.skip_requests:
            raise commands.BadArgument('You have already requested to skip.')

        session.skip_requests.append(ctx.author)

        skips_needed = len(list(session.listeners)) // 2 + 1
        if len(session.skip_requests) >= skips_needed:
            session.skip()
        else:
            await ctx.send(embed=discord.Embed(
                colour=discord.Colour.dark_green(),
                title='Skip track',
                description=f'You currently need **{skips_needed - len(session.skip_requests)}** more votes to skip this track.'
            ))

    @commands.command(name='repeat', aliases=['encore'])
    @commands.check(session_is_running)
    @commands.check(user_is_listening)
    async def repeat(self, ctx):
        """Repeats the currently playing track."""
        session = self._get_session(ctx.guild)

        if ctx.author in session.repeat_requests:
            raise commands.BadArgument('You have already requested to repeat.')

        session.repeat_requests.append(ctx.author)

        repeats_needed = len(list(session.listeners)) // 2 + 1
        if len(session.repeat_requests) >= repeats_needed:
            session.queue.add_request(session.current_track.copy(ctx.author, session.volume), at_start=True)
            await ctx.send(embed=discord.Embed(
                colour=discord.Colour.dark_green(),
                title='Repeat track',
                description='This track has been re-added to the queue.'
            ))
        else:
            await ctx.send(embed=discord.Embed(
                colour=discord.Colour.dark_green(),
                title='Repeat track',
                description=f'You currently need **{repeats_needed - len(session.repeat_requests)}** more votes to repeat this track.'
            ))

    @commands.command(name='volume', aliases=['set_volume'])
    @commands.check(session_is_running)
    @commands.check(user_is_listening)
    @commands.check(user_has_required_permissions)
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def volume(self, ctx, volume: float):
        """Set's the global player volume"""
        session = self._get_session(ctx.guild)

        if volume < 0:
            raise commands.BadArgument('You can\'t set the volume to below 0%.')
        elif volume > 2:
            raise commands.BadArgument('You can\'t set the volume to above 200%.')

        session.change_volume(volume)

        await ctx.send(embed=discord.Embed(
            colour=discord.Colour.dark_green(),
            title='Volume change',
            description=f'Setting volume to {volume:.0%}...'
        ))

    @commands.command(name='playing', aliases=['now'])
    @commands.check(session_is_running)
    async def playing(self, ctx):
        """Retrieves information on the currently playing track."""
        session = self._get_session(ctx.guild)

        play_time = session.current_track.play_time
        track_length = int(session.current_track.length)

        play_time_str = str(datetime.timedelta(seconds=play_time))
        length_str = str(datetime.timedelta(seconds=track_length))

        seek_length = 50
        seek_distance = round(seek_length * play_time / track_length)

        message = session.current_track.playing_message
        message['embed'].add_field(
            name=f'{play_time_str} / {length_str}', value=f'`{"-" * seek_distance}|{"-" * (seek_length - seek_distance)}`', inline=False)

        if ctx.guild not in COG_CONFIG.PREMIUM_GUILDS:
            if random.random() > 0.95:
                message['embed'].add_field(
                    name=f'Enjoying Meloetta? [conscider donating to help it\'s development](https://www.paypal.me/bijij/5)'
                )

        await ctx.send(**message)

    @commands.command(name='queue', aliases=['upcoming'])
    @commands.check(session_is_running)
    async def queue(self, ctx):
        """Displays the current request queue."""

        session = self._get_session(ctx.guild)

        total_length = session.current_track.length - session.current_track.play_time
        total_length += sum(track.length for track in session.queue.requests)
        length_str = str(datetime.timedelta(seconds=total_length))

        embed = discord.Embed(
            colour=discord.Colour.dark_green(),
            title=f'Upcoming requests - Total Queue Length: {length_str}'
        )

        for index, track in enumerate(session.queue.requests[:10], 1):
            embed.add_field(
                name=f'{index} - Requested by {track.requester}',
                value=track.information,
                inline=False
            )

        if not embed.fields:
            embed.description = 'There are currently no requests'

        await ctx.send(embed=embed)

    @tools.auto_help
    @commands.group(name='force')
    @commands.check(checks.is_administrator)
    async def force(self, ctx):
        """Admin commands."""
        pass

    @force.command(name='skip')
    @commands.check(session_is_running)
    async def force_skip(self, ctx):
        """Force skip the currently playing track."""
        session = self._get_session(ctx.guild)
        session.skip()

    @force.command(name='stop', aliases=['leave'])
    @commands.check(session_is_running)
    async def force_stop(self, ctx):
        """Force the session to stop."""
        session = self._get_session(ctx.guild)
        session.stop()

    @force.command(name='repeat', aliases=['encore'])
    @commands.check(session_is_running)
    async def force_repeat(self, ctx):
        """Force the currently track to be repeated."""
        session = self._get_session(ctx.guild)
        session.queue.add_request(session.current_track.copy(ctx.author, session.volume), at_start=True)

    @commands.Cog.listener()
    async def on_ready(self):
        for instance in COG_CONFIG.INSTANCES:
            if self.bot.get_channel(instance.voice_channel.id) is None:
                continue
            
            self.bot._player_sessions[instance.voice_channel.guild] = Session(self.bot, run_forever=True, stoppable=False, **instance.__dict__)

        if not MP3Track._search_ready.is_set():
            self.bot.loop.run_in_executor(None, MP3Track.setup_search)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        session = self._get_session(member.guild)
        if session is not None:
            if member.id not in session.listeners:
                for l in [session.skip_requests, session.repeat_requests, session.stop_requests]:
                    if member in l:
                        l.remove(member)

            await session.check_listeners()

            # Set alone flag for auto restart
            if not any(session.not_alone.is_set() for session in self.bot._player_sessions.values()):
                self._alone.set()
            else:
                self._alone.clear()

    @tasks.loop(hours=12)
    async def _restart(self):
        if self._restart.current_loop != 0:
            await self._alone.wait()
            self.bot.log.info(f'Automatically Restarting')
            await self.bot.logout()


def setup(bot: commands.Bot):
    if not hasattr(bot, '_player_sessions'):
        bot._player_sessions = dict()
    bot.add_cog(Player(bot))
