import asyncio
import random

from typing import Dict, List, Set, Type, TypeVar

import discord
from discord.enums import Enum

import wavelink
from wavelink.player import Track


class VoteType(Enum):
    PAUSE = 0
    RESUME = 1
    SKIP = 2
    REPEAT = 3
    SHUFFLE = 4
    STOP = 5


T = TypeVar('T', bound='Request')


class Request(wavelink.Track):

    def __init__(self, id, info, requester: discord.Member, query: str = None):
        self.requester = requester
        super().__init__(id, info, query)

    @classmethod
    def from_track(cls: Type[T], track: wavelink.Track, requester: discord.Member) -> T:
        return cls(track.id, track.info, requester, track.query)


class Player(wavelink.Player):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._queue = asyncio.Queue()
        self._repeat = False

        self._votes: Dict[VoteType, Set[discord.Member]] = {
            vote_type: set() for vote_type in VoteType}

        # Player state information
        self._listeners = []

        self.controls = {
            VoteType.PAUSE: self.pause,
            VoteType.RESUME: self.resume,
            VoteType.SKIP: self.skip,
            VoteType.REPEAT: self.repeat,
            VoteType.SHUFFLE: self.shuffle,
            VoteType.STOP: self.stop,
        }

    @property
    def listeners(self) -> List[discord.Member]:
        return self._listeners

    @property
    def guild(self) -> discord.Guild:
        return self.bot.get_guild(self.guild_id)

    @property
    def channel(self) -> discord.VoiceChannel:
        return self.bot.get_channel(self.channel_id)

    async def update_listeners(self):
        self._listeners = await self.guild.query_members(user_ids=[user_id for user_id in self.channel.voice_states])

    def vote_has_passed(self, vote_type: VoteType) -> bool:
        return len(self._votes[vote_type]) > len(self.listeners) // 2 + 1

    async def request(self, track: Track, requester: discord.Member):
        await self._queue.put(Request(track, requester))

    async def next(self):
        if self.is_playing:
            return

        try:
            track = await self._queue.get()
        except asyncio.TimeoutError:
            return await self.stop()

        await self.play(track)

    async def play(self, track: Track):
        for vote_type in (VoteType.PAUSE, VoteType.RESUME, VoteType.SKIP, VoteType.REPEAT):
            self._votes[vote_type].clear()

        await super().play(track)

    async def pause(self):
        self._votes[VoteType.PAUSE].clear()
        await self.set_pause(True)

    async def resume(self):
        self._votes[VoteType.RESUME].clear()
        await self.set_pause(False)

    async def skip(self):
        self._votes[VoteType.SKIP].clear()
        await super().stop()

    async def repeat(self):
        self._votes[VoteType.REPEAT].clear()
        self._repeat = True

    async def shuffle(self):
        self._votes[VoteType.SHUFFLE].clear()
        random.shuffle(self._queue._queue)

    async def stop(self):
        self._votes[VoteType.STOP].clear()
        await self.destroy()

    async def vote(self, vote_type: VoteType, member: discord.Member):
        self._votes[VoteType.STOP].add(member)
        if not self.vote_has_passed(vote_type):
            return

        await self.controls[vote_type]()
