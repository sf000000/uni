import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient

from helpers.logger_config import configure_logger
from helpers.utils import load_config

config = load_config()
db = AsyncIOMotorClient(config["db"]["connection_string"])


class Bot(commands.AutoShardedBot):
    """
    Represents a bot instance with additional functionality.

    Attributes:
        disabled_extensions (list): A list of disabled extensions.
        log (Logger): The logger instance for logging.
    """

    def __init__(self):
        super().__init__(
            command_prefix=config["bot"]["prefix"],
            case_insensitive=True,
            intents=discord.Intents.all(),
        )
        self.disabled_extensions = []
        self.log = configure_logger()
        self.config = config
        self.db = db.uni

        exts = [
            "extensions.developer",
            "extensions.github",
            "extensions.help",
            "extensions.information",
            "extensions.fun",
            "extensions.events",
            "extensions.lastfm",
            "extensions.misc",
            "extensions.moderation",
            "extensions.music",
        ]
        for ext in exts:
            try:
                self.load_extension(ext)
            except Exception as e:
                self.log.error(f"Failed to load extension {ext}\n{e}")

        # extensions_dir = "extensions"

        # for filename in os.listdir(extensions_dir):
        #     if filename.endswith(".py"):
        #         extension = f"{extensions_dir}.{filename[:-3]}"
        #         try:
        #             (
        #                 self.load_extension(extension)
        #                 if extension not in self.extensions
        #                 else None
        #             )
        #         except Exception as e:
        #             self.log.error(f"Failed to load extension {extension}\n{e}")

        self.load_extension("jishaku")
        self.remove_command("help")

    async def on_ready(self):
        self.log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        self.log.info(f"Connected to {len(self.guilds)} guilds")


bot = Bot()
bot.run(config["bot"]["token"])
