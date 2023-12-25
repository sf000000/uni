import discord
import aiosqlite
import yaml
import json
import os
import datetime
import aiohttp
import ast
import time

from discord.ext import commands
from helpers.utils import iso_to_discord_timestamp, fetch_latest_commit_info, is_premium


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class Developer(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
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
        name="dev", description="Developer related commands."
    )

    @_dev.command(
        name="bye",
        description="Remove the bot from a guild.",
    )
    @commands.is_owner()
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
        await guild.leave()
        await ctx.respond(
            f"Successfully left the guild **{guild.name}** ({guild.id}).",
            ephemeral=True,
        )

    @_dev.command(
        name="eval",
        description="Evaluates Python code.",
    )
    @commands.is_owner()
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
            await ctx.respond(f"```py\n{e}\n```")

    @_dev.command(
        name="rawembed",
        description="Sends an embed from a message as raw JSON.",
    )
    @commands.is_owner()
    async def _rawembed(
        self,
        ctx: discord.ApplicationContext,
        message_id: discord.Option(
            str, "The ID of the message to get the embed from.", required=True
        ),
    ):
        message = await ctx.channel.fetch_message(int(message_id))

        if not message.embeds:
            raise commands.CommandInvokeError("This message does not have an embed.")

        embed = message.embeds[0]
        embed_dict = embed.to_dict()
        embed_json = json.dumps(embed_dict, indent=4)

        await ctx.respond(f"```json\n{embed_json}\n```")

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
            await ctx.respond(f"An error occurred: {e}")

    @_dev.command(name="execute", description="Executes a SQL query.")
    @commands.is_owner()
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
            return await ctx.respond(f"An error occurred: {e}")

    @_dev.command(name="whitelist", description="Whitelists a guild to use the bot.")
    @commands.is_owner()
    async def whitelist(
        self,
        ctx: discord.ApplicationContext,
        guild_id: discord.Option(
            str, "The ID of the guild to whitelist.", required=True
        ),
    ):
        try:
            async with self.conn.cursor() as cur:
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS whitelisted_guilds (guild_id TEXT)"
                )
                await cur.execute(
                    "SELECT 1 FROM whitelisted_guilds WHERE guild_id = ?", (guild_id,)
                )
                if await cur.fetchone():
                    return await ctx.respond(
                        embed=discord.Embed(
                            description=f"The guild `{guild_id}` is already whitelisted.",
                            color=config["COLORS"]["ERROR"],
                        )
                    )

                await cur.execute(
                    "INSERT INTO whitelisted_guilds (guild_id) VALUES (?)", (guild_id,)
                )
                await self.conn.commit()

            return await ctx.respond(
                embed=discord.Embed(
                    description=f"The guild `{guild_id}` has been whitelisted.",
                    color=config["COLORS"]["SUCCESS"],
                )
            )
        except Exception as e:
            await ctx.respond(f"Error occurred: {e}")

    @_dev.command(
        name="unwhitelist", description="Unwhitelists a guild from using the bot."
    )
    @commands.is_owner()
    async def unwhitelist(
        self,
        ctx: discord.ApplicationContext,
        guild_id: discord.Option(
            str, "The ID of the guild to unwhitelist.", required=True
        ),
    ):
        try:
            async with self.conn.cursor() as cur:
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS whitelisted_guilds (guild_id TEXT)"
                )
                await cur.execute(
                    "SELECT 1 FROM whitelisted_guilds WHERE guild_id = ?", (guild_id,)
                )
                if not await cur.fetchone():
                    return await ctx.respond(
                        embed=discord.Embed(
                            description=f"The guild `{guild_id}` is not whitelisted.",
                            color=config["COLORS"]["ERROR"],
                        )
                    )

                await cur.execute(
                    "DELETE FROM whitelisted_guilds WHERE guild_id = ?", (guild_id,)
                )
                await self.conn.commit()

            return await ctx.respond(
                embed=discord.Embed(
                    description=f"The guild `{guild_id}` has been unwhitelisted.",
                    color=config["COLORS"]["SUCCESS"],
                )
            )
        except Exception as e:
            await ctx.respond(f"Error occurred: {e}")

    @_dev.command(
        name="status",
        description="Set bot's playing status.",
    )
    @commands.is_owner()
    async def _status(
        self,
        ctx: discord.ApplicationContext,
        status: discord.Option(
            str, "The status to set the bot's playing status to.", required=True
        ),
    ):
        await self.bot.change_presence(activity=discord.Game(name=status))

    @_dev.command(
        name="reload",
        description="Reloads an extension.",
    )
    @commands.is_owner()
    async def _reload(
        self,
        ctx: discord.ApplicationContext,
        extension: discord.Option(str, "The extension to reload.", required=True),
    ):
        self.bot.reload_extension(f"extensions.{extension}")
        await ctx.respond("\✅")

    @_dev.command(
        name="load",
        description="Loads an extension.",
    )
    @commands.is_owner()
    async def _load(
        self,
        ctx: discord.ApplicationContext,
        extension: discord.Option(str, "The extension to load.", required=True),
    ):
        self.bot.load_extension(f"extensions.{extension}")
        await ctx.respond("\✅")

    @_dev.command(
        name="unload",
        description="Unloads an extension.",
    )
    @commands.is_owner()
    async def _unload(
        self,
        ctx: discord.ApplicationContext,
        extension: discord.Option(str, "The extension to unload.", required=True),
    ):
        self.bot.unload_extension(f"extensions.{extension}")
        await ctx.respond("\✅")

    @_dev.command(
        name="reloadall",
        description="Reloads all extensions.",
    )
    @commands.is_owner()
    async def _reloadall(self, ctx: discord.ApplicationContext):
        reloaded_extensions = 0
        for filename in os.listdir("./extensions"):
            if filename.endswith(".py"):
                self.bot.reload_extension(f"extensions.{filename[:-3]}")
                reloaded_extensions += 1

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
            embed = discord.Embed(
                description=f"Commit message: {commit_info['message']}",
                color=config["COLORS"]["DEFAULT"],
            )
            embed.add_field(
                name="Commit",
                value=f"[{commit_info['id'][:7]}]({commit_info['url']})",
            )
            embed.add_field(name="Author", value=commit_info["author"])
            embed.add_field(
                name="Date", value=iso_to_discord_timestamp(commit_info["date"])
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
            await ctx.respond(f"Error occurred: {e}")

    @discord.slash_command(
        name="botpfp",
        description="Changes the bot's profile picture.",
    )
    @commands.is_owner()
    async def _botpfp(
        self,
        ctx: discord.ApplicationContext,
        image_url: discord.Option(
            str,
            "The URL of the image to set the bot's profile picture to.",
            required=True,
        ),
    ):
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    return await ctx.respond(
                        embed=discord.Embed(
                            description="Invalid image URL.",
                            color=config["COLORS"]["ERROR"],
                        )
                    )

                image_bytes = await resp.read()

        try:
            await self.bot.user.edit(avatar=image_bytes)
            await ctx.respond(
                embed=discord.Embed(
                    description="Successfully changed the bot's profile picture.",
                    color=config["COLORS"]["SUCCESS"],
                )
            )
        except Exception as e:
            await ctx.respond(f"Error occurred: {e}")

    @_dev.command(
        name="shards",
        description="Gets the current shards.",
    )
    @commands.is_owner()
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

    @commands.Cog.listener()
    async def on_application_command_completion(self, ctx: discord.ApplicationContext):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO command_usage (command, user_id, guild_id) VALUES (?, ?, ?)",
                (str(ctx.command), str(ctx.author.id), str(ctx.guild.id)),
            )
            await self.conn.commit()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        try:
            async with self.conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM whitelisted_guilds WHERE guild_id = ?",
                    (str(guild.id),),
                )
                if not await cur.fetchone():
                    await guild.leave()
        except Exception as e:
            print(f"Error occurred during guild join: {e}")


def setup(bot_: discord.Bot):
    bot_.add_cog(Developer(bot_))
