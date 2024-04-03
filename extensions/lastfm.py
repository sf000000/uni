import discord
from discord.ext import commands

from helpers.embeds import Embeds
from helpers.utils import localize_number
from services.lastfm_api import LastFMAPI


class LastFM(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.db = bot.db
        self.config = bot.config
        self.embed = Embeds()
        self.lastfm = LastFMAPI(self.config["lastfm"]["api_key"])

    _lastfm = discord.commands.SlashCommandGroup(
        name="lastfm", description="LastFM related commands."
    )

    @_lastfm.command(
        name="set",
        description="Set your LastFM username.",
        username=discord.Option(
            str,
            description="Your LastFM username.",
            required=True,
        ),
    )
    async def _set(self, ctx: discord.ApplicationContext, username: str):
        user_doc = await self.db.lastfm.find_one({"user_id": ctx.author.id})

        if user_doc:
            await self.db.lastfm.update_one(
                {"user_id": ctx.author.id}, {"$set": {"username": username}}
            )
            return await ctx.respond(
                embed=self.embed.success("Successfully updated your LastFM username."),
                ephemeral=True,
            )

        await self.db.lastfm.insert_one(
            {"user_id": ctx.author.id, "username": username}
        )
        await ctx.respond(
            embed=self.embed.success("Successfully set your LastFM username."),
            ephemeral=True,
        )

    @_lastfm.command(
        name="np",
        description="Shows the song you're currently listening to.",
    )
    async def _np(self, ctx: discord.ApplicationContext):
        user_doc = await self.db.lastfm.find_one({"user_id": ctx.author.id})

        if not user_doc:
            return await ctx.respond(
                embed=self.embed.error(
                    "You haven't set your LastFM username yet. Use `/lastfm set` to set it."
                ),
                ephemeral=True,
            )

        username = user_doc["username"]
        recent_tracks = await self.lastfm.get_recent_tracks(username)

        if not recent_tracks:
            return await ctx.respond(
                embed=self.embed.error("No recent tracks found."),
                ephemeral=True,
            )

        track = recent_tracks["track"][0]

        embed = discord.Embed(
            color=self.config["colors"]["success"],
        )
        embed.add_field(name="Artist", value=track["artist"]["#text"], inline=False)
        embed.add_field(
            name="Title", value=f"[{track['name']}]({track['url']})", inline=False
        )
        embed.set_thumbnail(url=track["image"][2]["#text"])

        await ctx.respond(embed=embed)

    @_lastfm.command(
        name="whois",
        description="View Last.fm profile information",
    )
    async def lastfm_whois(
        self,
        ctx: discord.ApplicationContext,
        username: discord.Option(
            str, description="The username to search for.", required=True
        ),
    ):
        user = await self.lastfm.get_user_info(username)
        embed = discord.Embed(
            description=f"User profile for **{user['name']}**",
            color=self.config["colors"]["brands"]["lastfm"],
        )

        embed.add_field(
            name="Play Count", value=localize_number(int(user["playcount"]))
        )
        embed.add_field(
            name="Artist Count",
            value=localize_number(int(user.get("artist_count", "N/A"))),
        )
        embed.add_field(
            name="Track Count",
            value=localize_number(int(user.get("track_count", "N/A"))),
        )
        embed.add_field(
            name="Album Count",
            value=localize_number(int(user.get("album_count", "N/A"))),
        )
        embed.add_field(name="Country", value=user.get("country", "N/A"))
        embed.add_field(
            name="Registered", value=f"<t:{user['registered']['unixtime']}:R>"
        )

        go_to_profile = discord.ui.Button(
            label="Go to Profile",
            url=user["url"],
            style=discord.ButtonStyle.link,
        )

        view = discord.ui.View()
        view.add_item(go_to_profile)

        if user["image"]:
            embed.set_thumbnail(url=user["image"][3]["#text"])

        await ctx.respond(embed=embed, view=view)


def setup(bot: discord.Bot):
    bot.add_cog(LastFM(bot))
