import asyncio
import datetime
import inspect
import logging
import traceback

import discord
from discord.ext import commands

try:
    import uvloop
except ImportError:
    pass
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

from bot.config import CONFIG, init_config
from bot.help import EmbedHelpCommand

_start_time = datetime.datetime.utcnow()

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(*CONFIG.PREFIXES),
    case_insensitive=True,
    help_command=EmbedHelpCommand(dm_help=None, dm_help_threshold=500),
    description=CONFIG.DESCRIPTION,
    max_messages=100,
    fetch_offline_members=False,
    activity=discord.Activity(
        name="Nothing", type=discord.ActivityType.playing
    )
)

bot.log = logging.getLogger(__name__)
bot.log.setLevel(logging.INFO)

handler = logging.FileHandler(filename=f"{CONFIG.APP_NAME}.log")
handler.setFormatter(logging.Formatter(
    "{asctime} - {levelname} - {message}", style="{"))

bot.log.addHandler(handler)
bot.log.addHandler(logging.StreamHandler())

bot.log.info("Instance starting...")


@bot.event
async def on_ready():
    bot.log.info(f"Succesfully logged in as {bot.user}...")
    bot.log.info(f"\tGuilds: {len(bot.guilds)}")
    bot.log.info(f"\tTook: {datetime.datetime.utcnow() - _start_time}")


@bot.event
async def on_command_error(ctx: commands.Context, e: Exception):

    bot.log.error(e)

    if isinstance(e, commands.CheckFailure):

        # Command Checks
        for check in ctx.command.checks:

            result = check(ctx)
            if inspect.isawaitable(result):
                result = await result

            if not result:
                return await ctx.author.send(embed=discord.Embed(
                    title=f"Error with command: {ctx.command.name}",
                    description=check.__doc__
                ))

        # Cog Checks
        cog_checks = [ctx.cog.cog_check, ctx.cog.cog_check_once]
        for check in cog_checks:

            result = check(ctx)
            if inspect.isawaitable(result):
                result = await result

            if not result:
                await ctx.send(embed=discord.Embed(
                    title=f"Error with command: {ctx.command.name}",
                    description=check.__doc__
                ))

        # TODO: Global Checks
        return

    embed = discord.Embed(
        title=f"Error with command: {ctx.command.name}",
        description=f"```py\n{type(e).__name__}: {e}\n```"
    )
    await ctx.send(embed=embed)

    if isinstance(e, (commands.BadArgument, commands.BadUnionArgument)):
        return

    bot.log.error(f"{type(e).__name__}: {e}")
    bot.log.error("".join(traceback.format_exception(type(e), e, e.__traceback__)))

    if isinstance(e, (commands.CommandError, asyncio.TimeoutError)):
        return

    embed.add_field(name="Channel:", value=f"<#{ctx.channel.id}>")
    embed.add_field(name="User:", value=f"<@{ctx.author.id}>")
    await CONFIG.ERROR_LOG_CHANNEL.send(embed=embed)


if __name__ == "__main__":

    # Initialise bot dependant configuration
    init_config(bot)

    # Load cogs
    for cog in CONFIG.COGS:
        try:
            bot.load_extension(cog)
        except Exception as e:
            bot.log.error(f"Failed to load cog: {cog}")
            bot.log.error(f"\t{type(e).__name__}: {e}")
            bot.log.error(traceback.format_exc())

    bot.run(CONFIG.TOKEN)
