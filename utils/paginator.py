from typing import Any, Dict, List, NamedTuple

import discord
from discord.ext import commands, menus


MAX_EMBED_SIZE = 5000
MAX_DESCRIPTION_LENGTH = 2048
MAX_NUM_FIELDS = 25


class EmbedPage(NamedTuple):
    description: List[str]
    fields: List[Dict[str, Any]]


class PaginatorSource(commands.Paginator, menus.PageSource):
    
    def is_paginating(self) -> bool:
        return self.get_max_pages() > 1

    def get_max_pages(self) -> int:
        return len(self._pages) + (self._count != 0) # boolean addition sue me

    async def get_page(self, page_number: int) -> Any:
        return self.pages[page_number]


class EmbedPaginator(discord.Embed, PaginatorSource):
    
    def __init__(self, max_size: int = MAX_EMBED_SIZE, max_description: int = MAX_DESCRIPTION_LENGTH, max_fields: int = MAX_NUM_FIELDS, **kwargs):

        description = kwargs.pop('description', '')
        super().__init__(self, **kwargs)
        super(PaginatorSource).__init__(None, None, max_size)

        self.max_description = max_description
        self.max_fields = max_fields

        for line in description.split('\n'):
            self.add_line(line)

    def clear(self):
        self._current_page = EmbedPage([], [])
        self._description_count = 0
        self._count = 0
        self._pages = []  # type: List[EmbedPage]

    def add_line(self, line: str = '', *, empty: bool = False):
        if len(line) > self.max_description:
            raise RuntimeError(f'Line exceeds maximum description size {self.max_description}')
        
        if self._count + len(line) + empty >= self.max_size or self._description_count + len(line) + empty >= self.max_description:
            self.close_page()

        self._count += len(line) + 1
        self._description_count += len(line) + 1
        self._current_page.description.append(line)

        if empty:
            self._current_page.description.append('')
            self._count += 1
            self._description_count += 1

    @property
    def fields(self) -> List[discord.embeds.EmbedProxy]:
        return [discord.embeds.EmbedProxy(field) for page in self._pages for field in page]

    def add_field(self, *, name: Any, value: Any, inline: bool = False):
        name = str(name)
        value = str(value)

        if len(name) + len(value) > self.max_size:
            raise RuntimeError(f'Field exceeds maximum page size {self.max_size}')
    
        if len(self._current_page.fields) >= self.max_fields:
            self.close_page()

        if self._count + len(name) + len(value) > self.max_size:
            self.close_page()

        self._count += len(name) + len(value)
        self._current_page.fields.append(dict(name=name, value=value, inline=inline))

    def close_page(self):
        self._pages.append(self._current_page)
        self._current_page = EmbedPage([],[])
        self._count = 0
        self._description_count = 0
    
    def _format_page(self, page: EmbedPage):
        embed = super().from_dict(self.to_dict())
        embed.description = '\n'.join(page.description)

        if self._pages.index(page) >= 1:
            ... # TODO: Add cont.?

        for field in page.fields:
            embed.add_field(**field)
        
        return embed

    async def format_page(self, menu: menus.Menu, page: Any) -> Any:
        return page

    @property
    def pages(self) -> List[discord.Embed]:
        if self._count > 0:
            self.close_page()
        
        return [self._format_page(page) for page in self._pages]

    def __repr__(self) -> str:
        return '<EmbedPaginator max_size: {0.max_size}>'.format(self)
