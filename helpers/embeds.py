import discord


class Embeds:
    """
    A utility class for creating Discord embeds with different colors and styles.
    """

    @staticmethod
    def get_embed(description: str, color: discord.Color) -> discord.Embed:
        """
        Creates a Discord embed with the given description and color.

        Args:
            description (str): The description text for the embed.
            color (discord.Color): The color of the embed.

        Returns:
            discord.Embed: The created embed.
        """
        embed = discord.Embed(
            description=description,
            color=color,
        )
        return embed

    @staticmethod
    def info(message: str, emoji: str = "💡") -> discord.Embed:
        """
        Creates an info embed with the given message.

        Args:
            message (str): The message for the embed.

        Returns:
            discord.Embed: The created info embed.
        """
        description = f"{emoji} {message}"
        return Embeds.get_embed(description, discord.Color.blue())

    @staticmethod
    def success(message: str, emoji: str = "✅") -> discord.Embed:
        """
        Creates a success embed with the given message.

        Args:
            message (str): The message for the embed.

        Returns:
            discord.Embed: The created success embed.
        """
        description = f"{emoji} {message}"
        return Embeds.get_embed(description, discord.Color.green())

    @staticmethod
    def warning(message: str, emoji: str = "⚠️") -> discord.Embed:
        """
        Creates a warning embed with the given message.

        Args:
            message (str): The message for the embed.

        Returns:
            discord.Embed: The created warning embed.
        """
        description = f"{emoji} {message}"
        return Embeds.get_embed(description, discord.Color.orange())

    @staticmethod
    def error(message: str, emoji: str = "❌") -> discord.Embed:
        """
        Creates an error embed with the given message and error ID.

        Args:
            message (str): The message for the embed.

        Returns:
            discord.Embed: The created error embed.
        """
        description = f"{emoji} {message}"
        return Embeds.get_embed(description, discord.Color.red())
