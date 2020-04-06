import asyncio

from typing import Generator

import discord

from .queue import Queue, Radio

from bot.config import config as BOT_CONFIG
COG_CONFIG = BOT_CONFIG.EXTENSIONS[__name__[:__name__.rindex('.')]]


class Session(discord.VoiceClient):

    def __init__(self, client, timeout, channel):
        super().__init__(client, timeout, channel)

        self.client = client
        self.skip_requests = list()
        self.repeat_requests = list()
        self.stop_requests = list()
        self.current_track = None
        self._is_playing = False
        self.play_next_song = asyncio.Event()

    @property
    def listeners(self) -> Generator[int, None, None]:
        """Members listening to this session.

        A member is classified as a listener if:
            - They are the not the bot
            - They are not deafened

        Returns:
            `generator` of `int`: A generator consisting of the user_id's of members listening to the bot.

        """
        for user_id, state in self.channel.voice_states.items():
            if user_id != self.user.id and not (state.deaf or state.self_deaf):
                yield user_id

    def user_has_permission(self, user: discord.Member) -> bool:
        """Checks if a user has permission to interact with this session."""
        if self.config.get('requires_role') is not None:
            return self.config.get('requires_role') in user.roles
        return True

    def change_volume(self, volume: float):
        """Changes this session's volume"""
        self.volume = volume
        self.current_track.volume = self.volume

    def toggle_next(self, error=None):
        """Sets the next track to start playing"""
        if error:
            pass
        self.skip_requests.clear()
        self.repeat_requests.clear()
        self.loop.call_soon_threadsafe(self.play_next_song.set)

    async def play_track(self):
        """Plays the next track in the queue."""

        if COG_CONFIG.PLAYING_STATUS_GUILD is not None:
            if self.channel.guild.id == COG_CONFIG.PLAYING_STATUS_GUILD.id:
                await self.client.change_presence(activity=discord.Activity(
                    name=self.current_track.status_information, type=discord.ActivityType.playing
                ))

        if self.log_channel is not None:
            await self.log_channel.send(**self.current_track.playing_message)

        self.play(self.current_track, after=self.toggle_next)

    def start(self, log_channel: discord.TextChannel = None, run_forever: bool = False, stoppable: bool = True, **kwargs):
        """Start's the player session.

        Args:
            log_channel (discord.TextChannel): Specifies a channel to log playback history.
            run_forever (bool): Determines wether the session should run forever.
            stoppable (bool): Determines wether the session should be able to be stopped by a user.

        """
        self.log_channel = log_channel
        self.stoppable = stoppable
        self.config = kwargs
        self.queue_config = self.config.get('queue')

        self.not_alone = asyncio.Event()
        self.timeout = self.config.get('timeout') or COG_CONFIG.DEFAULT_TIMEOUT

        if run_forever:
            self.queue = Radio(self.queue_config)
        else:
            self.queue = Queue(self.queue_config)

        self.volume = self.config.get(
            'default_volume') or COG_CONFIG.DEFAULT_VOLUME

        self._is_playing = True

        asyncio.create_task(self.session_task())

        return self

    def skip(self):
        """Skips the current track."""
        super().stop()

    def stop(self):
        """Stops this session."""
        self._is_playing = False
        super().stop()

    async def check_listeners(self):
        """Checks if there is anyone listening and pauses / resumes accordingly."""
        if list(self.listeners):
            if self.is_paused():
                self.resume()
                self.not_alone.set()
        elif self.is_playing():
            self.pause()
            self.not_alone.clear()

            # Wait to see if the bot stays alone for it's max timeout duration
            if self.stoppable:
                try:
                    await asyncio.wait_for(self.not_alone.wait(), self.timeout)
                except asyncio.TimeoutError:
                    self.stop()

    async def session_task(self):

        self.session = self

        while self._is_playing:
            self.play_next_song.clear()

            # if no more tracks in queue exit
            self.current_track = self.queue.next_track()
            if self.current_track is None:
                self.stop()
                break

            # Set volume and play new track
            self.current_track.volume = self.volume
            await self.play_track()
            await self.check_listeners()

            # Wait for track to finish before playing next track
            await self.play_next_song.wait()

        # Delete session and disconnect
        if hasattr(self.client, '_player_sessions'):
            del self.client._player_sessions[self.guild]
        await self.disconnect()
