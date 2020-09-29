import asyncio
import datetime
import logging
import traceback

import discord
import wavelink

from discord.ext import commands

from bot.help import EmbedHelpCommand

import bot.config as config
from bot.config import config as BOT_CONFIG

try:
    import uvloop
except ImportError:
    pass
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

_start_time = datetime.datetime.utcnow()


class MyBot(commands.Bot):
    ...


intents = discord.Intents()
intents.guilds = True
intents.voice_states = True
intents.messages = True
intents.reactions = True

# Create bot instance
config._bot = bot = MyBot(
    command_prefix=commands.when_mentioned_or(*BOT_CONFIG.PREFIXES),
    activity=discord.Activity(
        name=f'for Commands: {BOT_CONFIG.PREFIXES[0]}help', type=discord.ActivityType.watching),
    intents=intents,
    case_insensitive=True,
    help_command=EmbedHelpCommand(),
    fetch_offline_members=False,
    guild_subscriptions=False,
)

bot.__version__ = BOT_CONFIG.VERSION
bot._start_time = _start_time
bot.dm_help = False


class DivertMemberReferences(logging.Filter):
    def __init__(self, returning):
        self.returning = returning
        super().__init__(name='discord.state')

    def filter(self, record: logging.LogRecord):
        if record.levelno == logging.WARNING and 'referencing an unknown' in record.msg:
            return self.returning
        return not self.returning


# Setup logging
bot.log = logging.getLogger(__name__)
bot.log.setLevel(logging.getLevelName(BOT_CONFIG.LOGGING_LEVEL))

discord_log = logging.getLogger(discord.__name__)
discord_log.setLevel(logging.getLevelName(BOT_CONFIG.LOGGING_LEVEL_EXT))

wavelink_log = logging.getLogger(wavelink.__name__)
wavelink_log.setLevel(logging.getLevelName(BOT_CONFIG.LOGGING_LEVEL_EXT))

handler = logging.FileHandler(filename=f'{BOT_CONFIG.APP_NAME}.log')
handler.addFilter(DivertMemberReferences(False))
handler.setFormatter(logging.Formatter(
    '{asctime} - {module}:{levelname} - {message}', style='{'))

state_handler = logging.FileHandler(filename=f'{BOT_CONFIG.APP_NAME}.state.log')
state_handler.addFilter(DivertMemberReferences(True))
state_handler .setFormatter(logging.Formatter(
    '{asctime} - {module}:{levelname} - {message}', style='{'))

bot.log.addHandler(handler)
bot.log.addHandler(logging.StreamHandler())

discord_log.addHandler(handler)
discord_log.addHandler(state_handler)
discord_log.addHandler(logging.StreamHandler())

wavelink_log.addHandler(handler)
wavelink_log.addHandler(logging.StreamHandler())

bot.log.info('Instance starting...')


@bot.event
async def on_ready():
    bot.log.info(f'Succesfylly loggged in as {bot.user}...')
    bot.log.info(f'\tGuilds: {len(bot.guilds)}')
    bot.log.info(f'\tTook: {datetime.datetime.utcnow() - _start_time}')

    # Fetch app owner information
    app = await bot.application_info()
    bot.owner = app.owner


@bot.event
async def on_error(event_method, *args, **kwargs):
    if event_method == 'command_error':
        return
    bot.log.error(f'Exception in event: {event_method}', exc_info=True, stack_info=True)


@bot.event
async def on_command_error(ctx: commands.Context, e: Exception):
    # Ignore if CommandNotFound
    if isinstance(e, commands.CommandNotFound):
        return

    # Ignore if command has on error handler
    if hasattr(ctx.command, 'on_error'):
        return

    # Ignore if cog has a command error handler
    if ctx.cog is not None:
        if commands.Cog._get_overridden_method(ctx.cog.cog_command_error) is not None:
            return

    # Respond with error message if CheckFailure, CommandDisabled, CommandOnCooldown or UserInputError
    if isinstance(e, (commands.CheckFailure, commands.CommandOnCooldown, commands.UserInputError)):
        return await ctx.send(embed=discord.Embed(
            title=f'Error with command: {ctx.command.qualified_name}',
            description=str(e)
        ))

    # Ignore http 403 / 500 related errors
    if isinstance(e, commands.CommandInvokeError):

        if isinstance(e.original, discord.Forbidden):
            return await ctx.send(embed=discord.Embed(
                title=F'Error with command: {ctx.command.qualified_name}',
                description="The bot does not have the permissions required..."
            ))

        if isinstance(e.original, discord.HTTPException):
            if e.original.status >= 500:
                return await ctx.send(embed=discord.Embed(
                    title=F'Error with command: {ctx.command.qualified_name}',
                    description="Discord had an error, plese try again later..."
                ))

    # Otherwise log error
    tb = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
    bot.log.error(f'Ignoring exception in command: {ctx.command.qualified_name}\n\n{type(e).__name__}: {e}\n\n{tb}')

    # Send to user
    embed = discord.Embed(
        title=f'Error with command: {ctx.command.qualified_name}',
        description=f'```py\n{type(e).__name__}: {e}\n```'
    )
    await ctx.send(embed=embed)

    # Send to error log channel
    embed.add_field(
        name='Channel', value=f'<#{ctx.channel.id}> (#{ctx.channel})')
    embed.add_field(name='User', value=f'<@{ctx.author.id}> ({ctx.author})')
    await BOT_CONFIG.ERROR_LOG_CHANNEL.send(embed=embed)

if __name__ == '__main__':

    # Load extensions from config
    for extension in BOT_CONFIG.EXTENSIONS:
        try:
            bot.load_extension(extension)
        except Exception as e:
            bot.log.error(f'Failed to load extension: {extension}')
            bot.log.error(f'\t{type(e).__name__}: {e}', exc_info=True, stack_info=True)

    bot.run(BOT_CONFIG.TOKEN)
