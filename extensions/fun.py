import io

import discord
import httpx
from colorthief import ColorThief
from discord.ext import commands


class Fun(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @discord.slash_command(
        name="hex",
        description="Grab the most dominant color from an image",
    )
    async def hex(
        self,
        ctx: discord.ApplicationContext,
        image: discord.Option(
            discord.Attachment,
            description="The image to get the color from",
            required=True,
        ),
    ):
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(image.url)
                resp.raise_for_status()
                data = resp.content
            except httpx.HTTPError:
                return await ctx.respond("Could not get image.", ephemeral=True)

        color_thief = ColorThief(io.BytesIO(data))
        dominant_color = color_thief.get_color(quality=1)
        hex_color = (
            f"#{dominant_color[0]:02x}{dominant_color[1]:02x}{dominant_color[2]:02x}"
        )

        embed = discord.Embed(
            title="Dominant Color",
            description=hex_color,
            color=discord.Color.from_rgb(*dominant_color),
        )
        embed.set_thumbnail(url=image.url)
        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="urban",
        description="Get the Urban Dictionary definition of a word.",
    )
    async def urban(
        self,
        ctx: discord.ApplicationContext,
        word: discord.Option(
            str,
            description="The word to define",
            required=True,
        ),
    ):
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"https://api.urbandictionary.com/v0/define?term={word}"
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError:
                return await ctx.respond("Could not get definition.", ephemeral=True)

        embed = discord.Embed(
            title=data["list"][0]["word"],
            description=data["list"][0]["definition"],
            color=self.config["colors"]["default"],
        )

        await ctx.respond(embed=embed)


def setup(bot: discord.Bot):
    bot.add_cog(Fun(bot))
