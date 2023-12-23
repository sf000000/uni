import discord
import aiosqlite
import yaml

from discord.ext import commands
from discord_games import *


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class Games(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.db_path = "kino.db"
        self.bot.loop.create_task(self.setup_db())

    async def setup_db(self):
        self.conn = await aiosqlite.connect(self.db_path)

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

    @discord.slash_command(
        name="wordle",
        description="Play a game of Wordle!",
    )
    async def wordle(self, ctx: discord.ApplicationContext):
        await Wordle().start(ctx, embed_color=config["COLORS"]["DEFAULT"])

    @discord.slash_command(
        name="hangman",
        description="Play a game of Hangman!",
    )
    async def hangman(self, ctx: discord.ApplicationContext):
        await Hangman().start(ctx, embed_color=config["COLORS"]["DEFAULT"])

    @discord.slash_command(
        name="tictactoe",
        description="Play a game of Tic Tac Toe!",
    )
    async def tictactoe(
        self, ctx: discord.ApplicationContext, opponent: discord.Member
    ):
        await Tictactoe(
            cross=ctx.author,
            circle=opponent,
        ).start(ctx, embed_color=config["COLORS"]["DEFAULT"])

    @discord.slash_command(
        name="connectfour",
        description="Play a game of Connect Four!",
    )
    async def connectfour(
        self, ctx: discord.ApplicationContext, opponent: discord.Member
    ):
        await ConnectFour(
            red=ctx.author,
            blue=opponent,
        ).start(ctx, embed_color=config["COLORS"]["DEFAULT"])

    @discord.slash_command(
        name="chess",
        description="Play a game of Chess!",
    )
    async def chess(self, ctx: discord.ApplicationContext, opponent: discord.Member):
        await Chess(
            white=ctx.author,
            black=opponent,
        ).start(ctx, embed_color=config["COLORS"]["DEFAULT"])

    @discord.slash_command(
        name="akinator",
        description="Play a game of Akinator!",
    )
    async def akinator(self, ctx: discord.ApplicationContext):
        await Akinator().start(ctx, embed_color=config["COLORS"]["DEFAULT"])

    @discord.slash_command(
        name="rps",
        description="Play a game of Rock Paper Scissors!",
    )
    async def rps(self, ctx: discord.ApplicationContext):
        await RockPaperScissors().start(ctx, embed_color=config["COLORS"]["DEFAULT"])

    @discord.slash_command(
        name="reactiongame",
        description="Play a game of Reaction Game!",
    )
    async def reactiongame(self, ctx: discord.ApplicationContext):
        await ReactionGame().start(ctx, embed_color=config["COLORS"]["DEFAULT"])


def setup(bot_: discord.Bot):
    bot_.add_cog(Games(bot_))
