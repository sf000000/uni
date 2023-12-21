import discord
import aiosqlite
import yaml
import json
import os

from discord.ext import commands
from openai import OpenAI
from helpers.utils import fetch_latest_commit_info, iso_to_discord_timestamp


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
        self.client = OpenAI(api_key=config["OPENAI_API_KEY"])
        self.conversation_histories = {}

    async def setup_db(self):
        self.conn = await aiosqlite.connect(self.db_path)
        await self._create_tables()

    async def _create_tables(self):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "CREATE TABLE IF NOT EXISTS disabled_commands (command TEXT)"
            )
        await self.conn.commit()

    async def cog_unload(self):
        await self.conn.close()

    _dev = discord.commands.SlashCommandGroup(
        name="developer", description="Developer related commands."
    )

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

    @discord.slash_command(
        name="chat",
        description="Chat with Uni.",
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def chat(
        self,
        ctx: discord.ApplicationContext,
        message: discord.Option(str, "The message to send to Uni.", required=True),
    ):
        await ctx.defer()

        user_id = ctx.author.id
        user_history = self.conversation_histories.setdefault(user_id, [])
        user_history.append({"role": "user", "content": message})

        prompt = f"Q: {message}\nA:"
        chat_completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=user_history + [{"role": "system", "content": prompt}],
        )

        bot_response = chat_completion.choices[0].message.content
        user_history.append({"role": "assistant", "content": bot_response})
        history_length = len(user_history) // 2

        clear_history_button = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            label=f"Clear History ({history_length})",
            custom_id="clear_message_history",
        )
        clear_history_button.callback = self._clear_message_history_callback
        view = discord.ui.View(clear_history_button)

        await ctx.respond(bot_response, view=view)

    async def _clear_message_history_callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        self.conversation_histories[user_id] = []
        await interaction.response.edit_message(
            content="Message history cleared.", view=None
        )

    @_dev.command(name="execute", description="Executes a SQL query.")
    async def execute(
        self,
        ctx: discord.ApplicationContext,
        query: discord.Option(str, "The SQL query to execute.", required=True),
    ):
        if ctx.author.id != config["OWNER_ID"]:
            raise commands.CommandInvokeError(
                "You are not allowed to use this command."
            )

        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                result = cur.fetchall()
                formatted_result = "\n".join(str(row) for row in result)
                await ctx.respond(f"```{formatted_result}```")
        except Exception as e:
            await ctx.respond(f"Error executing query: {e}")

    @_dev.command(name="whitelist", description="Whitelists a guild to use the bot.")
    async def whitelist(
        self,
        ctx: discord.ApplicationContext,
        guild_id: discord.Option(
            str, "The ID of the guild to whitelist.", required=True
        ),
    ):
        if ctx.author.id != config["OWNER_ID"]:
            raise commands.CommandInvokeError(
                "You are not allowed to use this command."
            )

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
        if ctx.author.id != config["OWNER_ID"]:
            raise commands.CommandInvokeError(
                "You are not allowed to use this command."
            )

        await self.bot.change_presence(activity=discord.Game(name=status))

    @_dev.command(
        name="reload",
        description="Reloads an extension.",
    )
    async def _reload(
        self,
        ctx: discord.ApplicationContext,
        extension: discord.Option(str, "The extension to reload.", required=True),
    ):
        if ctx.author.id != config["OWNER_ID"]:
            raise commands.CommandInvokeError(
                "You are not allowed to use this command."
            )

        self.bot.reload_extension(f"extensions.{extension}")
        await ctx.respond("\✅")

    @_dev.command(
        name="load",
        description="Loads an extension.",
    )
    async def _load(
        self,
        ctx: discord.ApplicationContext,
        extension: discord.Option(str, "The extension to load.", required=True),
    ):
        if ctx.author.id != config["OWNER_ID"]:
            raise commands.CommandInvokeError(
                "You are not allowed to use this command."
            )

        self.bot.load_extension(f"extensions.{extension}")
        await ctx.respond("\✅")

    @_dev.command(
        name="unload",
        description="Unloads an extension.",
    )
    async def _unload(
        self,
        ctx: discord.ApplicationContext,
        extension: discord.Option(str, "The extension to unload.", required=True),
    ):
        if ctx.author.id != config["OWNER_ID"]:
            raise commands.CommandInvokeError(
                "You are not allowed to use this command."
            )

        self.bot.unload_extension(f"extensions.{extension}")
        await ctx.respond("\✅")

    @_dev.command(
        name="reloadall",
        description="Reloads all extensions.",
    )
    async def _reloadall(self, ctx: discord.ApplicationContext):
        if ctx.author.id != config["OWNER_ID"]:
            raise commands.CommandInvokeError(
                "You are not allowed to use this command."
            )

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

    @_dev.command(
        name="version",
        description="Gets the current version of the bot.",
    )
    async def _version(self, ctx: discord.ApplicationContext):
        commit_info = await fetch_latest_commit_info()
        if isinstance(commit_info, str):  # If it's an error message
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
