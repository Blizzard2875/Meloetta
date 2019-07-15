import asyncio

from typing import Dict, Generator

import discord

from bot.config import CONFIG as BOT_CONFIG

from .queue import Queue, Radio

COG_CONFIG = BOT_CONFIG.COGS[__name__[:__name__.rindex(".")]]


class Session:

    def __init__(self, bot: discord.Client, voice_channel: discord.VoiceChannel, *, log_channel: discord.TextChannel = None, run_forever: bool = False, **kwargs):
        """

        Args:
            voice_channel (discord.VoiceChannel): The voice channel the session should start playin in.

        Kwargs: 
            run_forever (bool): Determines wether the session should run forever
            log_channel (discord.TextChannel): Specifies a channel to log playback history.

        """
        self.bot = bot
        self.voice_channel = voice_channel

        self.log_channel = log_channel
        self.config = kwargs
        self.queue_config = self.config.get('queue')

        self.skip_requests = list()
        # self.repeat_requests = list() # TODO: Repeat requests?

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
            `generator` of `discord.Member`: A generator concisting ow members listening to this session.

        """
        for member in self.voice_channel.members:
            if not member.bot and not (member.voice.deaf or member.voice.self_deaf):
                yield member

    def user_has_permission(self, user: discord.Member) -> bool:
        """Checks if a user has permission to interact with this session."""
        if self.config.get("requires_role") is not None:
            return self.config.get("requires_role") in user.roles
        return True

    def change_volume(self, volume: float):
        """Changes this session's volume"""
        self.volume = volume
        self.current_track.volume = self.volume

    def toggle_next(self, error=None):
        """"""
        if error:
            pass
        self.skip_requests.clear()
        # self.repeat_requests.clear()
        self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

    async def play_next_track(self):
        """Plays the next track in the queue."""
        self.current_track = self.queue.next_track()
        self.current_track.volume = self.volume

        if self.voice_channel.guild == COG_CONFIG.PLAYING_STATUS_GUILD:
            await self.bot.change_presence(activity=discord.Activity(
                name=self.current_track.information, type=discord.ActivityType.playing
            ))

        if self.log_channel is not None:
            await self.log_channel.send(**self.current_track.playing_message)

        self.voice.play(self.current_track, after=self.toggle_next)

    def stop(self):
        """Stops this session."""
        self.is_playing = False
        self.voice.stop()

    def check_listeners(self):
        """Checks if there is anyone listening and pauses / resumes accordingly."""
        if list(self.listeners):
            if self.voice.is_paused():
                self.voice.resume()
        elif self.voice.is_playing():
            self.voice.pause()

    async def session_task(self):

        self.voice = await self.voice_channel.connect()

        while self.is_playing:
            self.play_next_song.clear()
            await self.play_next_track()
            self.check_listeners()
            await self.play_next_song.wait()

        await self.voice.disconnect()
