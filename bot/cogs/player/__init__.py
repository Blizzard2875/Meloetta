import discord
from discord.ext import commands

from bot.config import CONFIG as BOT_CONFIG

from .session import Session
from .track import MP3Track, YouTubeTrack

COG_CONFIG = BOT_CONFIG.COGS[__name__]


async def session_is_running(ctx: commands.Context) -> bool:
    """A player is not running on this server."""
    return ctx.cog._get_session(ctx.guild) is not None


async def user_is_in_voice_channel(ctx: commands.Context) -> bool:
    """You are currently not in a voice channel."""
    return isinstance(ctx.author, discord.Member) and ctx.author.voice is not None


async def user_is_listening(ctx: commands.Context) -> bool:
    """You are currently not listening to the bot."""
    session = ctx.cog._get_session(ctx.guild)
    return session is not None and ctx.author in session.listeners


async def user_has_required_permissions(ctx: commands.Context) -> bool:
    """You do not have the required role to perform this action."""
    session = ctx.cog._get_session(ctx.guild)
    return session is None or session.user_has_permission(ctx.author)


class Player(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self._sessions = dict()

    def _get_session(self, guild: discord.Guild) -> Session:
        return self._sessions.get(guild)

    @commands.group(name="request", invoke_without_subcommand=True)
    @commands.check(user_is_in_voice_channel)
    @commands.check(user_has_required_permissions)
    async def request(self, ctx: commands.Context, *, request: YouTubeTrack):
        """Adds a YouTube video to the requests queue.

        request: YouTube search query.
        """

        session = self._get_session(ctx.guild)

        if session is None:
            session = Session(self.bot, ctx.author.voice.channel)

        await ctx.send(**request.request_message)
        session.queue.add_request(request)

    @request.command(name="mp3")
    async def request_mp3(self, ctx: commands.Context, *, request: MP3Track):
        """Adds a local MP3 file to the requests queue.

        request: Local track search query.
        """
        await self.request(ctx, request=request)

    @request.command(name="youtube")
    async def request_youtube(self, ctx: commands.Context, *, request: YouTubeTrack):
        """Adds a YouTube video to the requests queue.

        request: YouTube search query.
        """
        await self.request(ctx, request=request)

    @commands.command(name="skip")
    @commands.check(session_is_running)
    @commands.check(user_is_listening)
    async def skip(self, ctx: commands.Context):
        """Skips the currently playing track."""
        session = self._get_session(ctx.guild)

        if ctx.author in session.skip_requests:
            raise commands.CommandError("You have already requested to skip.")

        session.skip_requests.append(ctx.author)

        skips_needed = len(session.listeners) // 2 + 1
        if len(session.skip_requests) >= skips_needed:
            session.voice.stop()
        else:
            await ctx.send(embed=discord.Embed(
                colour=discord.Colour.dark_green(),
                title="Skip video",
                description=f"You currently need **{skips_needed - len(skip_requests)}** more votes to skip this track."
            ))

    @commands.command(name="playing", aliases=["now"])
    @commands.check(session_is_running)
    async def playing(self, ctx: commands.Context):
        """Returns information on the currently playing track

        """
        session = self._get_session(ctx.guild)
        await ctx.send(**session.current_track.playing_message)

    @commands.command(name="queue", aliases=["upcoming"])
    @commands.check(session_is_running)
    async def queue(self, ctx: commands.Context):

        session = self._get_session(ctx.guild)

        embed = discord.Embed(
            colour=discord.Colour.dark_green(),
            title="Upcoming requests"
        )

        for index, track in enumerate(session.queue.requests[:10], 1):
            embed.add_field(
                name=f"{index} - Requested by {track.requester}",
                value=track.information
            )

        if not embed.fields:
            embed.description = "There are currently no requests"

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_ready(self):
        for instance in COG_CONFIG.INSTANCES:
            self._sessions[instance.voice_channel.guild] = Session(
                self.bot, run_forever=True, **instance.__dict__)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        session = self._get_session(member.guild)
        if session is not None:
            if after is None and member in session.skip_requests:
                session.skip_requests.remove(member)

            if session.voice is not None:
                session.check_listeners()


def setup(bot: commands.Bot):
    bot.add_cog(Player(bot))
