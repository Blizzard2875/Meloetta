import datetime
import logging
import traceback

from contextlib import suppress

import discord
from discord import member
from discord.ext import commands

from .config import CONFIG
from .context import Context
from .logging import WebhookHandler
from .help import EmbedMenuHelpCommand


class Bot(commands.Bot):

    def __init__(self, **options):
        self.start_time = datetime.datetime.min  # TODO: None?

        # TODO: ext-converters?

        self.log = logging.getLogger(__name__)

        log = logging.getLogger()
        log.setLevel(CONFIG.LOGGING.LOG_LEVEL)

        log.addHandler(WebhookHandler(CONFIG.LOGGING.WEBHOOK))
        log.addHandler(logging.StreamHandler())

        self.prefix = str(CONFIG.BOT.PREFIX)

        allowed_mentions = discord.AllowedMentions.none()
        intents = discord.Intents(
            guilds=True,
            voice_states=True,
            messages=True,
            reactions=True
        )

        super().__init__(commands.when_mentioned_or(self.prefix), help_command=EmbedMenuHelpCommand(),
                         allowed_mentions=allowed_mentions, intents=intents, **options)

        for extension in CONFIG.EXTENSIONS:
            try:
                self.load_extension(extension)
            except commands.ExtensionFailed:
                self.log.exception(f'Failed to load extension: {extension}')

    @property
    def uptime(self) -> datetime.timedelta:
        return datetime.datetime.utcnow - self.start_time

    async def on_ready(self):
        self.log.info(f'Logged in as {self.user} ({self.user.id})')

        # hacky way to fetch owner information
        await self.is_owner(self.user)
        if self.owner_id:
            self.owner = await self.fetch_user(self.owner_id)
            self.owner_ids = [self.owner_ids]
        else:
            self.owner = None

        self.owners = [await self.fetch_user(owner_id)
                        for owner_id in self.owner_ids]

    async def on_error(self, event_method: str, *args, **kwargs):
        self.log.exception(f'Ignoring exception in {event_method}\n')

    async def on_command_error(self, context: Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, (commands.CheckFailure, commands.UserInputError, 
                              commands.CommandOnCooldown, commands.MaxConcurrencyReached, commands.DisabledCommand)):
            return await context.send(
                embed=discord.Embed(
                    colour=discord.Colour.red(),
                    title=f'Error with command: {context.command.qualified_name}',
                    description=str(error)
                )
            )

        error: Exception = error.__cause__

        await context.send(
            embed=discord.Embed(
                colour=discord.Colour.dark_red(),
                title=f'Unexpected error with command: {context.command.qualified_name}',
                description=f'```py\n{type(error).__name__}: {error}\n```'
            )
        )

        tb = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        self.log.error(f'Ignoring exception in command: {context.command.qualified_name}\n\n{type(error).__name__}: {error}\n\n{tb}')

    async def process_commands(self, message: discord.Message):
        ctx = await self.get_context(message, cls=Context)
        await self.invoke(ctx)

    async def connect(self, *args, **kwargs):
        self.start_time = datetime.datetime.utcnow()

        return await super().connect(*args, **kwargs)

    def run(self):
        super().run(CONFIG.BOT.TOKEN)
