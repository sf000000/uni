import discord
import aiosqlite
import asyncio
import yaml
import os
import datetime
import ast
import time
import re
import pandas as pd
import base64
import json

from matplotlib import pyplot as plt
from discord.ext import commands
from helpers.utils import (
    iso_to_discord_timestamp,
    fetch_latest_commit_info,
    create_bar_chart,
    set_seaborn_style,
)
from helpers import emojis
from playwright.async_api import async_playwright


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


commit_emojis = {
    "feat": "✨",
    "fix": "🐛",
    "docs": "📚",
    "style": "💅",
    "refactor": "🔨",
    "test": "🧪",
    "chore": "🧹",
}


def replace_commit_type_with_emoji(commit_msg):
    commit_msg = commit_msg.lstrip("* ").strip()

    if match := re.match(
        r"(feat|fix|docs|style|refactor|test|chore)\((.*?)\):(.*)", commit_msg
    ):
        commit_type = match[1]
        extension_name = match[2]
        description = match[3]

        if extension_name.endswith(".py"):
            extension_name = f"**{extension_name}**"

        if commit_type in commit_emojis:
            return f"{commit_emojis[commit_type]}: ({extension_name}):{description}"

    return commit_msg


config = load_config()


class LogsPaginator(discord.ui.View):
    def __init__(self, pages: list[str]):
        super().__init__()
        self.pages = pages
        self.current_page = 0

    @discord.ui.button(emoji=emojis._prev, style=discord.ButtonStyle.gray)
    async def previous(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.current_page == 0:
            return

        self.current_page -= 1
        await self.update_page(interaction)

    @discord.ui.button(emoji=emojis._next, style=discord.ButtonStyle.gray)
    async def next(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.current_page == len(self.pages) - 1:
            return

        self.current_page += 1
        await self.update_page(interaction)

    @discord.ui.button(label="Clear Logs", style=discord.ButtonStyle.red)
    async def clear(self, button: discord.ui.Button, interaction: discord.Interaction):
        with open("bot.log", "w", encoding="utf-8") as f:
            f.write("")

        await interaction.response.edit_message(content="Cleared logs.", view=None)

    async def update_page(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content=f"```py\n{self.pages[self.current_page]}```"
        )


class Developer(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.log = bot_.log
        self.db_path = "kino.db"
        self.bot.loop.create_task(self.setup_db())

    async def setup_db(self):
        self.conn = await aiosqlite.connect(self.db_path)
        await self._create_tables()

    async def _create_tables(self):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "CREATE TABLE IF NOT EXISTS disabled_commands (command TEXT)"
            )
        await self.conn.commit()

    async def format_column(self, task_list, guild):
        if not task_list:
            return "```No Tasks```"
        lines = [
            f"{idx + 1} - {task[1].capitalize()}" for idx, task in enumerate(task_list)
        ]
        return "```" + "\n".join(lines) + "```"

    def insert_returns(self, body: list):
        if isinstance(body[-1], ast.Expr):
            body[-1] = ast.Return(body[-1].value)
            ast.fix_missing_locations(body[-1])

        if isinstance(body[-1], (ast.If, ast.With)):
            self.insert_returns(body[-1].body)
            if isinstance(body[-1], ast.If):
                self.insert_returns(body[-1].orelse)

    _dev = discord.commands.SlashCommandGroup(
        name="dev",
        description="Developer related commands.",
        checks=[commands.is_owner().predicate],
    )

    @_dev.command(
        name="bye",
        description="Remove the bot from a guild.",
    )
    async def _bye(
        self,
        ctx: discord.ApplicationContext,
        guild_id: discord.Option(
            str, "The ID of the guild to remove the bot from.", required=True
        ),
    ):
        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return await ctx.respond(
                "Could not find a guild with that ID.", ephemeral=True
            )
        try:
            await guild.leave()
        except Exception as e:
            self.log.error(f"Failed to leave guild: {e}")
        await ctx.respond(
            f"Successfully left the guild **{guild.name}** ({guild.id}).",
            ephemeral=True,
        )

    @_dev.command(
        name="eval",
        description="Evaluates Python code.",
    )
    async def _eval(
        self,
        ctx: discord.ApplicationContext,
        code: discord.Option(str, "The Python code to evaluate.", required=True),
    ):
        fn_name = "_eval_expr"
        cmd = code.strip("` ")
        cmd = "\n".join(f"    {i}" for i in cmd.splitlines())

        body = f"async def {fn_name}():\n{cmd}"
        parsed = ast.parse(body)
        body = parsed.body[0].body

        self.insert_returns(body)

        env = {
            "bot": self.bot,
            "discord": discord,
            "commands": commands,
            "ctx": ctx,
            "__import__": __import__,
        }

        try:
            start_time = time.perf_counter()
            exec(compile(parsed, filename="<ast>", mode="exec"), env)
            result = await eval(f"{fn_name}()", env)
            end_time = time.perf_counter()
            execution_time = end_time - start_time

            embed = discord.Embed(
                description=f"```py\n{result}\n```",
                color=config["COLORS"]["DEFAULT"],
            )
            embed.add_field(name="Execution Time", value=f"{execution_time:.4f}s")
            await ctx.respond(embed=embed)
        except Exception as e:
            self.log.error(f"Failed to evaluate code: {e}")
            await ctx.respond(f"```py\n{e}\n```")

    @_dev.command(
        name="disablecommand",
        description="Disables a command in the current guild.",
    )
    async def _disablecommand(
        self,
        ctx: discord.ApplicationContext,
        command: discord.Option(
            str, "The name of the command to disable.", required=True
        ),
    ):
        try:
            async with self.conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM disabled_commands WHERE command = ?", (command,)
                )
                if await cur.fetchone():
                    return await ctx.respond(
                        f"The command `{command}` is already disabled."
                    )

                await cur.execute(
                    "INSERT INTO disabled_commands (command) VALUES (?)", (command,)
                )
                await self.conn.commit()
        except Exception as e:
            self.log.error(f"Failed to disable command: {e}")
            return await ctx.respond(f"An error occurred: {e}")

        await ctx.respond(f"Command `{command}` has been disabled.")

    @_dev.command(
        name="enablecommand",
        description="Enables a command in the current guild.",
    )
    async def _enablecommand(
        self,
        ctx: discord.ApplicationContext,
        command: discord.Option(
            str, "The name of the command to enable.", required=True
        ),
    ):
        try:
            async with self.conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM disabled_commands WHERE command = ?", (command,)
                )
                if not await cur.fetchone():
                    await ctx.respond(f"The command `{command}` is not disabled.")
                    return

                await cur.execute(
                    "DELETE FROM disabled_commands WHERE command = ?", (command,)
                )
                await self.conn.commit()

            await ctx.respond(f"Command `{command}` has been enabled.")
        except Exception as e:
            self.log.error(f"Failed to enable command: {e}")
            await ctx.respond(f"An error occurred: {e}")

    @_dev.command(name="execute", description="Executes a SQL query.")
    async def execute(
        self,
        ctx: discord.ApplicationContext,
        query: discord.Option(str, "The SQL query to execute.", required=True),
    ):
        try:
            async with self.conn.cursor() as cur:
                await cur.execute(query)
                await self.conn.commit()
                await ctx.respond("Query executed.")
        except Exception as e:
            self.lgo.error(f"Failed to execute query: {e}")
            return await ctx.respond(f"An error occurred: {e}")

    @_dev.command(
        name="status",
        description="Set bot's playing status.",
    )
    async def _status(
        self,
        ctx: discord.ApplicationContext,
        status: discord.Option(
            str, "The status to set the bot's playing status to.", required=True
        ),
    ):
        try:
            await self.bot.change_presence(activity=discord.Game(name=status))
        except Exception as e:
            self.log.error(f"Failed to set status: {e}")
            await ctx.respond(f"An error occurred: {e}")

    @_dev.command(
        name="reload",
        description="Reloads an extension.",
    )
    async def _reload(
        self,
        ctx: discord.ApplicationContext,
        extension: discord.Option(str, "The extension to reload.", required=True),
    ):
        if not os.path.exists(f"./extensions/{extension}.py"):
            return await ctx.respond(f"Extension `{extension}` does not exist.")

        try:
            self.bot.reload_extension(f"extensions.{extension}")
            await ctx.respond("\✅")
        except Exception as e:
            self.log.error(f"Failed to reload extension: {e}")

    @_dev.command(
        name="load",
        description="Loads an extension.",
    )
    async def _load(
        self,
        ctx: discord.ApplicationContext,
        extension: discord.Option(str, "The extension to load.", required=True),
    ):
        try:
            self.bot.load_extension(f"extensions.{extension}")
            await ctx.respond("\✅")
        except Exception as e:
            self.log.error(f"Failed to load extension: {e}")

    @_dev.command(
        name="unload",
        description="Unloads an extension.",
    )
    async def _unload(
        self,
        ctx: discord.ApplicationContext,
        extension: discord.Option(str, "The extension to unload.", required=True),
    ):
        try:
            self.bot.unload_extension(f"extensions.{extension}")
            await ctx.respond("\✅")
        except Exception as e:
            self.log.error(f"Failed to unload extension: {e}")

    @_dev.command(
        name="reloadall",
        description="Reloads all extensions.",
    )
    async def _reloadall(self, ctx: discord.ApplicationContext):
        reloaded_extensions = 0
        for filename in os.listdir("./extensions"):
            if filename.endswith(".py"):
                try:
                    self.bot.reload_extension(f"extensions.{filename[:-3]}")
                    reloaded_extensions += 1
                except Exception as e:
                    self.log.error(f"Failed to reload {filename}: {e}")

        await ctx.respond(
            embed=discord.Embed(
                description=f"Reloaded {reloaded_extensions} extensions.",
                color=config["COLORS"]["SUCCESS"],
            )
        )

    @discord.slash_command(
        name="version",
        description="Gets the current version of the bot.",
    )
    async def _version(self, ctx: discord.ApplicationContext):
        commit_info = await fetch_latest_commit_info()
        if isinstance(commit_info, str):
            await ctx.respond(commit_info)
        else:
            embed = discord.Embed(color=config["COLORS"]["DEFAULT"])
            commit_messages = commit_info["message"].split("\n")
            emoji_commit_messages = [
                replace_commit_type_with_emoji(msg) for msg in commit_messages
            ]
            full_modified_commit_msg = "\n".join(emoji_commit_messages)

            embed.description = full_modified_commit_msg
            embed.add_field(
                name="Version", value=f"[{commit_info['id'][:7]}]({commit_info['url']})"
            )
            embed.add_field(name="Author", value=commit_info["author"])
            embed.add_field(
                name="Time", value=iso_to_discord_timestamp(commit_info["date"])
            )
            await ctx.respond(embed=embed)

    @discord.slash_command(
        name="givepremium",
        description="Gives a user premium.",
    )
    @commands.is_owner()
    async def _givepremium(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(
            discord.Member, "The user to give premium to.", required=True
        ),
    ):
        try:
            async with self.conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO premium_users (user_id, user_name, premium_granted_timestamp) VALUES (?, ?, ?)",
                    (
                        user.id,
                        user.name,
                        datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    ),
                )
                await self.conn.commit()

            await ctx.respond(
                embed=discord.Embed(
                    description=f"{user.mention} has been upgraded to premium status. All premium features are now available.",
                    color=config["COLORS"]["SUCCESS"],
                )
            )
        except Exception as e:
            self.log.error(f"Failed to give premium: {e}")
            await ctx.respond(f"Error occurred: {e}")

    @discord.slash_command(
        name="removepremium",
        description="Removes a user's premium.",
    )
    @commands.is_owner()
    async def _removepremium(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(
            discord.Member, "The user to remove premium from.", required=True
        ),
    ):
        try:
            async with self.conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM premium_users WHERE user_id = ?", (user.id,)
                )
                await self.conn.commit()

            await ctx.respond(
                embed=discord.Embed(
                    description=f"{user.mention} has been downgraded to standard status. All premium features are now unavailable.",
                    color=config["COLORS"]["SUCCESS"],
                )
            )
        except Exception as e:
            self.log.error(f"Failed to remove premium: {e}")
            await ctx.respond(f"Error occurred: {e}")

    @discord.slash_command(
        name="premiumstatus",
        description="Checks a user's premium status.",
    )
    @commands.is_owner()
    async def _premiumstatus(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(
            discord.Member, "The user to check premium status for.", required=True
        ),
    ):
        try:
            async with self.conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM premium_users WHERE user_id = ?", (user.id,)
                )
                if await cur.fetchone():
                    return await ctx.respond(
                        embed=discord.Embed(
                            description=f"{user.mention} is a premium user.",
                            color=config["COLORS"]["DEFAULT"],
                        )
                    )

            await ctx.respond(
                embed=discord.Embed(
                    description=f"{user.mention} is not a premium user.",
                    color=config["COLORS"]["DEFAULT"],
                )
            )
        except Exception as e:
            self.log.error(f"Failed to check premium status: {e}")
            await ctx.respond(f"Error occurred: {e}")

    @_dev.command(
        name="shards",
        description="Gets the current shards.",
    )
    async def _shards(self, ctx: discord.ApplicationContext):
        shard_lines = [
            f"Shard {shard_id} - {shard.latency * 1000:.2f}ms"
            for shard_id, shard in self.bot.shards.items()
        ]

        await ctx.respond(
            embed=discord.Embed(
                description="\n".join(shard_lines),
                color=config["COLORS"]["DEFAULT"],
            )
        )

    @_dev.command(
        name="usage",
        description="Shows a bar graph of command usage.",
    )
    async def usage(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        query = "SELECT command, COUNT(*) FROM command_usage GROUP BY command"

        async with self.conn.cursor() as cur:
            await cur.execute(query)
            results = await cur.fetchall()

        if not results:
            return await ctx.respond("No commands have been used.")

        command_usage = [
            {"name": f"/{command}", "size": count} for command, count in results
        ]
        command_usage = sorted(command_usage, key=lambda x: x["size"], reverse=True)[
            :20
        ]

        background_color = "#2F195F"
        grid_color = "#582FB1"
        text_color = "#eee"
        font_family = "sans-serif"

        set_seaborn_style(font_family, background_color, grid_color, text_color)

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.set_title("Command Usage")
        ax.set_xlabel("Times Used")
        ax.set_ylabel("Command")
        ax.set_facecolor(background_color)
        ax.grid(color=grid_color)
        ax.tick_params(axis="x", colors=text_color)
        ax.tick_params(axis="y", colors=text_color)

        ax = create_bar_chart(
            pd.Series(
                [cmd["size"] for cmd in command_usage],
                index=[cmd["name"] for cmd in command_usage],
            ),
            ax,
        )

        plt.tight_layout()

        filename = "command_usage.png"
        plt.savefig(filename, facecolor=background_color)

        await ctx.respond(file=discord.File(filename))
        os.remove(filename)

    @_dev.command(
        name="logs",
        description="Shows the bot's logs.",
    )
    async def _logs(self, ctx: discord.ApplicationContext):
        with open("bot.log", "r", encoding="utf-8") as f:
            logs = f.read()

        if not logs:
            return await ctx.respond("Logs are empty.", ephemeral=True)

        logs = logs.split("\n")
        logs.reverse()

        pages = []
        for i in range(0, len(logs), 10):
            pages.append("\n".join(logs[i : i + 10]))

        view = LogsPaginator(pages)
        await ctx.respond(content=f"```py\n{pages[0]}```", view=view)

    @_dev.command(
        name="test",
        description="Test command.",
    )
    async def _test(self, ctx: discord.ApplicationContext, member: discord.Member):
        if not member:
            member = ctx.author

        member_count = ctx.guild.member_count

        data = {
            "memberCount": member_count,
            "member": {
                "id": str(member.id),
                "username": member.name,
                "avatar": (
                    member.avatar.url if member.avatar else member.default_avatar.url
                ),
                "createdAt": member.created_at.isoformat(),
                "joinedAt": member.joined_at.isoformat(),
                "banner": member.banner.url if member.banner else None,
            },
        }
        data = json.dumps(data)
        data = base64.b64encode(data.encode("utf-8")).decode("utf-8")

        url = f"https://uni-ui-nine.vercel.app/welcome?data={data}"

        await ctx.defer()
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(
                device_scale_factor=4.0, viewport={"width": 800, "height": 600}
            )
            await page.goto(url)
            await page.wait_for_selector("img")  # Wait for the image to load

            card = page.locator(".card")

            await asyncio.sleep(5)
            await card.screenshot(path="temp/welcome.png", type="jpeg", quality=100)
            await browser.close()

        await ctx.respond(file=discord.File("temp/welcome.png"))
        os.remove("temp/welcome.png")

    @commands.Cog.listener()
    async def on_application_command_completion(self, ctx: discord.ApplicationContext):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO command_usage (command, user_id, guild_id) VALUES (?, ?, ?)",
                (str(ctx.command), str(ctx.author.id), str(ctx.guild.id)),
            )
            await self.conn.commit()


def setup(bot_: discord.Bot):
    bot_.add_cog(Developer(bot_))
