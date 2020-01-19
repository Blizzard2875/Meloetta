import asyncio

from typing import Generator

import discord
from discord.ext import commands

from .queue import Queue, Radio

from bot.config import config as BOT_CONFIG
COG_CONFIG = BOT_CONFIG.EXTENSIONS[__name__[:__name__.rindex('.')]]


class Session:

    def __init__(self, bot: discord.Client, cog: commands.Cog, voice_channel: discord.VoiceChannel, *,
                 log_channel: discord.TextChannel = None, run_forever: bool = False, stoppable: bool = True, **kwargs):
        """

        Args:
            voice_channel (discord.VoiceChannel): The voice channel the session should start playing in.

        Kwargs:
            log_channel (discord.TextChannel): Specifies a channel to log playback history.
            run_forever (bool): Determines wether the session should run forever.
            stoppable (bool): Determines wether the session should be able to be stopped by a user.

        """
        self.bot = bot
        self.cog = cog
        self.voice_channel = voice_channel

        self.log_channel = log_channel
        self.stoppable = stoppable
        self.config = kwargs
        self.queue_config = self.config.get('queue')

        self.alone = asyncio.Event()
        self.timeout = self.config.get('timeout') or COG_CONFIG.DEFAULT_TIMEOUT

        self.skip_requests = list()
        self.repeat_requests = list()
        self.stop_requests = list()

        self.voice = None
        self.current_track = None

        if run_forever:
            self.queue = Radio(self.queue_config)
        else:
            self.queue = Queue(self.queue_config)

        self.volume = self.config.get(
            'default_volume') or COG_CONFIG.DEFAULT_VOLUME

        self.is_playing = True
        self.play_next_song = asyncio.Event()

        asyncio.create_task(self.session_task())

    @property
    def listeners(self) -> Generator[discord.Member, None, None]:
        """Members listening to this session.

        A member is classified as a listener if:
            - They are not a bot account
            - They are not deafened

        Returns:
            `generator` of `discord.Member`: A generator consisting ow members listening to this session.

        """
        for member in self.voice.channel.members:
            if not member.bot and not (member.voice.deaf or member.voice.self_deaf):
                yield member

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
        self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

    async def play_track(self):
        """Plays the next track in the queue."""

        if COG_CONFIG.PLAYING_STATUS_GUILD is not None:
            if self.voice_channel.guild.id == COG_CONFIG.PLAYING_STATUS_GUILD.id:
                await self.bot.change_presence(activity=discord.Activity(
                    name=self.current_track.status_information, type=discord.ActivityType.playing
                ))

        if self.log_channel is not None:
            await self.log_channel.send(**self.current_track.playing_message)

        self.voice.play(self.current_track, after=self.toggle_next)

    def stop(self):
        """Stops this session."""
        self.is_playing = False
        self.voice.stop()

    async def check_listeners(self):
        """Checks if there is anyone listening and pauses / resumes accordingly."""
        if list(self.listeners):
            if self.voice.is_paused():
                self.voice.resume()
                self.alone.set()
        elif self.voice.is_playing():
            self.voice.pause()
            self.alone.clear()

            # Wait to see if the bot stays alone for it's max timeout duration
            if self.stoppable:
                try:
                    await asyncio.wait_for(self.alone.wait(), self.timeout)
                except asyncio.TimeoutError:
                    self.stop()

    async def session_task(self):

        self.voice = await self.voice_channel.connect()
        self.voice.session = self

        while self.is_playing:
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
        del self.cog._sessions[self.voice.guild]
        await self.voice.disconnect()
