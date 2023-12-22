import discord
import aiosqlite
import yaml
import asyncio
import concurrent.futures
import time
import aiohttp
import zipfile
import os
import io

from discord.ext import commands
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from helpers.snapchat import *


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

            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await asyncio.get_event_loop().run_in_executor(
                    executor, await run_selenium
                )

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
        channel: discord.Option(description="The channel to send welcome messages in"),
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "UPDATE guilds SET welcome_channel = ? WHERE guild_id = ?",
                (channel.id, ctx.guild.id),
            )
            await self.conn.commit()
        await ctx.respond(f"Welcome channel set to {channel.mention}.", ephemeral=True)

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

        me = SnapChat(username)
        snapcode_svg, filetype = me.get_snapcode(bitmoji=True)

        with open("temp/snapcode.svg", "wb") as file:
            file.write(snapcode_svg)

        doc = aw.Document()
        builder = aw.DocumentBuilder(doc)
        shape = builder.insert_image("temp/snapcode.svg")

        pageSetup = builder.page_setup
        pageSetup.page_width = shape.width
        pageSetup.page_height = shape.height
        pageSetup.top_margin = 0
        pageSetup.left_margin = 0
        pageSetup.bottom_margin = 0
        pageSetup.right_margin = 0

        doc.save("temp/snapcode.png")

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
                    color=int("313338", 16),
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


def setup(bot_: discord.Bot):
    bot_.add_cog(Server(bot_))
