import discord

from datetime import datetime


class Embeds:
    @staticmethod
    def get_embed(description, color):
        embed = discord.Embed(
            description=description,
            color=color,
        )
        return embed

    @staticmethod
    def info(message):
        description = message
        return Embeds.get_embed(description, discord.Color.blue())

    @staticmethod
    def success(message):
        description = message
        return Embeds.get_embed(description, discord.Color.green())

    @staticmethod
    def warning(message):
        description = message
        return Embeds.get_embed(description, discord.Color.orange())

    # TODO: Add /reporterror to send the error to the developer
    @staticmethod
    def error(message, error_id: int):
        description = message
        return Embeds.get_embed(description, discord.Color.red()).add_field(
            name="Error ID",
            value=f"`{error_id}` - 🚨 Please report this to the developer. `/reporterror`",
        )
