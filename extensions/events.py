import discord
import aiosqlite
import yaml


from discord.ext import commands, tasks
from helpers.top_gg import TopGGManager


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class Events(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.db_path = "kino.db"
        self.bot.loop.create_task(self.setup_db())
        self.top_gg = TopGGManager(config["top_gg"]["api_token"])

        # self.update_top_gg_stats.start()

    async def setup_db(self):
        self.conn = await aiosqlite.connect(self.db_path)

    @tasks.loop(minutes=10)
    async def update_top_gg_stats(self):
        await self.bot.wait_until_ready()

        server_count = len(self.bot.guilds)
        shards = [guild.shard_id for guild in self.bot.guilds]
        shard_count = len(self.bot.shards)

        await self.top_gg.post_bot_stats(
            self.bot.user.id, server_count, shards=shards, shard_count=shard_count
        )


def setup(bot_: discord.Bot):
    bot_.add_cog(Events(bot_))
