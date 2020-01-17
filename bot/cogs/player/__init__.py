import datetime

import discord
from discord.ext import commands

from bot.config import config as BOT_CONFIG

from bot.utils import checks, tools

from .session import Session
from .track import MP3Track, YouTubeTrack, AttachmentTrack

COG_CONFIG = BOT_CONFIG.EXTENSIONS[__name__]


async def session_is_running(ctx: commands.Context) -> bool:
    if ctx.cog._get_session(ctx.guild) is None:
        raise commands.CheckFailure('A player is not running on this server.')
    return True


async def user_is_in_voice_channel(ctx: commands.Context) -> bool:
    if not isinstance(ctx.author, discord.Member) or ctx.author.voice is None:
        raise commands.CheckFailure(
            'You are currently not in a voice channel.')
    return True


async def user_is_listening(ctx: commands.Context) -> bool:
    session = ctx.cog._get_session(ctx.guild)
    if session is None or ctx.author not in session.listeners:
        raise commands.CheckFailure(
            'You are currently not listening to the bot.')
    return True


async def user_has_required_permissions(ctx: commands.Context) -> bool:
    session = ctx.cog._get_session(ctx.guild)
    if session is not None and not session.user_has_permission(ctx.author):
        raise commands.CheckFailure(
            'You do not have the required role to perform this action.')
    return True


class Player(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self._sessions = dict()

    def _get_session(self, guild: discord.Guild) -> Session:
        return self._sessions.get(guild)

    @commands.group(name="request", aliases=["play"], invoke_without_command=True)
    @commands.check(user_is_in_voice_channel)
    @commands.check(user_has_required_permissions)
    @commands.cooldown(2, 30, commands.BucketType.user)
    async def request(self, ctx: commands.Context, *, request: YouTubeTrack):
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
            session = self._sessions[ctx.guild] = Session(
                self.bot, self, ctx.author.voice.channel)

        await ctx.send(**request.request_message)
        session.queue.add_request(request)

    @request.command(name="mp3")
    async def request_mp3(self, ctx: commands.Context, *, request: MP3Track):
        """Adds a local MP3 file to the requests queue.

        request: Local track search query.
        """
        await ctx.invoke(self.request, request=request)

    @request.command(name="youtube")
    async def request_youtube(self, ctx: commands.Context, *, request: YouTubeTrack):
        """Adds a YouTube video to the requests queue.

        request: YouTube search query.
        """
        await ctx.invoke(self.request, request=request)

    @request.command(name='file')
    @commands.check(checks.is_administrator)
    async def request_file(self, ctx: commands.Context):
        """Adds a local file to the requests queue.

        `request`: The local file attached.
        """
        if not ctx.message.attachments:
            raise commands.BadArgument('You did not attach a file!')

        await ctx.invoke(self.request, request=AttachmentTrack(ctx.message.attachments[0], requester=ctx.author))

    @commands.command(name="skip")
    @commands.check(session_is_running)
    @commands.check(user_is_listening)
    async def skip(self, ctx: commands.Context):
        """Skips the currently playing track."""
        session = self._get_session(ctx.guild)

        if ctx.author in session.skip_requests:
            raise commands.CommandError("You have already requested to skip.")

        session.skip_requests.append(ctx.author)

        skips_needed = len(list(session.listeners)) // 2 + 1
        if len(session.skip_requests) >= skips_needed:
            session.voice.stop()
        else:
            await ctx.send(embed=discord.Embed(
                colour=discord.Colour.dark_green(),
                title="Skip video",
                description=f"You currently need **{skips_needed - len(session.skip_requests)}** more votes to skip this track."
            ))

    @commands.command(name='repeat')
    @commands.check(session_is_running)
    @commands.check(user_is_listening)
    async def repeat(self, ctx: commands.Context):
        """Repeats the currently playing track."""
        session = self._get_session(ctx.guild)

        if ctx.author in session.repeat_requests:
            raise commands.CommandError(
                'You have already requested to repeat.')

        session.repeat_requests.append(ctx.author)

        repeats_needed = len(list(session.listeners)) // 2 + 1
        if len(session.repeat_requests) >= repeats_needed:
            session.queue.add_request(session.current_track, at_start=True)
        else:
            await ctx.send(embed=discord.Embed(
                colour=discord.Colour.dark_green(),
                title='Repeat track',
                description=f'You currently need **{repeats_needed - len(session.repeat_requests)}** more votes to repeat this track.'
            ))

    @commands.command(name='volume')
    @commands.check(session_is_running)
    @commands.check(user_is_listening)
    @commands.check(user_has_required_permissions)
    @commands.cooldown(2, 30, commands.BucketType.guild)
    async def volume(self, ctx: commands.Context, volume: float):
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
    async def playing(self, ctx: commands.Context):
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

        await ctx.send(**message)

    @commands.command(name="queue", aliases=["upcoming"])
    @commands.check(session_is_running)
    async def queue(self, ctx: commands.Context):
        """Displays the current request queue."""

        session = self._get_session(ctx.guild)

        total_length = sum(track.length for track in session.queue.requests)
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
    @commands.group(name='force', invoke_without_command=True)
    @commands.check(checks.is_administrator)
    async def force(self, ctx: commands.Context):
        """Admin commands."""
        pass

    @force.command(name='skip')
    @commands.check(session_is_running)
    async def force_skip(self, ctx: commands.Context):
        """Force skip the currently playing track."""
        session = self._get_session(ctx.guild)
        session.voice.stop()

    @commands.Cog.listener()
    async def on_ready(self):
        for instance in COG_CONFIG.INSTANCES:
            self._sessions[instance.voice_channel.guild] = Session(
                self.bot, self, run_forever=True, **instance.__dict__)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        session = self._get_session(member.guild)
        if session is not None:
            if after is None:
                if member in session.skip_requests:
                    session.skip_requests.remove(member)
                if member in session.repeat_requests:
                    session.repeat_requests.remove(member)

            if session.voice is not None:
                session.check_listeners()


def setup(bot: commands.Bot):
    bot.add_cog(Player(bot))
