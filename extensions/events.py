import datetime

import discord
from discord.ext import commands, tasks

from helpers.utils import load_config
from services.ui import UI

config = load_config()


class Events(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.db = bot.db
        self.log = bot.log
        self.ui = UI()

        self.check_reminders.start()

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
                self.bot.logger.warning(f"Guild {guild.id} not found in the database.")
        except Exception as e:
            self.log(f"Error occurred during on_guild_remove: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        pass  # TODO: Implement leave messages

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


def setup(bot: discord.Bot):
    bot.add_cog(Events(bot))
