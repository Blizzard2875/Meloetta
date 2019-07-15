from typing import Mapping, List, Optional

import discord
from discord.ext import commands


class EmbedPaginator(commands.Paginator):
    prefix = None
    suffix = None

    def __init__(self, embed=None, max_size=6000):
        self.embed = embed or discord.Embed
        self.max_size = max_size

    @property
    def pages(self) -> List[discord.Embed]:
        """Returns the rendered list of pages."""
        # we have more than just the prefix in our current page
        if len(self._current_page) > 1:
            self.close_page()
        return [self.embed(page) for page in self._pages]


class EmbedHelpCommand(commands.DefaultHelpCommand):

    def get_ending_note(self):
        return None

    def _embed(self, description: str) -> discord.Embed:
        return discord.Embed(
            description=description,
            colour=self.context.me.colour
        ).set_author(
            name=f"{self.context.me.name} Help Manual",
            icon_url=self.context.me.avatar_url
        ).set_footer(
            text=super().get_ending_note()
        )

    def __init__(self, **options):
        if options.get('paginator') is None:
            options['paginator'] = EmbedPaginator(embed=self._embed)

        super().__init__(**options)

    def add_indented_commands(self, commands, *, heading, max_size=None):
        if not commands:
            return
        if heading:
            heading = f"__**{heading}**__"

        self.paginator.add_line(heading)
        max_size = max_size or self.get_max_size(commands)

        get_width = discord.utils._string_width
        for command in commands:
            parent = command.full_parent_name
            name = f"**{self.clean_prefix}{command.name if not parent else f'{parent} {command.name}'}**"
            width = max_size - (get_width(name) - len(name))
            entry = '{0}{1:<{width}} {2}'.format(
                self.indent * ' ', name, command.short_doc, width=width)
            self.paginator.add_line(self.shorten_text(entry))

        self.paginator.add_line()

    def get_command_signature(self, command):
        return f"`Syntax : {super().get_command_signature(command)}`"

    async def send_pages(self):
        destination = self.get_destination()
        for page in self.paginator.pages:
            await destination.send(embed=page)
