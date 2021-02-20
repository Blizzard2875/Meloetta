import discord
from discord.ext import commands
from discord.ext.commands.core import command

import wavelink

from bot import Bot, Context

from bot.config import CONFIG
COG_CONFIG = CONFIG.EXTENSIONS[__name__]


def is_not_playing(ctx: Context):
    guild_id = getattr(ctx.guild, 'id', -1)
    if ctx.guild.voice_client is not None or ctx.bot.wavelink.get_player(guild_id).is_connected:
        raise commands.CheckFailure('A player is already running in this guild.')
    return True


class Player(commands.Cog, wavelink.WavelinkMixin):
    def __init__(self, bot: Bot):
        self.bot = bot

        self.bot.loop.create_task(self.start_wavelink())

    # TODO: Remove this.
    async def cog_check(self, ctx):
        if ctx.author != self.bot.owner:
            raise commands.CheckFailure('Nah')
        return True

    async def start_wavelink(self):
        await self.bot.wait_until_ready()

        await self.bot.wavelink.initiate_node(
            host=COG_CONFIG.LAVALINK.HOSTNAME,
            rest_uri=f"http://{COG_CONFIG.LAVALINK.HOSTNAME}:2333",
            password=COG_CONFIG.LAVALINK.PASSWORD,
            identifier='meloetta',
            region='us_east'
        )

    @commands.command(name='start', aliases=['connect'])
    @commands.check(is_not_playing)
    async def start(self, ctx: Context, *, channel: discord.VoiceChannel = None):
        channel = channel or getattr(ctx.author.voice, 'channel', None)
        if channel is None:
            raise commands.BadArgument('No channel to join.')

        player = self.bot.wavelink.get_player(ctx.guild.id)
        await player.connect(channel.id)

    @commands.command(name='play')
    async def play(self, ctx: Context, *, query: str):
        tracks = await self.bot.wavelink.get_tracks(f'ytsearch:{query}')

        if len(tracks) == 0:
            raise commands.BadArgument('Could not find any search results.')

        player = self.bot.wavelink.get_player(ctx.guild.id)
        if not player.is_connected:
            await ctx.invoke(self.start)

        await player.play(tracks[0])


def setup(bot: Bot):

    # Check for player botvars
    if not hasattr(bot, 'wavelink'):
        bot.wavelink = wavelink.Client(bot=bot)

    bot.add_cog(Player(bot))
