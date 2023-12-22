import discord
import aiosqlite
import yaml

from discord.ext import commands


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class HelpPaginator(discord.ui.View):
    def __init__(self, help_command, commands, *args, **kwargs):
        super().__init__(*args, **kwargs, timeout=60)
        self.help_command = help_command
        self.commands = commands
        self.current_page = 0
        self.max_page = len(commands) // 8

        self.add_item(
            discord.ui.Button(
                label="Previous", style=discord.ButtonStyle.grey, custom_id="previous"
            )
        )
        self.add_item(
            discord.ui.Button(
                label="Next", style=discord.ButtonStyle.grey, custom_id="next"
            )
        )

        self.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.grey,
                emoji="⏪",
                custom_id="go_to_beginning",
            )
        )
        self.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.grey,
                emoji="⏩",
                custom_id="go_to_end",
            )
        )

        self.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="Close",
                emoji="🗑️",
                custom_id="close_help_command",
            )
        )

        self.children[0].callback = self.previous_page
        self.children[1].callback = self.next_page
        self.children[2].callback = self.go_to_beginning
        self.children[3].callback = self.go_to_end
        self.children[4].callback = self.close_help_command

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    async def go_to_beginning(self, interaction: discord.Interaction):
        self.current_page = 0
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def go_to_end(self, interaction: discord.Interaction):
        self.current_page = self.max_page
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def previous_page(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
        else:
            self.current_page = self.max_page
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def next_page(self, interaction: discord.Interaction):
        if self.current_page < self.max_page:
            self.current_page += 1
        else:
            self.current_page = 0
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def close_help_command(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=None)
        await interaction.message.delete()

    def create_embed(self):
        embed = discord.Embed(
            color=config["COLORS"]["DEFAULT"],
        )
        page_commands = self.commands[
            self.current_page * 8 : (self.current_page + 1) * 8
        ]

        for command in page_commands:
            full_name = (
                f"/{command.parent.name} {command.name}"
                if command.parent
                else command.name
            )

            description_lines = [command.description or "No description"]

            if isinstance(command, discord.commands.SlashCommand):
                for option in command.options:
                    brackets = "<{}>" if option.required else "[{}]"
                    param_desc = f"`{brackets.format(option.name)}`: _{option.description or 'No description'}_"
                    description_lines.append(param_desc)

            full_description = "\n".join(description_lines)

            embed.add_field(name=full_name, value=full_description, inline=False)

            embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_page + 1}")

        return embed


class Help(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.db_path = "kino.db"
        self.bot.loop.create_task(self.setup_db())

    async def setup_db(self):
        self.conn = await aiosqlite.connect(self.db_path)

    @discord.slash_command(
        name="help",
        description="Shows all commands.",
    )
    async def _help(self, ctx: discord.ApplicationContext):
        skip_cogs = [
            "developer",
            "error_handler",
        ]

        commands = [
            cmd
            for cmd in self.bot.walk_application_commands()
            if isinstance(cmd, discord.commands.SlashCommand)
            and (cmd.parent is None or isinstance(cmd, discord.commands.SlashCommand))
            and (cmd.cog is None or cmd.cog.qualified_name.lower() not in skip_cogs)
        ]

        paginator = HelpPaginator(self._help, commands)
        embed = paginator.create_embed()
        await ctx.respond(embed=embed, view=paginator)


def setup(bot_: discord.Bot):
    bot_.add_cog(Help(bot_))
