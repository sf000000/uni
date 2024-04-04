import discord
from discord.ext import commands
from discord.ui import View
from tmdbv3api import TV, TMDb

from helpers.components import ShowSelect, ShowUntrackSelect


class Entertainment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.tmdb = TMDb()
        self.tmdb.api_key = bot.config["tmdb"]["api_key"]
        self.tv = TV()

    _showalerts = discord.commands.SlashCommandGroup(
        name="showalerts",
        description="Commands for managing show alerts",
    )

    @_showalerts.command(
        name="add",
        description="Add a show alert, I will notify you when a new episode is released",
    )
    async def trackshow(
        self,
        ctx: discord.ApplicationContext,
        title: discord.Option(
            str, "The title of the show you want to track", required=True
        ),
    ):
        search_results = self.tv.search(title)
        if not search_results:
            await ctx.respond(
                "No shows found with that title. Please try a different title.",
                ephemeral=True,
            )
            return

        if len(search_results) == 1:
            chosen_show = search_results[0]
            await self.db.user_shows.insert_one(
                {
                    "user_id": ctx.author.id,
                    "show_id": chosen_show.id,
                    "show_name": chosen_show.name,
                }
            )
            await ctx.respond(
                f"You are now tracking **{chosen_show.name}**!", ephemeral=True
            )
            return

        view = View()
        select = ShowSelect(
            search_results, self.tv, ctx, placeholder="Select a show to track"
        )
        view.add_item(select)
        await ctx.respond(
            "Please select the show you want to track:", view=view, ephemeral=True
        )

    @_showalerts.command(
        name="remove",
        description="Remove a show from your alerts list",
    )
    async def untrackshow(self, ctx: discord.ApplicationContext):
        collection = self.bot.db["user_shows"]
        user_shows = await collection.find({"user_id": ctx.author.id}).to_list(None)

        if not user_shows:
            await ctx.respond("You are not tracking any shows.", ephemeral=True)
            return

        select = ShowUntrackSelect(
            user_shows, ctx, placeholder="Select a show to stop tracking"
        )
        view = View()
        view.add_item(select)
        await ctx.respond(
            "Select the show you wish to stop tracking:", view=view, ephemeral=True
        )


def setup(bot):
    bot.add_cog(Entertainment(bot))
