import os

import discord
from discord.ext import commands

from helpers.embeds import Embeds
from helpers.utils import commit_to_emoji, iso_to_discord, latest_commit


class Developer(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.log = bot.log
        self.config = bot.config
        self.db = bot.db
        self.embed = Embeds()

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
        guild_id: discord.Option(str, "The ID of the guild to leave.", required=True),
    ):
        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return await ctx.respond(
                embed=self.embed.error("Guild not found.", ephemeral=True)
            )
        try:
            await guild.leave()
        except Exception as e:
            self.log.error(f"Failed to leave guild: {e}")
        await ctx.respond(
            embed=self.embed.success(f"Left guild {guild.name}.", ephemeral=True),
            ephemeral=True,
        )

    @_dev.command(
        name="enablecommand",
        description="Re-enables a previously disabled command in the current guild.",
    )
    async def _enablecommand(
        self,
        ctx: discord.ApplicationContext,
        command: discord.Option(
            str, "The name of the command to enable.", required=True
        ),
    ):
        try:
            disabled_commands = self.db["disabled_commands"]
            if not await disabled_commands.find_one({"command": command}):
                return await ctx.respond(
                    embed=self.embed.error("Command is not disabled."),
                    ephemeral=True,
                )

            await disabled_commands.delete_one({"command": command})
        except Exception as e:
            self.log.error(f"Failed to enable command: {e}")
            return await ctx.respond(
                embed=self.embed.error("An error occurred."),
                ephemeral=True,
            )

        await ctx.respond(
            embed=self.embed.success(f"Command `{command}` has been enabled."),
            ephemeral=True,
        )

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
            await ctx.respond(
                embed=self.embed.success(f"Set status to `{status}`."),
                ephemeral=True,
            )
        except Exception as e:
            self.log.error(f"Failed to set status: {e}")
            await ctx.respond(
                embed=self.embed.error("An error occurred."),
                ephemeral=True,
            )

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
            await ctx.respond(
                embed=self.embed.error(f"Failed to reload extension: {e}"),
                ephemeral=True,
            )

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
            await ctx.respond(
                embed=self.embed.error(f"Failed to load extension: {e}"),
                ephemeral=True,
            )

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
            await ctx.respond(
                embed=self.embed.error(f"Failed to unload extension: {e}"),
                ephemeral=True,
            )

    @_dev.command(
        name="reloadall",
        description="Reloads all extensions.",
    )
    async def _reloadall(self, ctx: discord.ApplicationContext):
        loaded_extensions = set(self.bot.extensions.keys())
        available_extensions = set(
            f"extensions.{filename[:-3]}"
            for filename in os.listdir("./extensions")
            if filename.endswith(".py")
        )
        failed_extensions = []
        reloaded_extensions = 0

        for extension in available_extensions:
            try:
                self.bot.reload_extension(extension)
                reloaded_extensions += 1
            except Exception as e:
                self.log.error(f"Failed to reload {extension}: {e}")
                failed_extensions.append(extension)

        embed = self.embed.info(
            f"Reloaded {reloaded_extensions} extensions out of {len(available_extensions)}."
        )

        if failed_extensions:
            embed.add_field(
                name="Failed to reload:",
                value="\n".join(failed_extensions),
                inline=False,
            )

        not_loaded_extensions = available_extensions - loaded_extensions
        if not_loaded_extensions:
            embed.add_field(
                name="Available but not loaded:",
                value="\n".join(not_loaded_extensions),
                inline=False,
            )

        await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(
        name="version",
        description="Gets the current version of the bot.",
    )
    async def _version(self, ctx: discord.ApplicationContext):
        commit_info = await latest_commit()
        if isinstance(commit_info, str):
            await ctx.respond(commit_info)
        else:
            embed = discord.Embed(color=self.config["colors"]["default"])
            commit_messages = commit_info["message"].split("\n")
            emoji_commit_messages = [commit_to_emoji(msg) for msg in commit_messages]
            full_modified_commit_msg = "\n".join(emoji_commit_messages)

            embed.description = full_modified_commit_msg
            embed.add_field(
                name="Version", value=f"[{commit_info['id'][:7]}]({commit_info['url']})"
            )
            embed.add_field(name="Author", value=commit_info["author"])
            embed.add_field(name="Time", value=iso_to_discord(commit_info["date"]))
            await ctx.respond(embed=embed)

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
                color=self.config["colors"]["default"],
            )
        )


def setup(bot_: discord.Bot):
    bot_.add_cog(Developer(bot_))
