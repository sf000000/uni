import discord
import yaml
import wavelink
import spotipy


import traceback

from spotipy import SpotifyClientCredentials
from discord.ext import commands
from discord.commands import Option, OptionChoice
from typing import List


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()
sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=config["spotify"]["client_id"],
        client_secret=config["spotify"]["client_secret"],
    )
)


class Music(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.bot.loop.create_task(self.connect_nodes())
        self.current_channel_id = None

    async def connect_nodes(self):
        await self.bot.wait_until_ready()
        nodes = [
            wavelink.Node(
                uri="http://localhost:2333",
                password="youshallnotpass",
            )
        ]
        await wavelink.Pool.connect(nodes=nodes, client=self.bot, cache_capacity=100)

    async def voice_channel_autocomplete(
        self, ctx: discord.AutocompleteContext
    ) -> List[discord.OptionChoice]:
        """Autocomplete callback function to suggest voice channels."""
        guild = ctx.interaction.guild
        voice_channels = await guild.fetch_channels()
        return [
            OptionChoice(name=channel.name, value=channel.id)
            for channel in voice_channels
            if isinstance(channel, discord.VoiceChannel)
        ]


def setup(bot_: discord.Bot):
    bot_.add_cog(Music(bot_))
