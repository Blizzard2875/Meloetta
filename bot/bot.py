import datetime
import logging

from contextlib import suppress

import discord
from discord.ext import commands

from .config import CONFIG
from .context import Context
# from .logging import WebhookHandler
from .help import EmbedMenuHelpCommand


class Bot(commands.Bot):
    
    def __init__(self, **options):
        self.start_time = datetime.datetime.min  # TODO: None?

        # TODO: ext-converters?

        self.log = logging.getLogger(__name__)
        self.log.setLevel(CONFIG.LOGGING.LOG_LEVEL)

        # TODO: Webhook Logging Handler?

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
            with suppress(commands.ExtensionFailed):
                self.load_extension(extension)

    @property
    def uptime(self) -> datetime.timedelta:
        return datetime.datetime.utcnow - self.start_time

    async def on_ready(self):
        self.log.info(f'Logged in as {self.user} ({self.user.id})')

        # hacky way to fetch owner information
        await self.is_owner(self.user) 
        if self.owner_id:
            self.owner = self.get_user(self.owner_id)

    async def on_error(self, event_method: str, *args, **kwargs):
        self.log.exception(f'Ignoring exception in {event_method}\n')

    async def on_command_error(self, context: Context, exception: Exception):
        # TODO: This
        ...
    
    async def process_commands(self, message: discord.Message):
        ctx = await self.get_context(message, cls=Context)
        await self.invoke(ctx)

    async def connect(self, *args, **kwargs):
        self.start_time = datetime.datetime.utcnow()

        return await super().connect(*args, **kwargs)

    def run(self):
        super().run(CONFIG.BOT.TOKEN)
