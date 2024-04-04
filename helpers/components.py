import discord
from discord.ui import Button, Select, View

from helpers.utils import format_air_date


class ShowSelect(Select):
    def __init__(self, shows, tv, ctx, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shows = shows
        self.ctx = ctx
        self.tv = tv
        for show in shows:
            self.add_option(
                label=f"{show.name} ({show.first_air_date[:4]})", value=str(show.id)
            )

    async def callback(self, interaction: discord.Interaction):
        chosen_show = next(
            (show for show in self.shows if str(show.id) == self.values[0]), None
        )
        if chosen_show:
            chosen_show_details = self.tv.details(chosen_show.id)
            last_episode = chosen_show_details.last_episode_to_air
            next_episode = chosen_show_details.next_episode_to_air
            last_episode_dict = (
                {
                    "id": last_episode.id,
                    "name": last_episode.name,
                    "air_date": last_episode.air_date,
                    "episode_number": last_episode.episode_number,
                    "season_number": last_episode.season_number,
                }
                if last_episode
                else None
            )
            next_episode_dict = (
                {
                    "id": next_episode.id,
                    "name": next_episode.name,
                    "air_date": next_episode.air_date,
                    "episode_number": next_episode.episode_number,
                    "season_number": next_episode.season_number,
                }
                if next_episode
                else None
            )

            collection = self.ctx.bot.db["user_shows"]
            await collection.insert_one(
                {
                    "user_id": self.ctx.author.id,
                    "show_id": chosen_show_details.id,
                    "show_name": chosen_show_details.name,
                    "last_episode": last_episode_dict,
                    "next_episode": next_episode_dict,
                }
            )

            embed = discord.Embed(
                title="Show Tracked!",
                description=f"I will notify you when a new episode of **{chosen_show_details.name}** is released.",
                color=discord.Color.green(),
            )
            if last_episode:
                embed.add_field(
                    name="Last Episode",
                    value=f"{last_episode.name} ({format_air_date(last_episode.air_date)})",
                    inline=False,
                )
            if next_episode:
                embed.add_field(
                    name="Next Episode Date",
                    value=f"{next_episode.name} ({format_air_date(next_episode.air_date)})",
                    inline=False,
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "There was an error selecting the show.", ephemeral=True
            )


class ShowUntrackSelect(Select):
    def __init__(self, shows, ctx, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shows = shows
        self.ctx = ctx
        for show in shows:
            self.add_option(label=show["show_name"], value=str(show["show_id"]))

    async def callback(self, interaction: discord.Interaction):
        chosen_show_id = self.values[0]
        chosen_show = next(
            show for show in self.shows if str(show["show_id"]) == chosen_show_id
        )

        confirm_view = View()
        confirm_button = ConfirmButton(
            show_id=chosen_show_id, show_name=chosen_show["show_name"], ctx=self.ctx
        )
        cancel_button = CancelButton()
        confirm_view.add_item(confirm_button)
        confirm_view.add_item(cancel_button)

        await interaction.response.send_message(
            f"Are you sure you want to stop tracking **{chosen_show['show_name']}**?",
            view=confirm_view,
            ephemeral=True,
        )


class ConfirmButton(Button):
    def __init__(self, show_id, show_name, ctx, *args, **kwargs):
        super().__init__(
            label="Yes, stop tracking",
            style=discord.ButtonStyle.danger,
            *args,
            **kwargs,
        )
        self.show_id = show_id
        self.show_name = show_name
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        collection = self.ctx.bot.db["user_shows"]
        await collection.delete_one(
            {"user_id": self.ctx.author.id, "show_id": self.show_id}
        )
        await interaction.response.send_message(
            f"You have stopped tracking **{self.show_name}**.", ephemeral=True
        )


class CancelButton(Button):
    def __init__(self, *args, **kwargs):
        super().__init__(
            label="Cancel", style=discord.ButtonStyle.secondary, *args, **kwargs
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=None)
        await interaction.delete_original_response()
