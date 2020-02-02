import discord
from discord.ext import commands, menus


class EmbedPaginator(commands.Paginator, menus.PageSource):

    def __init__(self, embed=None, **options):
        self._embed = embed or discord.Embed()
        self.clear()
        self.prefix = None
        self._count = 0

        self.max_embed_size = options.get('max_embed_size', 5500)
        self.max_description_size = options.get('max_description_size', 2048)
        self.max_field_name_size = options.get('max_field_name_size', 256)
        self.max_field_value_size = options.get('max_field_value_size', 1024)
        self.max_fields = options.get('max_fields', 25)

    def new_page(self):
        self._current_page = self._embed.copy()
        self._current_page.description = ''

    def clear(self):
        self._pages = []
        self.new_page()

    def add_line(self, line='', *, empty=False):

        if len(line) > self.max_description_size:
            raise RuntimeError('Line exceeds maximum size')

        # Close page if too large to add
        if len(self._current_page.description) + len(line) + 1 > self.max_description_size:
            self.close_page()

        if len(self._current_page) + len(line) + 1 > self.max_embed_size:
            self.close_page()

        self._current_page.description += '\n' + line + ('\n' if empty else '')

    def add_field(self, name, value, *, inline=False):

        if len(name) > self.max_field_name_size:
            raise RuntimeError('Field name exceeds maximum size')

        if len(value) > self.max_field_value_size:
            raise RuntimeError('Field value exceeds maximum size')

        if len(self._current_page.fields) == self.max_fields:
            self.close_page()

        if len(self._current_page) + len(name) + len(value) > self.max_embed_size:
            self.close_page()

        self._current_page.add_field(name=name, value=value, inline=inline)

    def update_embed(self, embed):
        self.embed = embed
        self._current_page = discord.Embed.from_dict({**self._current_page.to_dict(), **embed.to_dict()})
        self._pages = [discord.Embed.from_dict({**page.to_dict(), **embed.to_dict()}) for page in self._pages]

    def close_page(self):

        # Add cont if required.
        if len(self._pages) >= 1:
            if self._current_page.author.name:
                self._current_page.set_author(
                    name=self._current_page.author.name + ' Cont.',
                    url=self._current_page.author.url,
                    icon_url=self._current_page.author.icon_url
                )

        self._pages.append(self._current_page)
        self.new_page()

    def is_paginating(self):
        return len(self.pages) > 1

    def get_max_pages(self):
        return len(self.pages)

    async def get_page(self, page_number):
        return self.pages[page_number]

    async def format_page(self, menu, page):
        return page

    def __repr__(self):
        fmt = '<EmbedPaginator>'
        return fmt.format(self)
