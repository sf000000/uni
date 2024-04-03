import datetime
import os
import platform
from io import BytesIO

import discord
import httpx
import psutil
import pytz
import undetected_chromedriver as uc
from dateparser import parse
from discord.ext import commands

from helpers.utils import iso_to_discord, nano_id
from services.github_api import GitHubAPI


class Information(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.db = bot.db
        self.log = bot.log
        self.config = bot.config
        self.github_api = GitHubAPI()
        self.start_time = datetime.datetime.now()

    @discord.slash_command(
        name="ping",
        description="Get the bot's latency.",
    )
    async def ping(self, ctx: discord.ApplicationContext):
        await ctx.respond(f"Pong! 🏓️ {round(self.bot.latency * 1000)}ms")

    _sticker = discord.commands.SlashCommandGroup(
        name="sticker",
        description="Manage stickers.",
    )

    @_sticker.command(
        name="add",
        description="Add a sticker to the server.",
    )
    @commands.has_permissions(manage_emojis_and_stickers=True)
    async def sticker_add(
        self,
        ctx: discord.ApplicationContext,
        name: discord.Option(
            str,
            description="The name of the sticker",
            required=True,
        ),
        emoji: discord.Option(
            str,
            description="The emoji to use for the sticker",
            required=True,
        ),
        sticker: discord.Option(
            discord.Attachment,
            description="The sticker to add",
            required=True,
        ),
    ):
        try:
            created_sticker = await ctx.guild.create_sticker(
                name=name,
                file=discord.File(BytesIO(await sticker.read()), "sticker.png"),
                emoji=emoji,
            )
            await ctx.respond(f"Created sticker `{created_sticker.name}`. 🎉")
        except Exception as e:
            self.log.error(e)
            return await ctx.respond(
                f"Could not create sticker. ```py\n{e}```", ephemeral=True
            )

    @_sticker.command(
        name="remove",
        description="Remove a sticker from the server.",
    )
    @commands.has_permissions(manage_emojis_and_stickers=True)
    async def sticker_remove(
        self,
        ctx: discord.ApplicationContext,
        sticker_name: discord.Option(
            str, description="The name of the sticker to remove", required=True
        ),
    ):
        sticker = discord.utils.get(ctx.guild.stickers, name=sticker_name)
        if not sticker:
            return await ctx.respond("Sticker not found.", ephemeral=True)
        await sticker.delete()
        await ctx.respond(f"🗑️ Deleted sticker `{sticker.name}`.")

    @_sticker.command(
        name="tag",
        description="Add server vanity to all stickers.",
    )
    @commands.has_permissions(manage_emojis_and_stickers=True)
    async def sticker_tag(
        self,
        ctx: discord.ApplicationContext,
        vanity_code: discord.Option(
            str,
            description="The vanity code to add to the stickers",
            required=True,
        ),
    ):
        await ctx.defer()

        completed = 0
        for sticker in ctx.guild.stickers:
            new_name = f"{sticker.name} | .gg/{vanity_code}"

            if new_name == sticker.name:
                continue

            if len(new_name) <= 30:
                await sticker.edit(name=new_name)
                completed += 1
        await ctx.respond(f"Tagged {completed} stickers. 🏷️")

    _timezone = discord.commands.SlashCommandGroup(
        name="timezone",
        description="Manage timezones.",
    )

    @_timezone.command(
        name="set",
        description="Set your timezone",
    )
    async def timezone_set(
        self,
        ctx: discord.ApplicationContext,
        timezone: discord.Option(
            str,
            description="The timezone to set",
            required=True,
        ),
    ):
        if timezone not in pytz.common_timezones:
            return await ctx.respond("Invalid timezone. Use `/timezone list`.")
        user_timezones = self.bot.db.user_timezones
        await user_timezones.update_one(
            {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
            {"$set": {"timezone": timezone}},
            upsert=True,
        )

        embed = discord.Embed(
            title="Timezone Set",
            description=f"Your timezone has been set to `{timezone}`.",
            color=self.config["colors"]["success"],
        )

        tz = pytz.timezone(timezone)
        now = datetime.datetime.now(tz)

        formatted_12_hour_time = now.strftime("%I:%M %p").lstrip("0").replace(" 0", " ")
        formatted_24_hour_time = now.strftime("%H:%M")
        combined_time = f"{formatted_12_hour_time} ({formatted_24_hour_time})"

        embed.add_field(name="Current Time", value=combined_time)
        await ctx.respond(embed=embed)

    @_timezone.command(
        name="list",
        description="List all timezones",
    )
    async def timezone_list(
        self,
        ctx: discord.ApplicationContext,
    ):
        await ctx.respond(
            "All timezones can be found here: https://gist.github.com/notjawad/be42744b57bfb7b12496c43db95c52be",
            ephemeral=True,
        )

    @_timezone.command(
        name="get",
        description="Get a user's timezone",
    )
    async def timezone_get(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(
            discord.Member,
            description="The user to get the timezone of",
            required=True,
        ),
    ):
        user_timezones = self.bot.db.user_timezones
        result = await user_timezones.find_one(
            {"guild_id": ctx.guild_id, "user_id": user.id}
        )

        if not result:
            return await ctx.respond("User has not set their timezone.")

        embed = discord.Embed(
            title="Timezone",
            description=f"{user.mention}'s timezone is `{result['timezone']}`.",
            color=self.config["colors"]["success"],
        )

        tz = pytz.timezone(result["timezone"])
        now = datetime.datetime.now(tz)

        formatted_12_hour_time = now.strftime("%I:%M %p").lstrip("0").replace(" 0", " ")
        formatted_24_hour_time = now.strftime("%H:%M")
        combined_time = f"{formatted_12_hour_time} ({formatted_24_hour_time})"

        embed.add_field(name="Current Time", value=combined_time)
        await ctx.respond(embed=embed)

    @_timezone.command(
        name="remove",
        description="Remove your timezone",
    )
    async def timezone_remove(
        self,
        ctx: discord.ApplicationContext,
    ):
        user_timezones = self.bot.db.user_timezones
        result = await user_timezones.delete_one(
            {"guild_id": ctx.guild.id, "user_id": ctx.author.id}
        )

        if result.deleted_count > 0:
            await ctx.respond("Your timezone has been removed.")
        else:
            await ctx.respond("You haven't set your timezone yet.")

    @discord.slash_command(
        name="define",
        description="Get the definition of a word.",
    )
    async def define(
        self,
        ctx: discord.ApplicationContext,
        word: discord.Option(
            str,
            description="The word to define",
            required=True,
        ),
    ):
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError:
                return await ctx.respond("Could not get definition.", ephemeral=True)

        embed = discord.Embed(
            title=data[0]["word"],
            description=data[0]["meanings"][0]["definitions"][0]["definition"],
            color=self.config["colors"]["default"],
        )

        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="inviteinfo",
        description="Get information about an invite code.",
    )
    async def inviteinfo(
        self,
        ctx: discord.ApplicationContext,
        invite_code: discord.Option(
            str,
            description="The invite code to get information about",
            required=True,
        ),
    ):
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"https://discord.com/api/v9/invites/{invite_code}"
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError:
                return await ctx.respond(
                    "Could not get invite information.", ephemeral=True
                )

        timestamp = datetime.datetime.strptime(
            data["expires_at"], "%Y-%m-%dT%H:%M:%S%z"
        ).timestamp()
        banner = f"https://cdn.discordapp.com/banners/{data['guild']['id']}/{data['guild']['banner']}.png?size=512"

        embed = discord.Embed(
            title=data["guild"]["name"],
            description=data["guild"]["description"],
            color=self.config["colors"]["default"],
        )
        embed.add_field(name="Expires", value=f"<t:{int(timestamp)}:R>")
        embed.set_image(url=banner)

        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="screenshot",
        description="Get a screenshot of a website",
    )
    async def screenshot(
        self,
        ctx: discord.ApplicationContext,
        url: discord.Option(
            str, description="The website to screenshot", required=True
        ),
    ):
        await ctx.defer()

        driver = uc.Chrome(headless=True, use_subprocess=False)
        driver.get(url)
        driver.save_screenshot(f"temp/{ctx.author.id}.png")

        await ctx.respond(file=discord.File(f"temp/{ctx.author.id}.png"))

        os.remove(f"temp/{ctx.author.id}.png")

    _reminders = discord.commands.SlashCommandGroup(
        name="reminders", description="Reminder related commands."
    )

    @_reminders.command(
        name="add",
        description="Add a reminder.",
        time=discord.Option(
            str,
            description="The time to set the reminder for.",
            required=True,
        ),
        reminder=discord.Option(
            str,
            description="The reminder message.",
            required=True,
        ),
    )
    async def reminders_add(
        self,
        ctx: discord.ApplicationContext,
        time: discord.Option(
            str,
            description="The time to set the reminder for.",
            required=True,
        ),
        reminder: discord.Option(
            str,
            description="The reminder message.",
            required=True,
        ),
    ):
        try:
            future_time = parse(
                time,
                settings={
                    "TIMEZONE": "UTC",
                    "PREFER_DATES_FROM": "future",
                    "RELATIVE_BASE": datetime.datetime.now(datetime.timezone.utc),
                },
            )

        except Exception as e:
            self.log.error(e)

        if not future_time:
            return await ctx.respond(
                "Could not parse time. Please use a valid time format.",
                ephemeral=True,
            )

        if future_time < datetime.datetime.now():
            return await ctx.respond("Time cannot be in the past.", ephemeral=True)

        reminder_doc = {
            "reminder_id": nano_id(),
            "user_id": ctx.author.id,
            "guild_id": ctx.guild_id,
            "time": int(future_time.timestamp()),
            "reminder": reminder,
        }

        await self.db.reminders.insert_one(reminder_doc)

        await ctx.respond(
            f"Reminder set for <t:{int(future_time.timestamp())}:F>.",
        )

    # TODO: Change this to use a select menu, the same as the github commits command.
    @_reminders.command(
        name="view",
        description="View a list of your reminders.",
    )
    async def reminders_view(self, ctx: discord.ApplicationContext):
        reminders = await self.db.reminders.find(
            {"user_id": ctx.author.id, "guild_id": ctx.guild.id}
        ).to_list(length=None)

        if not reminders:
            return await ctx.respond(
                "You don't have any reminders.",
                ephemeral=True,
            )

        embed = discord.Embed(
            title="Reminders",
            color=self.config["colors"]["success"],
        )

        for reminder in reminders:
            reminder_timestamp = datetime.datetime.fromtimestamp(reminder["time"])
            embed.add_field(
                name=f"#{reminder['reminder_id']}",
                value=f"Time: <t:{int(reminder_timestamp.timestamp())}:R>\nReminder: {reminder['reminder']}",
                inline=False,
            )

        await ctx.respond(embed=embed)

    @_reminders.command(
        name="delete",
        description="Delete a reminder.",
        reminder_id=discord.Option(
            str,
            description="The ID of the reminder to delete.",
            required=True,
        ),
    )
    async def reminders_delete(
        self,
        ctx: discord.ApplicationContext,
        reminder_id: discord.Option(
            str,
            description="The ID of the reminder to delete.",
            required=True,
        ),
    ):
        result = await self.db.reminders.delete_one(
            {
                "reminder_id": reminder_id,
                "user_id": ctx.author.id,
                "guild_id": ctx.guild.id,
            }
        )

        if result.deleted_count == 0:
            return await ctx.respond(
                "Reminder not found or you do not have permission to delete it.",
                ephemeral=True,
            )

        await ctx.respond(
            "Reminder deleted.",
            ephemeral=True,
        )

    @_reminders.command(
        name="clear",
        description="Clear all of your reminders.",
    )
    async def reminders_clear(self, ctx: discord.ApplicationContext):
        result = await self.db.reminders.delete_many(
            {"user_id": ctx.author.id, "guild_id": ctx.guild.id}
        )

        if result.deleted_count == 0:
            return await ctx.respond(
                "You don't have any reminders.",
                ephemeral=True,
            )

        await ctx.respond(
            "All reminders deleted.",
            ephemeral=True,
        )

    @discord.slash_command(
        name="avatar",
        description="Get a user's avatar.",
    )
    async def avatar(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(
            discord.Member,
            description="The user to get the avatar of",
        ),
    ):
        member = member or ctx.author

        embed = discord.Embed(color=self.config["colors"]["success"])
        embed.set_image(url=member.avatar.url)
        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="about", description="Get some useful (or not) information about the bot."
    )
    async def about(self, ctx: discord.ApplicationContext):
        commit_info = await self.github_api.get_latest_commit_info(self.config["repo"])
        latest_commit = commit_info[0]
        uptime = datetime.datetime.now() - self.start_time

        embed = (
            discord.Embed(
                description="Uni is a multipurpose Discord bot.",
                color=self.config["colors"]["default"],
            )
            .add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms")
            .add_field(
                name="Version",
                value=f"[{latest_commit['sha'][:7]}]({latest_commit['url']}) - {iso_to_discord(latest_commit['commit']['author']['date'])}",
            )
            .add_field(name="Uptime", value=str(uptime).split(".")[0])
            .add_field(name="Python", value=f"{platform.python_version()}")
            .add_field(
                name="Memory Usage",
                value=f"{round(psutil.Process().memory_info().rss / 1024 ** 2)} / {round(psutil.virtual_memory().total / 1024 ** 2)} MB",
            )
            .set_thumbnail(url=self.bot.user.avatar.url)
        )

        await ctx.respond(embed=embed)


def setup(bot: discord.Bot):
    bot.add_cog(Information(bot))
