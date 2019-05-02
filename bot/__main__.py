import asyncio
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


bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(*CONFIG.PREFIXES),
    case_insensitive=True,
    help_command=None,  # TODO: Custom Help command
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
