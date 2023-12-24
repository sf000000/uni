import discord
import aiosqlite
import yaml
import time
import aiohttp
import zipfile
import os
import io
import wand.image
import wand.color
import pytz

from discord.ext import commands
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from helpers.snapchat import *
from datetime import datetime, timedelta


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class Server(commands.Cog):
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

    async def channel_autocomplete(self, ctx: discord.ApplicationContext, string: str):
        channels = ctx.guild.channels
        return [
            channel for channel in channels if string.lower() in channel.name.lower()
        ]

    def format_activity(self, activity):
        activity_formats = {
            discord.Spotify: lambda a: f"Listening to **{a.artist} - {a.title}**",
            discord.Game: lambda a: f"Playing **{a}**",
            discord.Streaming: lambda a: f"Watching **{a}**",
        }

        formatter = activity_formats.get(type(activity))

        return f" | {formatter(activity)}" if formatter else ""

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        try:
            async with self.conn.cursor() as cur:
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS guilds (guild_id INTEGER PRIMARY KEY, welcome_enabled INTEGER DEFAULT 0, welcome_channel INTEGER, leave_enabled INTEGER DEFAULT 0, leave_channel INTEGER)"
                )
                await cur.execute(
                    "SELECT 1 FROM guilds WHERE guild_id = ?", (guild.id,)
                )

                if not await cur.fetchone():
                    await cur.execute(
                        "INSERT INTO guilds (guild_id) VALUES (?)", (guild.id,)
                    )
                await self.conn.commit()
        except Exception as e:
            print(f"Error occurred during on_guild_join: {e}")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        try:
            async with self.conn.cursor() as cur:
                await cur.execute("DELETE FROM guilds WHERE guild_id = ?", (guild.id,))
                await self.conn.commit()
        except Exception as e:
            print(f"Error occurred during on_guild_remove: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT welcome_enabled, welcome_channel FROM guilds WHERE guild_id = ?",
                (member.guild.id,),
            )
            row = await cur.fetchone()
            if row is None or not row[0]:
                return

            welcome_enabled, welcome_channel_id = row
            welcome_channel = self.bot.get_channel(welcome_channel_id)
            if not welcome_channel:
                return

            avatar_url = (
                member.avatar.url
                if member.avatar
                else "https://files.catbox.moe/hg13w4.png"
            )
            formatted_url = f"https://uni-styles.vercel.app/welcome-card/{member.name}/{member.guild.name}/{member.guild.member_count}?avatarUrl={avatar_url}"

            async def run_selenium():
                options = Options()
                options.add_argument("--headless")
                options.add_argument("--no-sandbox")
                options.add_argument("--incognito")
                options.add_experimental_option("detach", True)
                options.add_experimental_option("excludeSwitches", ["enable-logging"])
                options.add_argument("--window-size=1280,720")

                driver = webdriver.Chrome(options=options)
                driver.get(formatted_url)

                try:
                    element_present = EC.presence_of_element_located((By.ID, "capture"))
                    WebDriverWait(driver, 10).until(element_present)

                    element = driver.find_element(by=By.ID, value="capture")
                    time.sleep(2)
                    element.screenshot("temp/welcome.png")

                    return "temp/welcome.png"

                finally:
                    driver.quit()

            result = await run_selenium()

            rules_channel_button = discord.ui.Button(
                label="Rules",
                style=discord.ButtonStyle.link,
                emoji="📜",
                url="https://discord.com/channels/793676963335897110/793712201365323786",
            )
            discussion_channel_button = discord.ui.Button(
                label="Discussion",
                style=discord.ButtonStyle.link,
                emoji="💬",
                url="https://discord.com/channels/793676963335897110/793676963335897112",
            )
            roles_channel_button = discord.ui.Button(
                label="Roles",
                style=discord.ButtonStyle.link,
                emoji="📚",
                url="https://discord.com/channels/793676963335897110/customize-community",
            )
            events_channel_button = discord.ui.Button(
                label="Events",
                style=discord.ButtonStyle.link,
                emoji="📅",
                url="https://discord.com/channels/793676963335897110/1110315118392258610",
            )

            view = discord.ui.View()
            view.add_item(rules_channel_button)
            view.add_item(roles_channel_button)
            view.add_item(discussion_channel_button)
            view.add_item(events_channel_button)

            await welcome_channel.send(
                member.mention,
                file=discord.File(result),
                view=view if member.guild.id == config["HOME_GUILD"] else None,
            )
            os.remove(result)

    _welcome = discord.commands.SlashCommandGroup(
        name="welcome", description="Welcome messages"
    )

    @_welcome.command(name="enable", description="Enable welcome messages")
    @commands.has_permissions(manage_guild=True)
    async def _welcome_enable(self, ctx: discord.ApplicationContext):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "UPDATE guilds SET welcome_enabled = 1 WHERE guild_id = ?",
                (ctx.guild.id,),
            )
            await self.conn.commit()
        await ctx.respond("Welcome messages enabled.", ephemeral=True)

    @_welcome.command(name="disable", description="Disable welcome messages")
    @commands.has_permissions(manage_guild=True)
    async def _welcome_disable(self, ctx: discord.ApplicationContext):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "UPDATE guilds SET welcome_enabled = 0 WHERE guild_id = ?",
                (ctx.guild.id,),
            )
            await self.conn.commit()
        await ctx.respond("Welcome messages disabled.", ephemeral=True)

    @_welcome.command(name="channel", description="Set the welcome channel")
    @commands.has_permissions(manage_guild=True)
    async def _welcome_channel(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.Option(
            discord.TextChannel, "Select a channel", autocomplete=channel_autocomplete
        ),
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "UPDATE guilds SET welcome_channel = ? WHERE guild_id = ?",
                (channel.id, ctx.guild.id),
            )
            await self.conn.commit()
        await ctx.respond(f"Welcome channel set to {channel.mention}.", ephemeral=True)

    _leave = discord.commands.SlashCommandGroup(
        name="leave", description="Leave messages"
    )

    @_leave.command(name="enable", description="Enable leave messages")
    @commands.has_permissions(manage_guild=True)
    async def _leave_enable(self, ctx: discord.ApplicationContext):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "UPDATE guilds SET leave_enabled = 1 WHERE guild_id = ?",
                (ctx.guild.id,),
            )
            await self.conn.commit()
        await ctx.respond("Leave messages enabled.", ephemeral=True)

    @_leave.command(name="disable", description="Disable leave messages")
    @commands.has_permissions(manage_guild=True)
    async def _leave_disable(self, ctx: discord.ApplicationContext):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "UPDATE guilds SET leave_enabled = 0 WHERE guild_id = ?",
                (ctx.guild.id,),
            )
            await self.conn.commit()
        await ctx.respond("Leave messages disabled.", ephemeral=True)

    @_leave.command(name="channel", description="Set the leave channel")
    @commands.has_permissions(manage_guild=True)
    async def _leave_channel(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.Option(
            discord.TextChannel, "Select a channel", autocomplete=channel_autocomplete
        ),
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "UPDATE guilds SET leave_channel = ? WHERE guild_id = ?",
                (channel.id, ctx.guild.id),
            )
            await self.conn.commit()
        await ctx.respond(f"Leave channel set to {channel.mention}.", ephemeral=True)

    @discord.slash_command(name="seticon", description="Set a new guild icon")
    @commands.has_permissions(manage_guild=True)
    async def _set_icon(
        self,
        ctx: discord.ApplicationContext,
        icon_url: discord.Option(str, description="The URL of the icon to set"),
    ):
        async with aiohttp.ClientSession() as session:
            async with session.get(icon_url) as resp:
                if resp.status != 200:
                    return await ctx.respond("Invalid image URL.", ephemeral=True)
                data = await resp.read()
                await ctx.guild.edit(icon=data)
        await ctx.respond("Guild icon updated.", ephemeral=True)

    @discord.slash_command(
        name="setsplash", description="Set a new guild splash background"
    )
    @commands.has_permissions(manage_guild=True)
    async def _set_splash(
        self,
        ctx: discord.ApplicationContext,
        splash_url: discord.Option(str, description="The URL of the splash to set"),
    ):
        async with aiohttp.ClientSession() as session:
            async with session.get(splash_url) as resp:
                if resp.status != 200:
                    return await ctx.respond("Invalid image URL.", ephemeral=True)
                data = await resp.read()
                await ctx.guild.edit(splash=data)
        await ctx.respond("Guild splash updated.", ephemeral=True)

    @discord.slash_command(name="setbanner", description="Set a new guild banner")
    @commands.has_permissions(manage_guild=True)
    async def _set_banner(
        self,
        ctx: discord.ApplicationContext,
        banner_url: discord.Option(str, description="The URL of the banner to set"),
    ):
        async with aiohttp.ClientSession() as session:
            async with session.get(banner_url) as resp:
                if resp.status != 200:
                    return await ctx.respond("Invalid image URL.", ephemeral=True)
                data = await resp.read()
                await ctx.guild.edit(banner=data)
        await ctx.respond("Guild banner updated.", ephemeral=True)

    @discord.slash_command(
        name="pin", description="Pin the most recent message in the channel"
    )
    @commands.has_permissions(manage_messages=True)
    async def _pin(self, ctx: discord.ApplicationContext):
        async for message in ctx.channel.history(limit=1):
            await message.pin()

    @discord.slash_command(
        name="extractstickers",
        description="Sends all of your servers stickers in a zip file",
    )
    @commands.has_permissions(manage_guild=True)
    async def _extract_stickers(self, ctx: discord.ApplicationContext):
        await ctx.defer()
        stickers = await ctx.guild.fetch_stickers()

        if not stickers:
            return await ctx.respond("No stickers found.", ephemeral=True)

        with zipfile.ZipFile("temp/stickers.zip", "w") as zipf:
            for sticker in stickers:
                data = await sticker.read()
                data_file = io.BytesIO(data)
                zipf.writestr(f"{sticker.name}.png", data_file.read())

        await ctx.respond(
            file=discord.File("temp/stickers.zip"), ephemeral=True, delete_after=60
        )

        os.remove("temp/stickers.zip")

    @discord.slash_command(
        name="extractemojis",
        description="Sends all of your servers emojis in a zip file",
    )
    @commands.has_permissions(manage_guild=True)
    async def _extract_emojis(self, ctx: discord.ApplicationContext):
        await ctx.defer()
        emojis = await ctx.guild.fetch_emojis()

        if not emojis:
            return await ctx.respond("No emojis found.", ephemeral=True)

        with zipfile.ZipFile("temp/emojis.zip", "w") as zipf:
            for emoji in emojis:
                data = await emoji.read()
                data_file = io.BytesIO(data)
                zipf.writestr(f"{emoji.name}.png", data_file.read())

        await ctx.respond(
            file=discord.File("temp/emojis.zip"), ephemeral=True, delete_after=60
        )

        os.remove("temp/emojis.zip")

    @discord.slash_command(
        name="snapchat",
        description="Get bitmoji and QR scan code for user",
    )
    async def _snapchat(
        self,
        ctx: discord.ApplicationContext,
        username: discord.Option(
            str, description="The Snapchat username to get the code for"
        ),
    ):
        await ctx.defer()

        snapchat_user = SnapChat(username)
        error = await snapchat_user.check_username()

        if error:
            return await ctx.respond(error, ephemeral=True)

        snapcode_svg, filetype, size = await snapchat_user.get_snapcode(
            bitmoji=True, size=1000
        )

        with open("temp/snapcode.svg", "wb") as file:
            file.write(snapcode_svg)

        with wand.image.Image() as img:
            with wand.color.Color("transparent") as background_color:
                img.read(blob=snapcode_svg, background=background_color)
                img.save(filename="temp/snapcode.png")

        await ctx.respond(file=discord.File("temp/snapcode.png"))

        os.remove("temp/snapcode.svg")
        os.remove("temp/snapcode.png")

    @discord.slash_command(
        name="xbox",
        description="Get Xbox profile for user",
    )
    async def _xbox(
        self,
        ctx: discord.ApplicationContext,
        gamertag: discord.Option(
            str, description="The Xbox gamertag to get the profile for"
        ),
    ):
        await ctx.defer()

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://xbl.io/api/v2/search/{gamertag}",
                headers={"X-Authorization": config["XBOX_LIVE_API_KEY"]},
            ) as resp:
                if resp.status != 200:
                    return await ctx.respond("Invalid gamertag.", ephemeral=True)
                data = await resp.json()

                person = data["people"][0]

                embed = discord.Embed(
                    color=config["COLORS"]["SUCCESS"],
                )

                embed.add_field(name="Gamertag", value=person["gamertag"], inline=True)
                embed.add_field(
                    name="Gamer Score",
                    value=person["gamerScore"],
                    inline=True,
                )
                embed.add_field(
                    name="Account Tier",
                    value=person["detail"]["accountTier"],
                    inline=True,
                )

                embed.add_field(
                    name="Followers",
                    value=person["detail"]["followerCount"],
                    inline=True,
                )
                embed.add_field(
                    name="Following",
                    value=person["detail"]["followingCount"],
                    inline=True,
                )
                embed.add_field(
                    name="Gamepass", value=person["detail"]["hasGamePass"], inline=True
                )

                embed.set_thumbnail(url=person["displayPicRaw"])
                await ctx.respond(embed=embed)

    @discord.slash_command(
        name="server",
        description="Get some information about the server",
    )
    async def _server(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        total_members = len(ctx.guild.members)
        bot_count = sum(member.bot for member in ctx.guild.members)
        online_count = sum(
            member.status != discord.Status.offline for member in ctx.guild.members
        )

        if ctx.guild.id == config["HOME_GUILD"]:
            owner = ctx.guild.get_member(config["OWNER_ID"]).mention
        else:
            owner = ctx.guild.owner

        created = f"<t:{int(ctx.guild.created_at.timestamp())}:R>"
        security = f"Verification Level: {ctx.guild.verification_level}\nExplicit Content Filter: {ctx.guild.explicit_content_filter}"

        text_channels = len(ctx.guild.text_channels)
        voice_channels = len(ctx.guild.voice_channels)
        roles = len(ctx.guild.roles)
        emojis = len(ctx.guild.emojis)

        embed = discord.Embed(title=ctx.guild.name, color=config["COLORS"]["DEFAULT"])
        embed.description = (
            f"\👥 {total_members} members (\🤖 {bot_count} bots) | \🟢 {online_count} online\n\n"
            f"**Owner:** {owner}\n**Created:** {created}\n**Security:** {security}\n\n"
            f"\💬 {text_channels} channels | \🔈 {voice_channels} voice channels | "
            f"\👤 {roles} roles | \🐸 {emojis} emotes"
        )
        embed.set_thumbnail(url=ctx.guild.icon.url)

        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="whois",
        description="Get information about a user.",
    )
    async def user_info(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(
            discord.Member, "The user to get information about", required=False
        ),
    ):
        await ctx.defer()

        user = member or ctx.author

        status = str(user.status).title()
        if status == "Dnd":
            status = "\🔴 DND"
        if status == "Idle":
            status = "\🌙 Idle"
        if status == "Offline":
            status = "\⚫ Offline"
        if status == "Online":
            status = "\🟢 Online"

        created = f"<t:{int(user.created_at.timestamp())}:R>"
        joined = f"<t:{int(user.joined_at.timestamp())}:R>"

        roles = ", ".join(
            [role.mention for role in user.roles if role != ctx.guild.default_role]
        )

        fetched_user = await self.bot.fetch_user(user.id)

        activity_phrase = (
            self.format_activity(user.activities[0]) if user.activities else "None"
        )

        embed = discord.Embed(color=config["COLORS"]["DEFAULT"])
        embed.description = f"{status} {activity_phrase}\n\n"
        embed.add_field(name="Created", value=created, inline=True)
        embed.add_field(name="Joined", value=joined, inline=True)
        embed.add_field(name="Roles", value=roles, inline=False)

        if fetched_user.banner:
            embed.description += f"\n**Banner:** [Link]({fetched_user.banner.url})"
            embed.set_image(url=fetched_user.banner.url)

        embed.set_thumbnail(url=user.display_avatar.url)
        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="statistics", description="Get simple statistics about the server."
    )
    async def _statistics(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        members = ctx.guild.members
        bots = [member for member in members if member.bot]
        online = [
            member for member in members if member.status != discord.Status.offline
        ]

        now = datetime.now(pytz.UTC)
        day_ago = now - timedelta(days=1)
        day_joined = [
            member
            for member in members
            if member.joined_at and member.joined_at.replace(tzinfo=pytz.UTC) > day_ago
        ]

        week_ago = now - timedelta(days=7)
        week_joined = [
            member
            for member in members
            if member.joined_at and member.joined_at.replace(tzinfo=pytz.UTC) > week_ago
        ]

        bans_count = 0
        async for ban in ctx.guild.bans(limit=None):
            bans_count += 1

        embed = discord.Embed(
            description=f"\👥 **{len(members)}** Members | \💚 **{len(online)}** Online | \🤖 **{len(bots)}** Bots",
            color=config["COLORS"]["DEFAULT"],
        )
        embed.add_field(
            name="New Members",
            value=f"\👥 Today: **{len(day_joined)}**\n\👥 This Week: **{len(week_joined)}**",
            inline=False,
        )
        embed.add_field(
            name="Bans and Boosts",
            value=f"\🔨 Bans: **{bans_count}**\n\🚀 Boosts: **{ctx.guild.premium_subscription_count}**",
            inline=False,
        )
        if ctx.guild.splash:
            embed.set_image(url=ctx.guild.splash.url)
        embed.set_thumbnail(url=ctx.guild.icon.url)

        await ctx.respond(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT leave_enabled, leave_channel FROM guilds WHERE guild_id = ?",
                (member.guild.id,),
            )
            row = await cur.fetchone()
            if row is None or not row[0]:
                return

            leave_enabled, leave_channel_id = row
            leave_channel = self.bot.get_channel(leave_channel_id)
            if not leave_channel:
                return

            embed = discord.Embed(
                title="Member Left",
                description=f"{member.mention} has left the server.",
                color=config["COLORS"]["ERROR"],
            )
            embed.set_thumbnail(url=member.avatar.url)
            await leave_channel.send(embed=embed)


def setup(bot_: discord.Bot):
    bot_.add_cog(Server(bot_))
