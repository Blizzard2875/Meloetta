import discord
from discord.ext import commands

from bot.config import CONFIG as BOT_CONFIG

from .session import Session
from .track import YouTubeTrack

COG_CONFIG = BOT_CONFIG.COGS[__name__]


async def session_is_running(ctx: commands.Context) -> bool:
    return ctx.cog._get_session(ctx.guild) is not None


async def user_is_in_voice_channel(ctx: commands.Context) -> bool:
    return ctx.author.voice is not None


async def user_is_listening(ctx: commands.Context) -> bool:
    return ctx.author in ctx.cog._get_session(ctx.guild).listeners


class Player(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self._sessions = dict()

    def _get_session(self, guild: discord.Guild) -> Session:
        return self._sessions.get(guild)

    @commands.command(name="request")
    @commands.check(user_is_in_voice_channel)
    async def request(self, ctx: commands.Context, *, request: YouTubeTrack):
        """Adds a YouTube video to the requests

        request: YouTube search query.
        """

        session = self._get_session(ctx.guild)

        if session is None:
            session = Session(self.bot, ctx.author.voice.channel)

        await request.send_request_embed(ctx, ctx.author)
        session.queue.add_request(request, ctx.author)

    @commands.command(name="skip")
    @commands.check(session_is_running)
    @commands.check(user_is_listening)
    async def skip(self, ctx: commands.Context):
        """Skips a track

        """
        session = self._get_session(ctx.guild)
        session.voice.stop()

    @commands.command(name="playing", aliases=["now"])
    @commands.check(session_is_running)
    async def playing(self, ctx: commands.Context):
        """Returns information on the currently playing track

        """
        session = self._get_session(ctx.guild)
        await session.current_track.send_playing_embed(ctx)

    @commands.command(name="queue", aliases=["upcoming"])
    @commands.check(session_is_running)
    async def queue(self, ctx: commands.Context):
        pass

    @commands.command(name="next")
    @commands.check(session_is_running)
    async def next(self, ctx: commands.Context):
        pass

    @commands.Cog.listener()
    async def on_ready(self):
        for instance in COG_CONFIG.INSTANCES:
            self._sessions[instance.voice_channel.guild] = Session(self.bot, run_forever=True,
                                                                   **instance.__dict__)


def setup(bot: commands.Bot):
    bot.add_cog(Player(bot))
