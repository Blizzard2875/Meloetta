import asyncio

from typing import Generator

import discord
from discord.ext import commands

from .queue import Queue, Radio

from bot.config import config as BOT_CONFIG
COG_CONFIG = BOT_CONFIG.EXTENSIONS[__name__[:__name__.rindex('.')]]


class Session:

    def __init__(self, bot: discord.Client, voice_channel: discord.VoiceChannel, *,
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
        self.guild = voice_channel.guild
        self.player = self.bot._wavelink.get_player(voice_channel.guild.id)

        self.log_channel = log_channel
        self.stoppable = stoppable
        self.config = kwargs
        self.queue_config = self.config.get('queue')

        self.not_alone = asyncio.Event()
        self.timeout = self.config.get('timeout') or COG_CONFIG.DEFAULT_TIMEOUT

        self.skip_requests = list()
        self.repeat_requests = list()
        self.stop_requests = list()

        self.current_track = None

        if run_forever:
            self.queue = Radio(self.queue_config)
        else:
            self.queue = Queue(self.queue_config)

        self.volume = self.config.get(
            'default_volume') or COG_CONFIG.DEFAULT_VOLUME

        self.is_playing = True
        self.play_next_song = asyncio.Event()

        asyncio.create_task(self.session_task(voice_channel))

    @property
    def current_track_play_time(self) -> float:
        return round(self.player.position / 1000, 2)

    @property
    def listeners(self) -> Generator[int, None, None]:
        """Members listening to this session.

        A member is classified as a listener if:
            - They are the not the bot
            - They are not deafened

        Returns:
            `generator` of `int`: A generator consisting of the user_id's of members listening to the bot.

        """
        voice_channel = self.bot.get_channel(int(self.player.channel_id))
        if voice_channel is None:
            return

        for user_id, state in voice_channel.voice_states.items():
            if user_id != self.bot.user.id and not (state.deaf or state.self_deaf):
                yield user_id

    def user_has_permission(self, user: discord.Member) -> bool:
        """Checks if a user has permission to interact with this session."""
        if self.config.get('requires_role') is not None:
            return self.config.get('requires_role') in user.roles
        return True

    async def change_volume(self, volume: float):
        """Changes this session's volume"""
        await self.player.set_volume(volume)

    async def toggle_next(self):
        """Sets the next track to start playing"""
        self.current_track = self.queue.next_track()

        # if no more tracks in queue exit
        if not self.is_playing or self.current_track is None:
            del self.bot._player_sessions[self.guild]
            await self.player.disconnect()
            await self.player.destroy()
            return

        self.skip_requests.clear()
        self.repeat_requests.clear()

        await self.play_track()

    async def play_track(self):
        """Plays the next track in the queue."""

        if COG_CONFIG.PLAYING_STATUS_GUILD is not None:
            if self.guild.id == COG_CONFIG.PLAYING_STATUS_GUILD.id:
                await self.bot.change_presence(activity=discord.Activity(
                    name=self.current_track.status_information, type=discord.ActivityType.playing
                ))

        if self.log_channel is not None:
            await self.log_channel.send(**self.current_track.playing_message)

        # Create wavelink object for track
        try:
            await self.player.play(await self.current_track.setup(self.bot))
        except commands.BadArgument:
            await self.toggle_next()

    async def skip(self):
        """Skips the currently playing track"""
        await self.player.stop()

    async def stop(self):
        """Stops this session."""
        self.is_playing = False
        await self.player.stop()

    async def check_listeners(self):
        """Checks if there is anyone listening and pauses / resumes accordingly."""
        if list(self.listeners):
            if self.player.is_paused:
                await self.player.set_pause(False)
                self.not_alone.set()
        elif self.player.is_playing:
            await self.player.set_pause(True)
            self.not_alone.clear()

            # Wait to see if the bot stays alone for it's max timeout duration
            if self.stoppable:
                try:
                    await asyncio.wait_for(self.not_alone.wait(), self.timeout)
                except asyncio.TimeoutError:
                    self.stop()

    async def session_task(self, voice_channel):
        await self.player.connect(voice_channel.id)
        await self.player.set_volume(self.volume)
        await self.toggle_next()
        await self.check_listeners()
