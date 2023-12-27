import discord
import aiosqlite
import yaml

from discord.ext import commands
from helpers.constants import commands_with_tips


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
        self.max_page = len(commands) // 8 + 1

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
                custom_id="close_help_command",
            )
        )

        self.children[0].callback = self.previous_page
        self.children[1].callback = self.next_page
        self.children[2].callback = self.go_to_beginning
        self.children[3].callback = self.go_to_end
        self.children[4].callback = self.close_help_command

    def create_embed(self):
        if self.current_page == 0:
            return self.create_introductory_embed()
        else:
            return self.create_command_embed()

    def create_introductory_embed(self):
        embed = discord.Embed(
            title="📘 Help Command Guide",
            description="Learn how to navigate and utilize the bot's commands for a seamless experience!",
            color=config["COLORS"]["DEFAULT"],
        )
        embed.add_field(
            name="🔢 Navigating Pages",
            value="Use the **Next** and **Previous** buttons below to move between pages. You can jump to the first or last page with ⏪ and ⏩ respectively.",
            inline=False,
        )
        embed.add_field(
            name="🔍 Understanding Commands",
            value="Commands are listed with details. Required arguments are in **<angle brackets>**, optional ones in **[square brackets]**. Parameters describe what should be entered.",
            inline=False,
        )
        embed.add_field(
            name="🌟 Premium Commands",
            value=f"Look for the {config['EMOJIS']['PREMIUM']} emoji for premium commands. They might need special permissions or subscriptions.",
            inline=False,
        )
        embed.add_field(
            name="📄 Example Usage",
            value="Each command comes with an example usage to guide you on how to use it properly. Pay attention to the syntax and ordering of arguments!",
            inline=False,
        )
        embed.add_field(
            name="💡 Tips",
            value="Use the bot in a specific channel or in DMs to avoid clutter. Remember, you can always type `/` and the command name to see interactive options!",
            inline=False,
        )
        embed.add_field(
            name="❓ Getting More Help",
            value="Need more specific help with a command? Use `/help [command]` to get detailed instructions about a particular command.",
            inline=False,
        )
        embed.add_field(
            name="🔐 Privacy & Permissions",
            value="Your privacy is important. The bot operates under strict data handling policies. Ensure you have the necessary permissions in your server to use commands.",
            inline=False,
        )
        embed.set_thumbnail(url="https://files.catbox.moe/vx7txo.png")
        return embed

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
        if embed is None or embed.fields == []:
            embed = discord.Embed(description="No commands available!")
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

    def create_command_embed(self):
        embed = discord.Embed(
            color=config["COLORS"]["DEFAULT"],
        )

        start_index = (self.current_page - 1) * 8
        end_index = start_index + 8

        page_commands = self.commands[start_index:end_index]

        if not page_commands:
            embed.description = "No more commands to display!"

        for command in page_commands:
            full_name = (
                f"/{command.parent.name} {command.name}"
                if command.parent
                else command.name
            )
            premium = ""
            if full_name in self.help_command.cog.premium_commands:
                premium = " " + config["EMOJIS"]["PREMIUM"]

            description_lines = [command.description or "No description"]

            if isinstance(command, discord.commands.SlashCommand):
                for option in command.options:
                    brackets = "<{}>" if option.required else "[{}]"
                    param_desc = f"`{brackets.format(option.name)}`: _{option.description or 'No description'}_"
                    description_lines.append(param_desc)

            full_description = "\n".join(description_lines)

            embed.add_field(
                name=full_name + premium, value=full_description, inline=False
            )

        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_page + 1}")

        return embed


class Help(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.db_path = "kino.db"
        self.premium_commands = set()
        self.bot.loop.create_task(self.setup_db())

    async def setup_db(self):
        self.conn = await aiosqlite.connect(self.db_path)
        async with self.conn.execute(
            "SELECT command_name FROM premium_commands"
        ) as cursor:
            premium_commands = await cursor.fetchall()
            self.premium_commands = {cmd[0] for cmd in premium_commands}

    async def show_specific_command_help(self, ctx, command):
        premium = ""
        if f"/{command.qualified_name}" in self.premium_commands:
            premium = " " + config["EMOJIS"]["PREMIUM"]

        embed = discord.Embed(
            title=f"`{command.qualified_name}`{premium}",
            description=command.description or "No description available.",
            color=config["COLORS"]["DEFAULT"],
        )

        if isinstance(command, discord.commands.SlashCommand):
            embed.add_field(
                name="Usage",
                value=f"```/{command.qualified_name} { ' '.join([f'<{opt.name}>' for opt in command.options]) }```",
                inline=False,
            )
            for option in command.options:
                embed.add_field(
                    name=option.name,
                    value=f"{option.description}\nRequired: {'<:checkmark:1189457685171687538>' if option.required else '<:letterx:1189490617961697380>'}",
                    inline=False,
                )

        command_path = f"/{command.full_parent_name} {command.name}".strip()

        print(command_path)

        if command_path in commands_with_tips:
            tips_data = commands_with_tips[command_path]

            tips_button = discord.ui.Button(
                emoji="🔍", style=discord.ButtonStyle.secondary
            )

            async def tips_button_callback(interaction: discord.Interaction):
                await interaction.response.send_message(
                    f"**Extra tips for `{command_path}`**\n\n{tips_data['description']}\n\n**Example**\n{tips_data['example']}\n{tips_data['image']}",
                    ephemeral=True,
                )

            tips_button.callback = tips_button_callback

            view = discord.ui.View()
            view.add_item(tips_button)

            await ctx.respond(embed=embed, view=view)
        else:
            await ctx.respond(embed=embed)

    @discord.slash_command(
        name="help",
        description="Shows all commands.",
    )
    async def _help(
        self,
        ctx: discord.ApplicationContext,
        command_name: discord.Option(
            str, description="The command to get help for.", required=False
        ),
    ):
        if command_name:
            path_parts = command_name.strip().split()
            command = None
            commands = list(self.bot.walk_application_commands())

            for part in path_parts:
                command = discord.utils.find(
                    lambda c: c.name == part and c.parent == command, commands
                )

                if command is None:
                    await ctx.respond(
                        f"Command **{command_name}** not found.", ephemeral=True
                    )
                    return

            if command:
                await self.show_specific_command_help(ctx, command)
        else:
            skip_cogs = [
                "developer",
                "error_handler",
            ]

            commands = [
                cmd
                for cmd in self.bot.walk_application_commands()
                if isinstance(cmd, discord.commands.SlashCommand)
                and (
                    cmd.parent is None or isinstance(cmd, discord.commands.SlashCommand)
                )
                and (cmd.cog is None or cmd.cog.qualified_name.lower() not in skip_cogs)
            ]

            paginator = HelpPaginator(self._help, commands)
            embed = paginator.create_embed()
            await ctx.respond(embed=embed, view=paginator)


def setup(bot_: discord.Bot):
    bot_.add_cog(Help(bot_))
