import discord
import aiosqlite
import yaml
import aiohttp
import datetime

from discord.ext import commands


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class Soundcloud(commands.Cog):
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

    _soundcloud = discord.commands.SlashCommandGroup(
        name="soundcloud", description="Soundcloud related commands."
    )

    @_soundcloud.command(
        name="search",
        description="Search for a song on Soundcloud.",
    )
    async def _search(
        self,
        ctx: discord.ApplicationContext,
        query: discord.Option(
            str,
            description="The query to search for.",
            required=True,
        ),
        show_comments: discord.Option(
            bool,
            description="Whether to show comments or not.",
            required=False,
            default=True,
        ),
    ):
        headers = {
            "Accept": "application/json",
        }

        params = {
            "q": query,
            "client_id": config["SOUNDCLOUD_CLIENT_ID"],
            "limit": "20",
            "offset": "0",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api-v2.soundcloud.com/search",
                params=params,
                headers=headers,
            ) as response:
                data = await response.json()

                if not data or "collection" not in data or not data["collection"]:
                    await ctx.respond(
                        "No results found for your search.", ephemeral=True
                    )
                    return

                tracks = [
                    track for track in data["collection"] if track["kind"] == "track"
                ]

                initial_track = tracks[0]

                title = initial_track.get("title", "Unknown Title")
                user = initial_track.get("user", {}).get("username", "Unknown Artist")
                duration_ms = initial_track.get("duration", 0)
                playback_count = initial_track.get("playback_count", "N/A")
                likes_count = initial_track.get("likes_count", "N/A")
                artwork_url = initial_track.get("artwork_url", None)

                embed = discord.Embed(color=config["COLORS"]["ORANGE"])
                embed.add_field(name="Title", value=title)
                embed.add_field(name="Artist", value=user)
                embed.add_field(
                    name="Duration",
                    value="{:02}:{:02}".format(
                        duration_ms // 60000, (duration_ms // 1000) % 60
                    ),
                )
                embed.add_field(name="Plays", value=playback_count)
                embed.add_field(name="Likes", value=likes_count)

                release_date = datetime.datetime.strptime(
                    initial_track["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                )
                embed.add_field(
                    name="Published",
                    value=f"<t:{int(release_date.timestamp())}:R>",
                )

                go_to_track = discord.ui.Button(
                    label="Go to Track",
                    url=initial_track["permalink_url"],
                    style=discord.ButtonStyle.link,
                )
                view = discord.ui.View()
                view.add_item(go_to_track)

                if artwork_url:
                    embed.set_thumbnail(url=artwork_url)

                comments = await self.get_track_comments(initial_track["id"])

                if comments and show_comments:
                    formatted_comments = [
                        f"{index + 1}. [{comment['user']['username']}]({comment['user']['permalink_url']}) - {comment['body']}"
                        for index, comment in enumerate(comments)
                    ]
                    embed.add_field(
                        name="Comments",
                        value="\n".join(formatted_comments),
                    )

                await ctx.respond(embed=embed, view=view)

    async def get_track_comments(self, track_id: str):
        headers = {
            "Accept": "application/json",
        }

        params = {
            "sort": "newest",
            "threaded": "1",
            "client_id": config["SOUNDCLOUD_CLIENT_ID"],
            "limit": "5",
            "offset": "0",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api-v2.soundcloud.com/tracks/{track_id}/comments",
                params=params,
                headers=headers,
            ) as response:
                data = await response.json()

                if not data or "collection" not in data or not data["collection"]:
                    return None

                return [
                    comment
                    for comment in data["collection"]
                    if comment["kind"] == "comment" and len(comment["body"]) <= 100
                ]


def setup(bot_: discord.Bot):
    bot_.add_cog(Soundcloud(bot_))
