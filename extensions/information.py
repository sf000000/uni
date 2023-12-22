import discord
import yaml
import aiohttp
import io
import datetime
import pytz
import aiosqlite
import platform

from kick_py import Kick
from discord.ext import commands, tasks
from colorthief import ColorThief
from helpers.utils import fetch_latest_commit_info, iso_to_discord_timestamp


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class Information(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.db_path = "kino.db"
        self.bot.loop.create_task(self.setup_db())
        self.check_reminders.start()
        self.bot_started = datetime.datetime.now()

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
        sticker_url: discord.Option(
            str,
            description="The URL of the sticker",
            required=True,
        ),
    ):
        async with aiohttp.ClientSession() as session:
            async with session.get(sticker_url) as resp:
                if resp.status != 200:
                    return await ctx.respond(
                        "Could not download sticker.", ephemeral=True
                    )
                try:
                    created_sticker = await ctx.guild.create_sticker(
                        name=name,
                        file=discord.File(io.BytesIO(await resp.read()), filename=name),
                        emoji=emoji,
                    )
                except discord.HTTPException:
                    return await ctx.respond(
                        "Could not create sticker.", ephemeral=True
                    )
                await ctx.respond(f"Created sticker `{created_sticker.name}`. \🎉")

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
        await ctx.respond(f"Deleted sticker `{sticker.name}`. \🗑️")

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
        await ctx.respond(f"Tagged {completed} stickers. \🏷️")

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
        timezone: str = discord.Option(
            description="Select your timezone (Case sensitive)",
            required=True,
        ),
    ):
        if timezone not in pytz.common_timezones:
            return await ctx.respond("Invalid timezone. Use `/timezone list`.")

        async with self.conn.execute(
            "CREATE TABLE IF NOT EXISTS user_timezones (guild_id INTEGER, user_id INTEGER PRIMARY KEY, timezone TEXT)"
        ):
            pass

        async with self.conn.execute(
            "INSERT OR REPLACE INTO user_timezones (guild_id, user_id, timezone) VALUES (?, ?, ?)",
            (ctx.guild.id, ctx.author.id, timezone),
        ):
            pass

        embed = discord.Embed(
            title="Timezone Set",
            description=f"Your timezone has been set to `{timezone}`.",
            color=config["COLORS"]["SUCCESS"],
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
        user: discord.User = discord.Option(
            description="The user to get the timezone of",
            required=True,
        ),
    ):
        async with self.conn.execute(
            "SELECT timezone FROM user_timezones WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, user.id),
        ) as cursor:
            result = await cursor.fetchone()

        if not result:
            return await ctx.respond("User has not set their timezone.")

        embed = discord.Embed(
            title="Timezone",
            description=f"{user.mention}'s timezone is `{result[0]}`.",
            color=config["COLORS"]["SUCCESS"],
        )

        tz = pytz.timezone(result[0])
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
        async with self.conn.execute(
            "DELETE FROM user_timezones WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, ctx.author.id),
        ):
            pass

        await ctx.respond("Your timezone has been removed.")

    @_timezone.command(
        name="all",
        description="List all users' timezones",
    )
    async def timezone_all(
        self,
        ctx: discord.ApplicationContext,
    ):
        async with self.conn.execute(
            "SELECT user_id, timezone FROM user_timezones WHERE guild_id = ?",
            (ctx.guild.id,),
        ) as cursor:
            results = await cursor.fetchall()

        if not results:
            return await ctx.respond("No users have set their timezones.")

        embed = discord.Embed(
            title="Timezones",
            color=config["COLORS"]["SUCCESS"],
        )

        for user_id, timezone in results:
            user = await self.bot.fetch_user(user_id)
            embed.add_field(name=user.display_name, value=timezone)

        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="define",
        description="Get the definition of a word.",
    )
    async def define(
        self,
        ctx: discord.ApplicationContext,
        word: str = discord.Option(
            description="The word to define",
            required=True,
        ),
    ):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
            ) as resp:
                if resp.status != 200:
                    return await ctx.respond(
                        "Could not get definition.", ephemeral=True
                    )
                data = await resp.json()

        embed = discord.Embed(
            title=data[0]["word"],
            description=data[0]["meanings"][0]["definitions"][0]["definition"],
            color=config["COLORS"]["INVISIBLE"],
        )

        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="urban",
        description="Get the Urban Dictionary definition of a word.",
    )
    async def urban(
        self,
        ctx: discord.ApplicationContext,
        word: str = discord.Option(
            description="The word to define",
            required=True,
        ),
    ):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.urbandictionary.com/v0/define?term={word}"
            ) as resp:
                if resp.status != 200:
                    return await ctx.respond(
                        "Could not get definition.", ephemeral=True
                    )
                data = await resp.json()

        embed = discord.Embed(
            title=data["list"][0]["word"],
            description=data["list"][0]["definition"],
            color=config["COLORS"]["INVISIBLE"],
        )

        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="inviteinfo",
        description="Get information about an invite code.",
    )
    async def inviteinfo(
        self,
        ctx: discord.ApplicationContext,
        invite_code: str = discord.Option(
            description="The invite code to get information about",
            required=True,
        ),
    ):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://discord.com/api/v9/invites/{invite_code}"
            ) as resp:
                if resp.status != 200:
                    return await ctx.respond(
                        "Could not get invite information.", ephemeral=True
                    )
                data = await resp.json()

        timestamp = datetime.datetime.strptime(
            data["expires_at"], "%Y-%m-%dT%H:%M:%S%z"
        ).timestamp()
        banner = f"https://cdn.discordapp.com/banners/{data['guild']['id']}/{data['guild']['banner']}.png?size=512"

        embed = discord.Embed(
            title=data["guild"]["name"],
            description=data["guild"]["description"],
            color=config["COLORS"]["INVISIBLE"],
        )
        embed.add_field(name="Expires", value=f"<t:{int(timestamp)}:R>")
        embed.set_image(url=banner)

        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="hex",
        description="Grab the most dominant color from an image",
    )
    async def hex(
        self,
        ctx: discord.ApplicationContext,
        image_url: str = discord.Option(
            description="The image to get the color from", required=True
        ),
    ):
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    return await ctx.respond("Could not get image.", ephemeral=True)

                data = await resp.read()

                color_thief = ColorThief(io.BytesIO(data))
                dominant_color = color_thief.get_color(quality=1)
                hex_color = f"#{dominant_color[0]:02x}{dominant_color[1]:02x}{dominant_color[2]:02x}"

                embed = discord.Embed(
                    title="Dominant Color",
                    description=hex_color,
                    color=discord.Color.from_rgb(*dominant_color),
                )
                embed.set_thumbnail(url=image_url)
                await ctx.respond(embed=embed)

    @discord.slash_command(
        name="screenshot",
        description="Get a screenshot of a website",
    )
    async def screenshot(
        self,
        ctx: discord.ApplicationContext,
        url: str = discord.Option(
            description="The website to screenshot", required=True
        ),
    ):
        await ctx.defer()

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://image.thum.io/get/width/1920/crop/675/noanimate/{url}"
            ) as resp:
                if resp.status != 200:
                    return await ctx.respond(
                        "Could not get screenshot.", ephemeral=True
                    )

                data = await resp.read()

                embed = discord.Embed(
                    title="Screenshot",
                    color=config["COLORS"]["INVISIBLE"],
                )
                embed.set_image(url="attachment://screenshot.png")
                await ctx.respond(
                    embed=embed,
                    file=discord.File(io.BytesIO(data), filename="screenshot.png"),
                )

    _highlight = discord.commands.SlashCommandGroup(
        name="highlight",
        description="Set notifications for when a keyword is said",
    )

    @_highlight.command(
        name="add",
        description="Add a highlighted keyword",
    )
    async def highlight_add(
        self,
        ctx: discord.ApplicationContext,
        keyword: str = discord.Option(
            description="The keyword to highlight", required=True
        ),
    ):
        async with self.conn.execute(
            "CREATE TABLE IF NOT EXISTS highlight_keywords (guild_id INTEGER, user_id INTEGER, keyword TEXT)"
        ):
            pass

        async with self.conn.execute(
            "INSERT INTO highlight_keywords (guild_id, user_id, keyword) VALUES (?, ?, ?)",
            (ctx.guild.id, ctx.author.id, keyword),
        ):
            pass

        await ctx.respond(f"Added **{keyword}** to your highlights.")

    @_highlight.command(
        name="remove",
        description="Remove a highlighted keyword",
    )
    async def highlight_remove(
        self,
        ctx: discord.ApplicationContext,
        keyword: str = discord.Option(
            description="The keyword to remove", required=True
        ),
    ):
        async with self.conn.execute(
            "DELETE FROM highlight_keywords WHERE guild_id = ? AND user_id = ? AND keyword = ?",
            (ctx.guild.id, ctx.author.id, keyword),
        ):
            pass

        await ctx.respond(f"Removed **{keyword}** from your highlights.")

    @_highlight.command(
        name="list",
        description="List your highlighted keywords",
    )
    async def highlight_list(
        self,
        ctx: discord.ApplicationContext,
    ):
        async with self.conn.execute(
            "SELECT keyword FROM highlight_keywords WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, ctx.author.id),
        ) as cursor:
            results = await cursor.fetchall()

        if not results:
            return await ctx.respond("You have no highlighted keywords.")

        embed = discord.Embed(
            title="Highlighted Keywords",
            color=config["COLORS"]["SUCCESS"],
        )

        for keyword in results:
            embed.add_field(name=keyword[0], value="")

        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="membercount",
        description="Get the member count of the server.",
    )
    async def membercount(self, ctx: discord.ApplicationContext):
        await ctx.respond(f"There are {ctx.guild.member_count} members in this server.")

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
            time = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M")
        except ValueError:
            return await ctx.respond(
                "Invalid time format. Please use `YYYY-MM-DD HH:MM`.",
                ephemeral=True,
            )

        if time < datetime.datetime.now(datetime.timezone.utc):
            return await ctx.respond(
                "Time cannot be in the past.",
                ephemeral=True,
            )

        async with self.conn.execute(
            "CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, guild_id INTEGER, time TEXT, reminder TEXT)"
        ):
            pass

        async with self.conn.execute(
            "INSERT INTO reminders (user_id, guild_id, time, reminder) VALUES (?, ?, ?, ?)",
            (ctx.author.id, ctx.guild.id, time.strftime("%Y-%m-%d %H:%M"), reminder),
        ):
            pass

        await ctx.respond(
            f"Reminder set for <t:{int(time.timestamp())}:R>.",
            ephemeral=True,
        )

    @_reminders.command(
        name="view",
        description="View a list of your reminders.",
    )
    async def reminders_view(self, ctx: discord.ApplicationContext):
        async with self.conn.execute(
            "SELECT time, reminder, id FROM reminders WHERE user_id = ? AND guild_id = ?",
            (ctx.author.id, ctx.guild.id),
        ) as cursor:
            reminders = await cursor.fetchall()

        if not reminders:
            return await ctx.respond(
                "You don't have any reminders.",
                ephemeral=True,
            )

        embed = discord.Embed(
            title="Reminders",
            color=config["COLORS"]["SUCCESS"],
        )

        for reminder in reminders:
            reminder_timestamp = datetime.datetime.strptime(
                reminder[0], "%Y-%m-%d %H:%M:%S"
            )
            embed.add_field(
                name=f"Reminder #{reminder[2]}",
                value=f"Time: <t:{int(reminder_timestamp.timestamp())}:R>\nReminder: {reminder[1]}",
                inline=False,
            )

        await ctx.respond(embed=embed)

    @_reminders.command(
        name="delete",
        description="Delete a reminder.",
        reminder_id=discord.Option(
            int,
            description="The ID of the reminder to delete.",
            required=True,
        ),
    )
    async def reminders_delete(
        self,
        ctx: discord.ApplicationContext,
        reminder_id: discord.Option(
            int,
            description="The ID of the reminder to delete.",
            required=True,
        ),
    ):
        async with self.conn.execute(
            "DELETE FROM reminders WHERE user_id = ? AND guild_id = ? AND id = ?",
            (ctx.author.id, ctx.guild.id, reminder_id),
        ):
            pass

        await ctx.respond(
            "Reminder deleted.",
            ephemeral=True,
        )

    @_reminders.command(
        name="clear",
        description="Clear all of your reminders.",
    )
    async def reminders_clear(self, ctx: discord.ApplicationContext):
        async with self.conn.execute(
            "DELETE FROM reminders WHERE user_id = ? AND guild_id = ?",
            (ctx.author.id, ctx.guild.id),
        ):
            pass

        await ctx.respond(
            "Reminders cleared.",
            ephemeral=True,
        )

    @discord.slash_command(
        name="kickchannel",
        description="Get information about a Kick.com channel.",
    )
    async def kick_channel(
        self,
        ctx: discord.ApplicationContext,
        username: str = discord.Option(
            description="The username to get the channel of", required=True
        ),
    ):
        kick = Kick()
        channel_data = kick.get_channel(username)
        user_info = channel_data.get("user", {})
        recent_categories = channel_data.get("recent_categories", [])[:5]

        recent_categories_list = "\n".join(
            f"- {category['category']['icon']} {category['name']} ({category['viewers']})"
            for category in recent_categories
        )

        bio = user_info.get("bio", "No bio available.")
        embed_description = f"{bio}\n\n**Recent Categories:**\n{recent_categories_list}"

        embed = discord.Embed(
            description=embed_description,
            color=config["COLORS"]["INVISIBLE"],
        )

        if profile_pic := user_info.get("profile_pic"):
            embed.set_author(
                name=user_info.get("username", "Unknown"),
                url=f"https://kick.com/{user_info.get('username', 'user')}",
                icon_url=profile_pic,
            )
            embed.set_thumbnail(url=profile_pic)

        if email_verified_at := user_info.get("email_verified_at"):
            created_at_timestamp = datetime.datetime.fromisoformat(
                email_verified_at.rstrip("Z")
            ).timestamp()
            embed.add_field(name="Created", value=f"<t:{int(created_at_timestamp)}:R>")

        followers_count = channel_data.get("followers_count", 0)
        embed.add_field(name="Followers", value=followers_count)

        livestream_info = channel_data.get("livestream")
        if livestream_info:
            start_time = datetime.datetime.strptime(
                livestream_info["start_time"], "%Y-%m-%d %H:%M:%S"
            ).timestamp()
            viewers = livestream_info.get("viewer_count", 0)
            if thumbnail_url := livestream_info.get("thumbnail", {}).get("url"):
                embed.set_image(url=thumbnail_url)

            embed_description += (
                f"\n\n**LIVE [👁️ {viewers}]**\nStarted <t:{int(start_time)}:R>\n{livestream_info['session_title'][:50]}")  # fmt: skip
            embed.description = embed_description
        else:
            embed.add_field(name="Live", value="No")

        view = discord.ui.View()
        watch_button_url = f"https://kick.com/{user_info.get('username', 'user')}"
        watch_button = discord.ui.Button(
            style=discord.ButtonStyle.link,
            label="Watch",
            url=watch_button_url,
        )

        if livestream_info:
            view.add_item(watch_button)
        await ctx.respond(embed=embed, view=view)

    @discord.slash_command(
        name="about", description="Get some useful (or not) information about the bot."
    )
    async def about(self, ctx: discord.ApplicationContext):
        commit_info = await fetch_latest_commit_info()
        uptime = datetime.datetime.now() - self.bot_started
        bot_avatar_url = self.bot.user.avatar.url if self.bot.user.avatar else None

        async with self.conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM command_usage")
            total_commands_used = (await cur.fetchone())[0]

        embed = (
            discord.Embed(
                description="Uni is a multipurpose Discord bot.",
                color=config["COLORS"]["INVISIBLE"],
            )
            .add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms")
            .add_field(
                name="Version",
                value=f"[{commit_info['id'][:7]}]({commit_info['url']}) - {iso_to_discord_timestamp(commit_info['date'])}",
            )
            .add_field(name="Uptime", value=str(uptime).split(".")[0])
            .add_field(name="Commands Used", value=total_commands_used)
            .add_field(name="Python", value=f"{platform.python_version()}")
            .add_field(name="Pycord", value=f"{discord.__version__}")
            .set_thumbnail(url=bot_avatar_url)
        )

        source_code_button = discord.ui.Button(
            style=discord.ButtonStyle.link,
            label="Source Code",
            url="https://github.com/notjawad/uni",
        )
        view = discord.ui.View(timeout=60).add_item(source_code_button)

        await ctx.respond(embed=embed, view=view)

    @tasks.loop(minutes=1)
    async def check_reminders(self):
        async with self.conn.execute(
            "SELECT id, user_id, guild_id, time, reminder FROM reminders"
        ) as cursor:
            reminders = await cursor.fetchall()

        if not reminders:
            return

        for reminder in reminders:
            reminder_timestamp = datetime.datetime.strptime(
                reminder[3], "%Y-%m-%d %H:%M:%S"
            )
            if reminder_timestamp < datetime.datetime.now(datetime.timezone.utc):
                user = await self.bot.fetch_user(reminder[1])
                guild = self.bot.get_guild(reminder[2])
                await user.send(
                    f"Reminder for <t:{int(reminder_timestamp.timestamp())}:R>:\n{reminder[4]}"
                )

                async with self.conn.execute(
                    "DELETE FROM reminders WHERE id = ?", (reminder[0],)
                ):
                    pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        async with self.conn.execute(
            "SELECT keyword FROM highlight_keywords WHERE guild_id = ?",
            (message.guild.id,),
        ) as cursor:
            results = await cursor.fetchall()

        if not results:
            return

        for keyword in results:
            if keyword[0] in message.content:
                await message.author.send(
                    f"**{message.guild.name}**: {message.author.mention} said **{keyword[0]}** in {message.channel.mention}:\n\n{message.content}"
                )


def setup(bot_: discord.Bot):
    bot_.add_cog(Information(bot_))
