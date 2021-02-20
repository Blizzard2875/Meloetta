from typing import List

import discord

import wavelink
from wavelink.player import Track

from bot import Context
from utils.abc import BaseChoiceMenu


class YoutubeSearchResultsMenu(BaseChoiceMenu):

    def __init__(self, query: str, options: List[wavelink.Track]) -> None:
        self.query = query
        super().__init__(options)

    async def send_initial_message(self, ctx: Context, channel: discord.TextChannel):

        embed = discord.Embed(
            color=discord.Colour.red(),
            title=f'Results for search: {self.query}'
        )

        for i, track in enumerate(self.options, 1):
            length = track.length // 1000
            embed.add_field(
                name=f"{i}\ufe0f\N{COMBINING ENCLOSING KEYCAP} {track.title}",
                value=f"[link]({track.uri}) ({length//60*1000:02d}:{length//1000%60}) - {track.author}",
                inline=False
            )

        await channel.send(embed=embed)
