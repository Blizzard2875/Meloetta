from typing import List

import discord

import wavelink

from bot import Context
from utils.abc import BaseChoiceMenu


class YoutubeSearchResultsMenu(BaseChoiceMenu):

    def __init__(self, query: str, options: List[wavelink.Track]) -> None:
        self.query = query
        super().__init__(options)

    async def send_initial_message(self, ctx: Context, channel: discord.TextChannel) -> discord.Message:

        embed = discord.Embed(
            colour=discord.Colour.red(),
            title=f'Results for search: {self.query}'
        )

        for i, track in enumerate(self.options, 1):
            length = track.length // 1000
            embed.add_field(
                name=f'{i}\ufe0f\N{COMBINING ENCLOSING KEYCAP} {track.title}',
                value=f'[link]({track.uri}) ({length//60:02d}:{length%60:02d}) - {track.author}',
                inline=False
            )

        return await channel.send(embed=embed)
