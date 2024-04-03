import discord
from discord.ext import commands

# TODO: Implement Spotify commands


class Spotify(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot


def setup(bot: discord.Bot):
    bot.add_cog(Spotify(bot))
