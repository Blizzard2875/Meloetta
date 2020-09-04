import asyncio

from contextlib import suppress
from typing import Generator, List

import discord
from discord.ext import commands
import wavelink

from .queue import Queue, Radio
from .track import Track, MP3Track

from bot.config import config as BOT_CONFIG
COG_CONFIG = BOT_CONFIG.EXTENSIONS[__name__[:__name__.rindex('.')]]


class Session(wavelink.Player):

    def setup(self, *, log_channel_id: int = None, run_forever: bool = False, stoppable: bool = True, request: Track = None, **kwargs):
        self.log_channel = self.client.get_channel(log_channel_id)
        self.run_forever = run_forever
        self.stoppable = stoppable
        self.config = kwargs
        self.queue_config = self.config.get('queue')
        self.dead = False

        self.not_alone = asyncio.Event()
        self.timeout = self.config.get('timeout') or COG_CONFIG.DEFAULT_TIMEOUT

        self.skip_requests: List[discord.User] = list()
        self.repeat_requests: List[discord.User] = list()
        self.stop_requests: List[discord.User] = list()

        self.current_track = None

        if not run_forever:
            self.queue = Queue(self.queue_config)
        else:
            self.queue = Radio(self.queue_config)

        if request is not None:
            self.queue.add_request(request)

        self.volume = self.config.get('default_volume') or COG_CONFIG.DEFAULT_VOLUME

        self.play_next_song = asyncio.Event()

        asyncio.create_task(self.session_task())

    @property
    def listeners(self) -> Generator[int, None, None]:
        """Members listening to this session.

        A member is classified as a listener if:
            - They are the not the bot
            - They are not deafened

        Returns:
            `generator` of `int`: A generator consisting of the user_id's of members listening to the bot.

        """
        if self.channel is None:
            return

        for user_id, state in self.channel.voice_states.items():
            if user_id != self.client.user.id and not (state.deaf or state.self_deaf):
                yield user_id

    def user_has_permission(self, user: discord.Member) -> bool:
        """Checks if a user has permission to interact with this session."""
        if self.config.get('requires_role') is not None:
            return self.config.get('requires_role') in user.roles
        return True

    async def toggle_next(self):
        """Sets the next track to start playing"""
        if self.dead:
            return

        self.current_track = self.queue.next_track()

        # if no more tracks in queue exit
        if self.current_track is None:
            await self.disconnect(force=False)
            return

        # Clear the queues
        self.skip_requests.clear()
        self.repeat_requests.clear()

        # Create wavelink object for track
        try:
            self._source = None  # this fixes things
            if isinstance(self.current_track, MP3Track):
                if self.node != Track.local_node:
                    await self.change_node(Track.local_node)
            else:
                if self.node != Track.global_node:
                    await self.change_node(Track.global_node)

            await self.current_track.setup(self.client, self.node)
        except (commands.BadArgument, wavelink.LavalinkException):
            self.client.log.error(f'Failed to play track {self.current_track._title!r}.')

            if self.log_channel is not None:
                with suppress(discord.HTTPException):
                    await self.log_channel.send(embed=discord.Embed(colour=discord.Colour.red(), title='Error playing track, skipping.'))   

            await asyncio.sleep(3)
            return await self.toggle_next()

        # If on r/Pokemon update presence
        if COG_CONFIG.PLAYING_STATUS_GUILD is not None:
            if self.guild.id == COG_CONFIG.PLAYING_STATUS_GUILD.id:
                with suppress(discord.HTTPException):
                    await self.client.change_presence(activity=discord.Activity(
                        name=self.current_track.status_information, type=discord.ActivityType.playing
                    ))

        # If server has log channel log new track
        if self.log_channel is not None:
            with suppress(discord.HTTPException):
                await self.log_channel.send(**self.current_track.playing_message)

        # Play the new track
        await self.play(self.current_track.track)

    async def skip(self):
        """Skips the currently playing track"""
        await self.stop()

    async def check_listeners(self):
        """Checks if there is anyone listening and pauses / resumes accordingly."""
        if len(list(self.listeners)) > 0:
            if self.is_paused():
                await self.resume()
                self.not_alone.set()
        elif not self.is_paused():
            await self.set_pause(True)
            self.not_alone.clear()

            # Wait to see if the bot stays alone for it's max timeout duration
            if self.stoppable:
                try:
                    await asyncio.wait_for(self.not_alone.wait(), self.timeout)
                except asyncio.TimeoutError:
                    self.disconnect(force=False)

    async def session_task(self):
        try:
            await self.set_volume(self.volume)
            await self.toggle_next()
            await self.check_listeners()
        except Exception:
            self.client.log.error('Exception in session', exc_info=True, stack_info=True)

    def cleanup(self):
        self.client._recover_player = self.channel, self.queue
        super().cleanup()

    async def restart(self, force: bool = False):
        config = self.config
        voice_channel = self.channel
        log_channel = self.log_channel
        await self.disconnect(force=True)
        self.dead = True
        await asyncio.sleep(15)
        new_session = await voice_channel.connect(cls=Session)
        new_session.setup(log_channel_id=log_channel.id if log_channel else None, run_forever=True, stoppable=False, **config)
