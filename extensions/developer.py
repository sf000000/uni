import discord
import aiosqlite
import yaml
import json
import os
import datetime
import openai

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
        self.open_ai = openai.OpenAI(api_key=config["OPENAI_API_KEY"])
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

    async def format_column(self, task_list, guild):
        if not task_list:
            return "```No Tasks```"
        lines = []
        for idx, task in enumerate(task_list):
            member = guild.get_member(int(task[3]))
            display_name = member.display_name if member else "Unknown member"
            lines.append(f'{idx + 1} - "{task[1]}" added by: {display_name}')
        return "```" + "\n".join(lines) + "```"

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
        if not await is_premium(
            ctx.author,
            self.conn,
        ):
            return await ctx.respond(
                embed=discord.Embed(
                    description="This command is only available to premium users.",
                    color=config["COLORS"]["ERROR"],
                )
            )

        await ctx.defer()

        user_id = ctx.author.id
        user_history = self.conversation_histories.setdefault(user_id, [])
        user_history.append({"role": "user", "content": message})

        prompt = f"Q: {message}\nA:"
        chat_completion = self.open_ai.chat.completions.create(
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

    _kanban = discord.commands.SlashCommandGroup(
        name="kanban", description="Kanban related commands."
    )

    @_kanban.command(
        name="add",
        description="Adds a task to the kanban board.",
    )
    @commands.is_owner()
    async def _add(
        self,
        ctx: discord.ApplicationContext,
        description: discord.Option(
            str, "The description of the task to add.", required=True
        ),
        position: discord.Option(
            str,
            "The position to add the task to.",
            required=True,
            choices=[
                discord.OptionChoice(name="Backlog", value="backlog"),
                discord.OptionChoice(name="In Progress", value="in_progress"),
                discord.OptionChoice(name="Completed", value="completed"),
            ],
        ),
    ):
        try:
            async with self.conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO kanban_tasks (description, status, added_by) VALUES (?, ?, ?)",
                    (description, position, str(ctx.author.id)),
                )
                await self.conn.commit()
        except Exception as e:
            return await ctx.respond(f"An error occurred: {e}")
        embed = discord.Embed(
            description=f"**{description}** has been added to the {position.title()} column by {ctx.author.mention}.",
            color=config["COLORS"]["SUCCESS"],
        )
        await ctx.respond(embed=embed)

    @_kanban.command(
        name="view",
        description="View the kanban board.",
    )
    @commands.is_owner()
    async def _view(self, ctx: discord.ApplicationContext):
        async with self.conn.cursor() as cur:
            await cur.execute("SELECT * FROM kanban_tasks ORDER BY task_id")
            tasks = await cur.fetchall()

        backlog_tasks = [task for task in tasks if task[2] == "backlog"]
        in_progress_tasks = [task for task in tasks if task[2] == "in_progress"]
        completed_tasks = [task for task in tasks if task[2] == "completed"]

        embed = discord.Embed(color=3447003)
        embed.add_field(
            name="Project Backlog",
            value=await self.format_column(backlog_tasks, ctx.guild),
            inline=False,
        )
        embed.add_field(
            name="In Progress",
            value=await self.format_column(in_progress_tasks, ctx.guild),
            inline=False,
        )
        embed.add_field(
            name="Completed Tasks",
            value=await self.format_column(completed_tasks, ctx.guild),
            inline=False,
        )

        await ctx.respond(embed=embed)

    @_kanban.command(
        name="move",
        description="Moves a task on the kanban board.",
    )
    @commands.is_owner()
    async def _move(
        self,
        ctx: discord.ApplicationContext,
        task_description: discord.Option(
            str, "The description of the task to move.", required=True
        ),
        new_position: discord.Option(
            str,
            "The new position to move the task to.",
            required=True,
            choices=[
                discord.OptionChoice(name="Backlog", value="backlog"),
                discord.OptionChoice(name="In Progress", value="in_progress"),
                discord.OptionChoice(name="Completed", value="completed"),
            ],
        ),
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM kanban_tasks WHERE description = ?", (task_description,)
            )
            task = await cur.fetchone()

            if not task:
                return await ctx.respond(
                    embed=discord.Embed(
                        description="Task not found.",
                        color=config["COLORS"]["ERROR"],
                    )
                )

            await cur.execute(
                "UPDATE kanban_tasks SET status = ? WHERE task_id = ?",
                (new_position, task[0]),
            )
            await self.conn.commit()

        embed = discord.Embed(
            description="Moved task on board.",
            color=config["COLORS"]["SUCCESS"],
        )
        embed.add_field(name="Description", value=task_description)
        embed.add_field(name="New Status", value=new_position)
        await ctx.respond(embed=embed)

    @_kanban.command(
        name="delete",
        description="Deletes a task from the kanban board.",
    )
    @commands.is_owner()
    async def _delete(
        self,
        ctx: discord.ApplicationContext,
        task_description: discord.Option(
            str, "The description of the task to delete.", required=True
        ),
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM kanban_tasks WHERE description = ?", (task_description,)
            )
            task = await cur.fetchone()

            if not task:
                return await ctx.respond(
                    embed=discord.Embed(
                        description="Task not found.",
                        color=config["COLORS"]["ERROR"],
                    )
                )

            await cur.execute("DELETE FROM kanban_tasks WHERE task_id = ?", (task[0],))
            await self.conn.commit()

        embed = discord.Embed(
            description="Deleted task from board.",
            color=config["COLORS"]["SUCCESS"],
        )
        embed.add_field(name="Description", value=task_description)
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
