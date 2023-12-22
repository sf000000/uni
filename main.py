import discord
import traceback
import yaml

from discord.ext import commands
from colorama import Fore, Style


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class Bot(commands.AutoShardedBot):
    def __init__(self):
        super().__init__(
            command_prefix=config["PREFIX"],
            case_insensitive=True,
            intents=discord.Intents.all(),
            activity=discord.Game(name=config["STATUS"]),
            status=config["STATUS_TYPE"],
        )

        self.inital_extensions = [
            "extensions.information",
            "extensions.server",
            "extensions.trivia",
            "extensions.moderation",
            "extensions.lastfm",
            "extensions.misc",
            "extensions.help",
            "extensions.developer",
            "extensions.error_handler",
        ]
        for extension in self.inital_extensions:
            try:
                self.load_extension(extension)
            except Exception as e:
                print(
                    f"Failed to load extension {Fore.RED}{extension}{Style.RESET_ALL}: {Fore.RED}{e}{Style.RESET_ALL}"
                )
                traceback.print_exc()

        self.remove_command("help")

    async def on_ready(self):
        print(
            f"\n🤖 Logged in as {Fore.GREEN}{self.user}{Style.RESET_ALL} ({Fore.GREEN}{self.user.id}{Style.RESET_ALL})"
        )
        print(
            f"🔄 Discord API version: {Fore.GREEN}{discord.__version__}{Style.RESET_ALL}"
        )


bot = Bot()
bot.run(config["TOKEN"])
