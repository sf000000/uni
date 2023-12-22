import discord
import aiosqlite
import yaml
import aiohttp
import json
import urllib.request

from discord.ext import commands
from helpers.utils import iso_to_discord_timestamp


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class Fun(commands.Cog):
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

    async def fetch_json(self, url: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return None if response.status == 404 else await response.json()

    async def get_valorant_rank(self, name: str, tag: str, region: str):
        url = f"https://api.henrikdev.xyz/valorant/v2/mmr/{region}/{name}/{tag}"
        data = await self.fetch_json(url)
        if data:
            data = data["data"]
            return {
                "currenttier": data["current_data"]["currenttierpatched"],
                "mmr_change_to_last_game": data["current_data"][
                    "mmr_change_to_last_game"
                ],
                "elo": data["current_data"]["elo"],
                "next_rank_in": data["current_data"]["games_needed_for_rating"],
                "highest_rank": f"{data['highest_rank']['patched_tier']} ({data['highest_rank']['season']})",
                "rank_image": data["current_data"]["images"]["large"],
            }
        return None

    @discord.slash_command(
        name="duckduckgo",
        description="Searches DuckDuckGo for a query.",
    )
    async def duckduckgo(
        self,
        ctx: discord.ApplicationContext,
        query: discord.Option(
            str, description="The query to search for.", required=True
        ),
    ):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": query,
                    "format": "json",
                    "pretty": 1,
                },
            ) as resp:
                str_data = await resp.text()
                data = json.loads(str_data)

                # Check if there's a direct answer or abstract available
                if data.get("AbstractText"):
                    title = data.get("Heading", "Search Result")
                    description = data["AbstractText"]
                    url = data["AbstractURL"]

                    embed = discord.Embed(
                        title=title,
                        description=description,
                        url=url,
                        color=config["COLORS"]["SUCCESS"],
                    )
                    await ctx.respond(embed=embed)

                elif data.get("RelatedTopics"):
                    # If there's no direct answer, use the first few related topics
                    description_lines = []
                    for index, topic in enumerate(data["RelatedTopics"][:8]):
                        text = topic.get("Text")
                        first_url = topic.get("FirstURL")
                        if text and first_url:
                            description_lines.append(f"{index}. [{text}]({first_url})")
                    if description := "\n".join(description_lines):
                        embed = discord.Embed(
                            description=description,
                            color=config["COLORS"]["SUCCESS"],
                        )
                        await ctx.respond(embed=embed)
                    else:
                        await ctx.respond(
                            "Found no related topics with sufficient information.",
                            ephemeral=True,
                        )

                else:
                    await ctx.respond(
                        "Sorry, I couldn't find any results for that query.",
                        ephemeral=True,
                    )

    @discord.slash_command(
        name="google",
        description="Get some searching done.",
    )
    async def google(
        self,
        ctx: discord.ApplicationContext,
        query: discord.Option(
            str, description="The query to search for.", required=True
        ),
    ):
        google_url = "https://www.google.com/search?safe=active&q="
        await ctx.respond(
            google_url + urllib.parse.quote_plus(query, safe=""),
        )

    @discord.slash_command(
        name="valorant", description="Get Valorant profile for a player."
    )
    async def valorant(
        self,
        ctx: discord.ApplicationContext,
        player: discord.Option(
            str, description="The player to search for. (Name#Tag)", required=True
        ),
    ):
        if "#" not in player:
            return await ctx.respond(
                "Please provide a valid player name and tag. (Name#Tag)",
                ephemeral=True,
            )

        name, tag = player.split("#")
        await ctx.defer()

        account_url = f"https://api.henrikdev.xyz/valorant/v1/account/{name}/{tag}"
        account_data = await self.fetch_json(account_url)
        if not account_data:
            return await ctx.respond(
                "I couldn't find a player with that name and tag.",
                ephemeral=True,
            )

        region = account_data["data"]["region"]
        ranked_data = await self.get_valorant_rank(name, tag, region)

        if not ranked_data:
            return await ctx.respond(
                "Failed to retrieve rank data for the player.",
                ephemeral=True,
            )

        embed = discord.Embed(color=config["COLORS"]["SUCCESS"])

        embed.add_field(name="Name", value=account_data["data"]["name"], inline=True)
        embed.add_field(name="Tag", value=account_data["data"]["tag"], inline=True)
        embed.add_field(
            name="Level", value=account_data["data"]["account_level"], inline=True
        )
        embed.add_field(name="Region", value=region.upper(), inline=True)
        embed.add_field(name="Rank", value=ranked_data["currenttier"], inline=True)
        embed.add_field(name="Elo", value=ranked_data["elo"], inline=True)
        embed.add_field(
            name="Next Rank In",
            value=f"{ranked_data['next_rank_in']} game(s)",
            inline=True,
        )
        embed.add_field(
            name="Highest Rank", value=ranked_data["highest_rank"], inline=True
        )
        embed.add_field(
            name="Last Game MMR Change",
            value=ranked_data["mmr_change_to_last_game"],
            inline=True,
        )
        embed.set_image(url=account_data["data"]["card"]["wide"])
        embed.set_thumbnail(url=ranked_data["rank_image"])
        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="manga", description="Search MyAnimeList for manga information"
    )
    async def manga(
        self,
        ctx: discord.ApplicationContext,
        query: discord.Option(
            str, description="The query to search for.", required=True
        ),
    ):
        await ctx.defer()
        url = f"https://api.jikan.moe/v4/manga?q={query}"
        data = await self.fetch_json(url)
        if not data:
            return await ctx.respond(
                "I couldn't find a manga with that name.",
                ephemeral=True,
            )

        result = data["data"][0]

        embed = discord.Embed(
            description=result["synopsis"][:200] + "...",
            color=config["COLORS"]["SUCCESS"],
        )
        embed.set_author(name=f"{result['title']} ({result['title_japanese']})")
        embed.set_thumbnail(url=result["images"]["jpg"]["image_url"])
        embed.add_field(name="Status", value=result["status"])
        embed.add_field(
            name="First Release",
            value=iso_to_discord_timestamp(result["published"]["from"]),
        )
        embed.add_field(
            name="Score", value=f"**{result['score']}** ({result['scored_by']})"
        )
        embed.add_field(name="Popularity", value=f"#{result['popularity']}")
        embed.add_field(name="Members", value=result["members"])
        embed.add_field(name="Favorites", value=result["favorites"])
        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="anime", description="Search MyAnimeList for anime information"
    )
    async def anime(
        self,
        ctx: discord.ApplicationContext,
        query: discord.Option(
            str, description="The query to search for.", required=True
        ),
    ):
        await ctx.defer()
        url = f"https://api.jikan.moe/v4/anime?q={query}"
        data = await self.fetch_json(url)
        if not data:
            return await ctx.respond(
                "I couldn't find an anime with that name.",
                ephemeral=True,
            )

        result = data["data"][0]

        embed = discord.Embed(
            description=result["synopsis"][:200] + "...",
            color=config["COLORS"]["SUCCESS"],
        )
        embed.set_author(name=f"{result['title']} ({result['title_japanese']})")
        embed.set_thumbnail(url=result["images"]["jpg"]["image_url"])
        embed.add_field(name="Status", value=result["status"])
        embed.add_field(
            name="Aired",
            value=iso_to_discord_timestamp(result["aired"]["from"]),
        )
        embed.add_field(
            name="Score", value=f"**{result['score']}** ({result['scored_by']})"
        )
        embed.add_field(name="Popularity", value=f"#{result['popularity']}")
        embed.add_field(name="Trailer", value=f"[Youtube]({result['trailer']['url']})")
        embed.add_field(name="Episodes", value=result["episodes"])
        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="character", description="Search MyAnimeList for character information"
    )
    async def character(
        self,
        ctx: discord.ApplicationContext,
        query: discord.Option(
            str, description="The query to search for.", required=True
        ),
    ):
        await ctx.defer()
        url = f"https://api.jikan.moe/v4/characters?q={query}"
        data = await self.fetch_json(url)
        if not data:
            return await ctx.respond(
                "I couldn't find a character with that name.",
                ephemeral=True,
            )

        result = data["data"][0]

        embed = discord.Embed(
            description=result["about"][:200] + "...",
            color=config["COLORS"]["SUCCESS"],
        )
        embed.set_author(name=f"{result['name']} ({result['name_kanji']})")
        embed.set_thumbnail(url=result["images"]["jpg"]["image_url"])
        embed.add_field(name="Favorites", value=result["favorites"])
        embed.add_field(name="More Info", value=f"[MyAnimeList]({result['url']})")
        await ctx.respond(embed=embed)


def setup(bot_: discord.Bot):
    bot_.add_cog(Fun(bot_))
