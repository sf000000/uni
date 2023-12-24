import discord
import aiosqlite
import yaml
import aiohttp

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

    def add_chess_ratings(self, embed, player_data):
        game_types = ["blitz", "bullet", "rapid"]
        for game_type in game_types:
            key = f"chess_{game_type}"
            if key in player_data:
                last_rating = player_data[key]["last"]["rating"]
                best_rating = player_data[key]["best"]["rating"]
                record = player_data[key]["record"]
                record_str = f"{record['win']}W / {record['loss']}L / {record['draw']}D"

                embed.add_field(
                    name=f"⚡ {game_type.capitalize()} Rating",
                    value=f"Current: {last_rating} | Best: {best_rating}",
                    inline=True,
                )
                embed.add_field(
                    name=f"📊 {game_type.capitalize()} Record",
                    value=record_str,
                    inline=True,
                )

    def add_tactics_ratings(self, embed, player_data):
        if "tactics" in player_data:
            highest = player_data["tactics"]["highest"]["rating"]
            lowest = player_data["tactics"]["lowest"]["rating"]
            embed.add_field(
                name="🧠 Tactics",
                value=f"Highest: {highest} | Lowest: {lowest}",
                inline=False,
            )

    def add_puzzle_rush(self, embed, player_data):
        if "puzzle_rush" in player_data:
            best_score = player_data["puzzle_rush"]["best"]["score"]
            total_attempts = player_data["puzzle_rush"]["best"]["total_attempts"]
            embed.add_field(
                name="🧩 Puzzle Rush",
                value=f"Best Score: {best_score} | Attempts: {total_attempts}",
                inline=False,
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

    _chess = discord.commands.SlashCommandGroup(
        name="chess", description="Chess commands."
    )

    @_chess.command(
        name="play",
        description="Play a game of Chess!",
    )
    async def chess(self, ctx: discord.ApplicationContext, opponent: discord.Member):
        await Chess(
            white=ctx.author,
            black=opponent,
        ).start(ctx, embed_color=config["COLORS"]["DEFAULT"])

    @_chess.command(
        name="whois", description="Get information about a chess player on Chess.com."
    )
    async def chess_whois(
        self,
        ctx: discord.ApplicationContext,
        username: discord.Option(
            str, description="The username of the player to get information about."
        ),
    ):
        await ctx.defer()

        try:
            async with aiohttp.ClientSession() as session, session.get(
                f"https://api.chess.com/pub/player/{username}"
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

            embed = discord.Embed(color=config["COLORS"]["DEFAULT"])
            embed.set_thumbnail(url=data["avatar"])

            fields = [
                ("ID", data["player_id"]),
                ("Name", data["name"]),
                ("Country", data["country"].split("/")[-1]),
                ("Joined", f"<t:{data['joined']}:R>"),
                ("Status", data["status"]),
                ("Is Streamer", data["is_streamer"]),
                ("Verified", data["verified"]),
                ("Followers", data["followers"]),
                ("Last Online", f"<t:{data['last_online']}:R>"),
            ]

            for name, value in fields:
                embed.add_field(name=name, value=value)

            await ctx.respond(embed=embed)
        except Exception as e:
            await ctx.respond(
                embed=discord.Embed(
                    description="I couldn't find a player with that username.",
                    color=config["COLORS"]["ERROR"],
                )
            )

    @_chess.command(
        name="stats", description="Get stats about a chess player on Chess.com."
    )
    async def chess_stats(
        self,
        ctx: discord.ApplicationContext,
        username: discord.Option(
            str, description="The username of the player to get stats for."
        ),
    ):
        await ctx.defer()
        try:
            async with aiohttp.ClientSession() as session, session.get(
                f"https://api.chess.com/pub/player/{username}/stats"
            ) as resp:
                resp.raise_for_status()
                player_data = await resp.json()

            embed = discord.Embed(color=config["COLORS"]["DEFAULT"])
            self.add_chess_ratings(embed, player_data)
            self.add_tactics_ratings(embed, player_data)
            self.add_puzzle_rush(embed, player_data)

            await ctx.respond(embed=embed)

        except aiohttp.ClientError as e:
            await ctx.respond(
                embed=discord.Embed(
                    description=f"HTTP Request failed: {e}",
                    color=config["COLORS"]["ERROR"],
                )
            )
        except KeyError as e:
            await ctx.respond(
                embed=discord.Embed(
                    description=f"Missing data: {e}", color=config["COLORS"]["ERROR"]
                )
            )

        except Exception as e:
            await ctx.respond(
                embed=discord.Embed(
                    description="I couldn't find a player with that username.",
                    color=config["COLORS"]["ERROR"],
                )
            )

    @_chess.command(
        name="daily",
        description="Get the daily chess puzzle.",
    )
    async def chess_daily(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        try:
            async with aiohttp.ClientSession() as session, session.get(
                "https://api.chess.com/pub/puzzle"
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

            embed = discord.Embed(
                description=f"🧩 {data['title']}",
                color=config["COLORS"]["DEFAULT"],
            )
            embed.set_image(url=data["image"])
            embed.add_field(name="Published", value=f"<t:{data['publish_time']}:R>")

            play_button = discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Play",
                url=data["url"],
            )
            view = discord.ui.View()
            view.add_item(play_button)

            await ctx.respond(embed=embed, view=view)
        except Exception as e:
            await ctx.respond(
                embed=discord.Embed(
                    description="I couldn't get the daily puzzle.",
                    color=config["COLORS"]["ERROR"],
                )
            )

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
