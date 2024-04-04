import datetime

import discord
from discord.ext import commands, tasks
from tmdbv3api import TV, TMDb

from helpers.utils import format_air_date, load_config
from services.ui import UI

config = load_config()


class Events(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.db = bot.db
        self.log = bot.log
        self.ui = UI()
        self.tmdb = TMDb()
        self.tmdb.api_key = bot.config["tmdb"]["api_key"]
        self.tv = TV()

        self.check_reminders.start()
        self.show_alerts.start()

    # |--- Server Events ---|
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_doc = await self.db.guilds.find_one({"guild_id": member.guild.id})
        if not guild_doc:
            return

        if guild_doc["welcome_enabled"] != 1:
            return

        channel = member.guild.get_channel(guild_doc["welcome_channel"])
        if not channel:
            return

        avatar = member.avatar.url if member.avatar else member.default_avatar.url
        member_count = member.guild.member_count
        username = member.display_name

        if len(username) > 6:
            username = username[:6] + "..."

        file = await self.ui.welcome_card(avatar, member_count, username)

        await channel.send(
            f"Welcome to {member.guild.name}, {member.mention}! We hope you enjoy your stay.",
            file=file,
        )

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        try:
            guild_doc = await self.db.guilds.find_one({"guild_id": guild.id})
            if not guild_doc:
                await self.db.guilds.insert_one(
                    {
                        "guild_id": guild.id,
                        "welcome_enabled": 0,
                        "welcome_channel": None,
                        "leave_enabled": 0,
                        "leave_channel": None,
                    }
                )
        except Exception as e:
            self.log(f"Error occurred during on_guild_join: {e}")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        try:
            result = await self.db.guilds.delete_one({"guild_id": guild.id})
            if result.deleted_count == 0:
                self.log(f"Guild {guild.id} not found in the database.")
        except Exception as e:
            self.log(f"Error occurred during on_guild_remove: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        pass  # TODO: Implement leave messages

    # |--- Reminder Events ---|
    # TODO: make reminder message look better
    @tasks.loop(seconds=config["constants"]["reminder_check_interval"])
    async def check_reminders(self):
        current_time = datetime.datetime.now(datetime.timezone.utc)
        due_reminders = self.db.reminders.find(
            {"time": {"$lte": current_time.timestamp()}}
        )

        for reminder in await due_reminders.to_list(length=100):
            user = self.bot.get_user(reminder["user_id"])
            if user:
                try:
                    await user.send(f"Reminder: {reminder['reminder']}")
                    await self.db.reminders.delete_one({"_id": reminder["_id"]})
                except discord.HTTPException as e:
                    self.log.error(f"Failed to send reminder to {user.name}: {e}")

    # |--- Show Alerts ---|
    @tasks.loop(minutes=20, reconnect=True)
    async def show_alerts(self):
        await self.bot.wait_until_ready()

        user_shows = await self.db.user_shows.find({}).to_list(None)

        for show in user_shows:
            user = self.bot.get_user(show["user_id"])
            if not user:
                continue

            last_episode = show["last_episode"]
            next_episode = show["next_episode"]

            if not last_episode or not next_episode:
                continue

            show_details = self.tv.details(show["show_id"])

            if (
                show_details.last_episode_to_air.id != last_episode["id"]
                or show_details.next_episode_to_air.id != next_episode["id"]
            ):
                last_episode = show_details.last_episode_to_air
                next_episode = show_details.next_episode_to_air

                embed = discord.Embed(
                    title="New Episode Available!",
                    description=f"A new episode of **{show['show_name']}** is now available!",
                    color=discord.Color.green(),
                )
                embed.add_field(
                    name=f"Episode {last_episode.episode_number}",
                    value=f"{last_episode.name} ({format_air_date(last_episode.air_date)})",
                    inline=False,
                )
                embed.add_field(
                    name="Overview",
                    value=f"|| {last_episode.overview} ||",
                    inline=False,
                )
                embed.set_image(
                    url=f"https://image.tmdb.org/t/p/original{show_details.last_episode_to_air.still_path}"
                )
                await user.send(embed=embed)

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

                await self.db.user_shows.update_one(
                    {"_id": show["_id"]},
                    {
                        "$set": {
                            "last_episode": last_episode_dict,
                            "next_episode": next_episode_dict,
                        }
                    },
                )


def setup(bot: discord.Bot):
    bot.add_cog(Events(bot))
