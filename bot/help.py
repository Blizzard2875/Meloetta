import discord
from discord.ext import commands, menus

from bot.utils.paginator import EmbedPaginator


class EmbedMenuHelpCommand(commands.DefaultHelpCommand):

    def __init__(self, **options):
        super().__init__(**options, paginator=options.pop('paginator', EmbedPaginator(max_fields=8)))

    def get_ending_note(self):
        return None

    async def send_pages(self):
        destination = self.get_destination()

        self.paginator.update_embed(
            discord.Embed(
                colour=self.context.me.colour
            ).set_author(
                name=f'{self.context.me} Help Manual',
                icon_url=self.context.me.avatar_url
            ).set_footer(
                text=super().get_ending_note()
            )
        )

        try:
            menu = menus.MenuPages(self.paginator, clear_reactions_after=True, check_embeds=True)
            await menu.start(self.context, channel=destination)

        except discord.Forbidden:
            await self.context.send(
                embed=discord.Embed(
                    title='Error with command: help',
                    description='I was not able to Direct Message you.\nDo you have direct messages disabled?'
                )
            )

    def get_command_signature(self, command):
        return f'Syntax: `{super().get_command_signature(command)}`'

    def add_indented_commands(self, commands, *, heading, max_size=None):
        if not commands:
            return

        max_size = max_size or self.get_max_size(commands)

        lines = []
        get_width = discord.utils._string_width
        for command in commands:
            name = command.name
            width = max_size - (get_width(name) - len(name))
            entry = '{0}**{1:<{width}}**: {2}'.format(
                self.indent * ' ', name, command.short_doc, width=width)
            lines.append(self.shorten_text(entry))

        self.paginator.add_field(
            name=heading,
            value='\n'.join(lines)
        )
