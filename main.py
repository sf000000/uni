import discord
import yaml
import os

from discord.ext import commands
from helpers.logger_config import configure_logger

import yaml


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class Bot(commands.AutoShardedBot):
    """
    Represents a bot instance with additional functionality.

    Attributes:
        disabled_extensions (list): A list of disabled extensions.
        log (Logger): The logger instance for logging.
    """

    def __init__(self):
        super().__init__(
            command_prefix=config["PREFIX"],
            case_insensitive=True,
            intents=discord.Intents.all(),
            activity=discord.Game(name=config["STATUS"]),
            status=config["STATUS_TYPE"],
        )
        self.disabled_extensions = []
        self.log = configure_logger()

        extensions_dir = "extensions"
        for filename in os.listdir(extensions_dir):
            if filename.endswith(".py"):
                extension = f"{extensions_dir}.{filename[:-3]}"
                try:
                    (
                        self.load_extension(extension)
                        if extension not in self.extensions
                        else None
                    )
                except Exception as e:
                    self.log.error(f"Failed to load extension {extension}\n{e}")

        self.load_extension("jishaku")
        self.remove_command("help")

    async def on_ready(self):
        self.log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        self.log.info(f"Connected to {len(self.guilds)} guilds")


bot = Bot()
bot.run(config["TOKEN"])
