from pathlib import Path
from random import choice
from typing import Generator, Tuple

import discord

from .track import Track, MP3Track

from bot.config import CONFIG as BOT_CONFIG

COG_CONFIG = BOT_CONFIG.COGS[__name__[:__name__.rindex(".")]]


class Queue:

    def __init__(self, config=None):
        self.config = config or dict()
        self.requests = list()

    def next_track(self) -> Track:
        if self.requests:
            return self.requests.pop(0)

    def add_request(self, track: Track):
        """Adds a track to the list of requests.

        Args:
            track (Track): The track to add to the requests pool.
            user (discord.User): The user who requested the track.

        """
        self.requests.append(track)


class Radio(Queue):

    def __init__(self, config=None):
        super().__init__(config)

        self.playlist_directory = self.config.get(
            'playlist_directory') or COG_CONFIG.DEFAULT_PLAYLIST_DIRECTORY

    def next_track(self) -> Track:
        return super().next_track() or MP3Track(choice(list(Path(self.playlist_directory).glob("**/*.mp3"))))
