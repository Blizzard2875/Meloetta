from pathlib import Path
from random import choice

from typing import Optional

import wavelink

from .track import Track, MP3Track

from bot.config import config as BOT_CONFIG
COG_CONFIG = BOT_CONFIG.EXTENSIONS[__name__[:__name__.rindex('.')]]


class Queue:

    def __init__(self, config=None):
        self.config = config or dict()
        self.requests = list()

    async def next_track(self, client) -> Optional[Track]:
        if self.requests:
            return self.requests.pop(0)
        return None

    def add_request(self, track: Track, *, at_start: bool = False):
        """Adds a track to the list of requests.

        Args:
            track (Track): The track to add to the requests pool.
            user (discord.User): The user who requested the track.
        Kwargs:
            at_start (bool): Determines wether the track should be added to the start of the queue.

        """
        if at_start:
            self.requests.insert(0, track)
        else:
            self.requests.append(track)


class Radio(Queue):
    def __init__(self, config=None):
        super().__init__(config)

        self.playlist_directory = self.config.get(
            'playlist_directory') or COG_CONFIG.DEFAULT_PLAYLIST_DIRECTORY
        self.next_radio_track = None

    async def get_radio_track(self, client):
        try:
            directory = Path(self.playlist_directory)
            tracks = list(directory.glob('**/*.mp3'))
            track = MP3Track(str(choice(tracks)))
            await track.setup(client)
        except wavelink.LavalinkException:
            return await self.setup_next_radio_track(client)
        return track

    async def setup_next_radio_track(self, client):
        self.next_radio_track = await self.get_radio_track(client)

    async def next_track(self, client) -> Track:
        next_track = await super().next_track(client)
        if next_track is None:
            if self.next_radio_track is None:
                await self.setup_next_radio_track(client)
            next_track = self.next_radio_track
            client.loop.create_task(self.setup_next_radio_track(client))
        return next_track
