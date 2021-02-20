from typing import List, Optional
from unicodedata import name

import discord
from discord.ext import commands, menus

from utils.paginator import EmbedPaginator


SPACE = ' '
MAX_FIELDS = 8


class EmbedHelpCommand(commands.DefaultHelpCommand):
    paginator: EmbedPaginator

    def __init__(self, **options):
        options.update({
            'paginator': EmbedPaginator(max_fields=options.pop('max_fields', MAX_FIELDS))
        })
        super().__init__(**options)

    def format_pages(self):
        self.paginator.colour = self.context.me.colour
        self.paginator.set_author(
            name=f'{self.context.me} Help Manual',
            icon_url=self.context.me.avatar_url,
        )
        self.paginator.set_footer(
            text=self.get_ending_note()
        )

    async def send_pages(self):
        destination = self.get_destination()

        self.format_pages()

        try:
            for page in self.paginator.pages:
                await destination.send(embed=page)
        except discord.HTTPException:
            raise commands.BadArgument(
                'I was not able to send command help.')  # TODO: Better type?

    def get_command_signature(self, command: commands.Command) -> str:
        return f'Syntax: `{super().get_command_signature(command)}`'

    def add_indented_commands(self, commands: List[commands.Command], *, heading: str, max_size: Optional[int] = None):
        if not commands:
            return

        max_size = max_size or self.get_max_size(commands)

        lines = []
        get_width = discord.utils._string_width
        for command in commands:
            width = max_size - (get_width(command.name) - len(command.name))
            lines.append(self.shorten_text(
                f'{SPACE * self.indent}**{command.name:<{width}}**: {command.short_doc}'))

        self.paginator.add_field(
            name=heading,
            value='\n'.join(lines)
        )


class EmbedMenuHelpCommand(EmbedHelpCommand):
    async def send_pages(self):
        self.format_pages()

        try:
            menu = menus.MenuPages(
                self.paginator, clear_reactions_after=True, check_embeds=True, delete_message_after=True)
            await menu.start(self.context, channel=self.get_destination())
        except menus.MenuError:
            raise commands.BadArgument(
                'I was not able to send command help.')  # TODO: Better type?
