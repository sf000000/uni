import discord
import aiosqlite
import yaml
import uwuify
import aiohttp
import os

from discord.ext import commands


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class Misc(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.db_path = "kino.db"
        self.bot.loop.create_task(self.setup_db())

    async def setup_db(self):
        self.conn = await aiosqlite.connect(self.db_path)

    async def channel_autocomplete(self, ctx: discord.ApplicationContext):
        return [
            discord.OptionChoice(name=channel.name, value=str(channel.id))
            for channel in ctx.guild.text_channels
        ]

    async def role_autocomplete(self, ctx: discord.ApplicationContext):
        return [
            discord.OptionChoice(name=role.name, value=str(role.id))
            for role in ctx.guild.roles
        ]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT message FROM afk WHERE user_id = ?", (message.author.id,)
            )
            afk_message = await cur.fetchone()
            if afk_message:
                await message.channel.send(
                    f"Welcome back {message.author.mention}! AFK status removed.",
                    delete_after=5,
                )
                await cur.execute(
                    "DELETE FROM afk WHERE user_id = ?", (message.author.id,)
                )

            if message.mentions:
                for user in message.mentions:
                    await cur.execute(
                        "SELECT message FROM afk WHERE user_id = ?", (user.id,)
                    )
                    afk_message = await cur.fetchone()
                    if afk_message:
                        embed = discord.Embed(
                            description=f"Hello {message.author.mention}, {user.mention} is currently AFK.",
                            color=config["COLORS"]["INFO"],
                        )
                        embed.add_field(
                            name="AFK Message", value=afk_message[0], inline=False
                        )
                        await message.channel.send(embed=embed, delete_after=5)
        await self.conn.commit()

    @discord.slash_command(
        name="uwu",
        description="Uwuify text",
    )
    async def uwuify(
        self,
        ctx: discord.ApplicationContext,
        text=discord.Option(str, "Text to uwuify", required=True),
    ):
        await ctx.respond(uwuify.uwu(text, flags=uwuify.SMILEY))

    @discord.slash_command(
        name="quickpoll",
        description="Add up/down arrow to message initiating a poll",
    )
    async def quickpoll(
        self,
        ctx: discord.ApplicationContext,
        message_id=discord.Option(str, "Message ID to add emojis to.", required=True),
        emoji_type=discord.Option(
            str,
            "Emoji type to add to message.",
            required=True,
            choices=[
                discord.OptionChoice(name="Up/Down Arrow", value="updown"),
                discord.OptionChoice(name="Green Check/Red X", value="yesno"),
                discord.OptionChoice(name="Thumbs Up/Down", value="thumbs"),
            ],
        ),
    ):
        emoji_pairs = { 
            "updown": ("⬆️", "⬇️"),
            "yesno": ("✅", "❌"),
            "thumbs": ("👍", "👎") 
        }  # fmt: skip

        message = await ctx.channel.fetch_message(int(message_id))
        emojis = emoji_pairs.get(emoji_type, ())
        for emoji in emojis:
            await message.add_reaction(emoji)

        await ctx.respond("Done.", ephemeral=True, delete_after=5)

    @discord.slash_command(
        name="afk",
        description="Set an AFK status for when you are mentioned",
    )
    async def _afk(
        self,
        ctx: discord.ApplicationContext,
        message=discord.Option(
            str, "Message to display when you are mentioned", required=True
        ),
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "CREATE TABLE IF NOT EXISTS afk (user_id INTEGER PRIMARY KEY, message TEXT)"
            )
            await cur.execute("SELECT 1 FROM afk WHERE user_id = ?", (ctx.author.id,))
            if await cur.fetchone():
                await cur.execute("DELETE FROM afk WHERE user_id = ?", (ctx.author.id,))
                await ctx.respond("AFK status removed.", ephemeral=True)
            else:
                await cur.execute(
                    "INSERT INTO afk (user_id, message) VALUES (?, ?)",
                    (ctx.author.id, message),
                )
                await ctx.respond("AFK status set.", ephemeral=True)
        await self.conn.commit()

    async def popular_movies_autocomplete(self, ctx: discord.ApplicationContext):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.themoviedb.org/3/discover/movie",
                params={
                    "language": "en-US",
                    "page": "1",
                    "sort_by": "popularity.desc",
                },
                headers={
                    "Authorization": f"Bearer {config['TMDB_API_KEY']}",
                    "accept": "application/json",
                },
            ) as response:
                data = await response.json()

        return [
            discord.OptionChoice(
                name="Popular Movies Right Now", value="0"
            ),  # Non-selectable placeholder
            *[
                discord.OptionChoice(name=movie["title"], value=str(movie["title"]))
                for movie in data["results"]
            ],
        ]

    @discord.slash_command(
        name="movie",
        description="Get a link to watch a movie 🏴‍☠🦜",
    )
    async def _movie(
        self,
        ctx: discord.ApplicationContext,
        movie=discord.Option(
            str,
            "Movie to watch",
            required=True,
            autocomplete=popular_movies_autocomplete,
        ),
        include_adult=discord.Option(
            bool, "Include adult movies (True by default)", required=False, default=True
        ),
    ):
        if movie == "0":
            return await ctx.respond(
                "Um, you selected the placeholder option. Please select a movie.",
                ephemeral=True,
            )

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.themoviedb.org/3/search/movie",
                params={
                    "query": movie,
                    "language": "en-US",
                    "include_adult": str(include_adult).lower(),
                },
                headers={
                    "Authorization": f"Bearer {config['TMDB_API_KEY']}",
                    "accept": "application/json",
                },
            ) as response:
                data = await response.json()

        if not data["results"]:
            return await ctx.respond("No results found.", ephemeral=True)

        genre_dict = {
            "Action": 28,
            "Adventure": 12,
            "Animation": 16,
            "Comedy": 35,
            "Crime": 80,
            "Documentary": 99,
            "Drama": 18,
            "Family": 10751,
            "Fantasy": 14,
            "History": 36,
            "Horror": 27,
            "Music": 10402,
            "Mystery": 9648,
            "Romance": 10749,
            "Science Fiction": 878,
            "TV Movie": 10770,
            "Thriller": 53,
            "War": 10752,
            "Western": 37,
        }

        movie = data["results"][0]

        watch_url = f"https://movie-web.app/media/tmdb-movie-{movie['id']}-{movie['title'].replace(' ', '-').lower()}"
        embed = discord.Embed(
            title=movie["title"],
            description=movie["overview"],
            color=config["COLORS"]["SUCCESS"],
        )
        embed.set_thumbnail(
            url=f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
        )

        embed.add_field(
            name="Genres",
            value=", ".join(
                [
                    genre_name
                    for genre_name, genre_id in genre_dict.items()
                    if genre_id in movie["genre_ids"]
                ]
            ),
        )

        embed.add_field(
            name="Vote Average",
            value=f"{round(movie['vote_average'] * 2) / 2} ({movie['vote_count']})",
        )

        watch_button = discord.ui.Button(
            style=discord.ButtonStyle.link, label="Watch", url=watch_url
        )
        view = discord.ui.View()
        view.add_item(watch_button)
        await ctx.respond(embed=embed, view=view)

    @discord.slash_command(
        name="tts",
        description="Sends a .mp3 file of text speech",
    )
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def _tts(
        self,
        ctx: discord.ApplicationContext,
        text=discord.Option(str, "Text to speak", required=True),
        voice=discord.Option(
            str,
            "Voice to speak with",
            required=False,
            choices=[
                discord.OptionChoice(name="Brian", value="Brian"),
                discord.OptionChoice(name="Emma", value="Emma"),
                discord.OptionChoice(name="Ivy", value="Ivy"),
                discord.OptionChoice(name="Joey", value="Joey"),
                discord.OptionChoice(name="Justin", value="Justin"),
                discord.OptionChoice(name="Kendra", value="Kendra"),
                discord.OptionChoice(name="Kimberly", value="Kimberly"),
                discord.OptionChoice(name="Matthew", value="Matthew"),
                discord.OptionChoice(name="Salli", value="Salli"),
            ],
        ),
    ):
        await ctx.defer()

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://ttsmp3.com/makemp3_new.php",
                data={
                    "msg": text,
                    "lang": voice,
                    "source": "ttsmp3",
                    "quality": "hi",
                    "speed": "0",
                    "action": "process",
                },
            ) as response:
                data = await response.json()

            async with session.get(data["URL"]) as response:
                with open("tts.mp3", "wb") as file:
                    file.write(await response.read())

            await ctx.respond(file=discord.File("tts.mp3"))
            os.remove("tts.mp3")


def setup(bot_: discord.Bot):
    bot_.add_cog(Misc(bot_))
