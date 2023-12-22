import discord
import aiosqlite
import yaml

from discord.ext import commands


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class Twitch(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.db_path = "kino.db"
        self.bot.loop.create_task(self.setup_db())

    async def setup_db(self):
        self.conn = await aiosqlite.connect(self.db_path)

    async def channel_autocomplete(self, ctx: discord.ApplicationContext, string: str):
        channels = ctx.guild.channels
        return [
            channel for channel in channels if string.lower() in channel.name.lower()
        ]

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        command_name = ctx.command.name

        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM disabled_commands WHERE command = ?", (command_name,)
            )
            if await cur.fetchone():
                embed = discord.Embed(
                    title="Command Disabled",
                    description=f"The command `{command_name}` is currently disabled in this guild.",
                    color=discord.Color.red(),
                )
                embed.set_footer(text="This message will be deleted in 10 seconds.")
                embed.set_author(
                    name=self.bot.user.display_name, icon_url=self.bot.user.avatar.url
                )
                await ctx.respond(embed=embed, ephemeral=True, delete_after=10)
                raise commands.CommandInvokeError(
                    f"Command `{command_name}` is disabled."
                )

    _twitch = discord.commands.SlashCommandGroup(
        name="twitch", description="Twitch related commands."
    )

    @_twitch.command(
        name="enable",
        description="Enables Twitch notifications",
    )
    async def _enable(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.Option(
            name="channel",
            description="The channel to send notifications to.",
            required=True,
            autocomplete=channel_autocomplete,
        ),
    ):
        ...

    @_twitch.command(
        name="disable",
        description="Disables Twitch notifications",
    )
    async def _disable(
        self,
        ctx: discord.ApplicationContext,
    ):
        ...

    @_twitch.command(
        name="add",
        description="Adds a Twitch channel to the notification list.",
    )
    async def _add(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.Option(
            name="channel",
            description="The channel to add to the notification list.",
            required=True,
        ),
    ):
        ...


def setup(bot_: discord.Bot):
    bot_.add_cog(Twitch(bot_))
