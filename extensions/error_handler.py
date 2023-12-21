import discord
import yaml
from discord.ext import commands


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class ErrorHandler(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_application_command_error(
        self, ctx: discord.ApplicationContext, error: discord.DiscordException
    ):
        if await self.handle_common_errors(ctx, error):
            return
        if isinstance(error, commands.CommandNotFound):
            await ctx.respond(
                "The command you tried to use does not exist. Please check the command name and try again.",
                ephemeral=True,
            )
        elif isinstance(error, commands.DisabledCommand):
            await ctx.respond(
                "This command is currently disabled and cannot be used.", ephemeral=True
            )
        else:
            raise error

    async def handle_common_errors(
        self, ctx: discord.ApplicationContext, error: discord.DiscordException
    ):
        if isinstance(
            error,
            (
                commands.UserInputError,
                commands.ConversionError,
                commands.ArgumentParsingError,
            ),
        ):
            await ctx.respond(
                "There was an error with your input. Please check the command format and try again.",
                ephemeral=True,
            )
            return True
        if isinstance(error, commands.CheckFailure):
            await ctx.respond(
                "You do not meet the requirements to use this command.", ephemeral=True
            )
            return True
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.respond(
                "This command cannot be used in private messages.", ephemeral=True
            )
            return True
        if isinstance(error, commands.NotOwner):
            await ctx.respond(
                "This command can only be used by the bot owner.", ephemeral=True
            )
            return True
        if isinstance(error, commands.MissingPermissions):
            await ctx.respond(
                "You do not have the required permissions to use this command.",
                ephemeral=True,
            )
            return True
        if isinstance(error, commands.BotMissingPermissions):
            await ctx.respond(
                "I do not have the required permissions to use this command.",
                ephemeral=True,
            )
            return True
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.respond(
                f"This command is on cooldown. Please try again in {error.retry_after:.2f} seconds.",
                ephemeral=True,
            )
            return True

        return False


def setup(bot: discord.Bot):
    bot.add_cog(ErrorHandler(bot))
