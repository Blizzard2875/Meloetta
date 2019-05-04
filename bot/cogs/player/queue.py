from glob import glob
from random import choice
from typing import Generator, Tuple

import discord

from .track import Track, MP3Track

from bot.config import CONFIG as BOT_CONFIG

COG_CONFIG = BOT_CONFIG.COGS[__name__[:__name__.rindex(".")]]


class Queue:

    def __init__(self, config=None):
        self.config = config or dict()
        self._requests = list()

    @property
    def requests(self) -> Generator[Tuple[Track, discord.User], None, None]:
        for request in self._requests:
            yield request

    def next_track(self) -> Track:
        if self._requests:
            return self._requests.pop(0)[0]

    def add_request(self, track: Track, user: discord.User):
        """Adds a track to the list of requests.

        Args:
            track (Track): The track to add to the requests pool.
            user (discord.User): The user who requested the track.

        """
        self._requests.append((track, user))


class Radio(Queue):

    def __init__(self, config=None):
        super().__init__(config)

        self.playlist_directory = self.config.get(
            'playlist_directory') or COG_CONFIG.DEFAULT_PLAYLIST_DIRECTORY

    def next_track(self) -> Track:
        return super().next_track() or MP3Track(choice(glob(self.playlist_directory + "/*.mp3")))
