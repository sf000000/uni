import os

import discord
import httpx
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from helpers.embeds import Embeds
from helpers.utils import ms_to_hours


class ListenerPaginator(discord.ui.View):
    def __init__(self, data, track):
        super().__init__()
        self.data = data
        self.track = track
        self.current_page = 0

    @discord.ui.button(label="First", emoji="⏮️", style=discord.ButtonStyle.secondary)
    async def first_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        self.current_page = 0
        await interaction.response.edit_message(
            embed=self.get_page_content(), view=self
        )

    @discord.ui.button(label="Previous", emoji="⬅️", style=discord.ButtonStyle.secondary)
    async def previous_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(
                embed=self.get_page_content(), view=self
            )

    @discord.ui.button(label="Next", emoji="➡️", style=discord.ButtonStyle.secondary)
    async def next_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.current_page < len(self.data) - 1:
            self.current_page += 1
            await interaction.response.edit_message(
                embed=self.get_page_content(), view=self
            )

    @discord.ui.button(label="Last", emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def last_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        self.current_page = len(self.data) - 1
        await interaction.response.edit_message(
            embed=self.get_page_content(), view=self
        )

    def get_page_content(self):
        item = self.data[self.current_page]
        embed = discord.Embed(
            description=item["user"]["profile"]["bio"] or "No bio",
            color=discord.Color.embed_background(),
        )

        if item["user"]["image"]:
            embed.set_thumbnail(url=item["user"]["image"])

        embed.set_author(
            name=f"{self.track.title} by {self.track.artist}",
            url=self.track.track_url,
            icon_url=self.track.album_cover_url,
        )

        embed.add_field(
            name="User",
            value=f"{item['user']['displayName']} ([Open in Spotify](https://open.spotify.com/user/{item['user']['id']}))",
        )
        embed.add_field(
            name="Streams",
            value=f"{item['streams']}x ({ms_to_hours(item['playedMs'])})",
        )

        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.data)}")

        return embed


class Misc(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.config = bot.config
        self.embed = Embeds()

    @discord.slash_command(
        name="quickpoll",
        description="Add up/down arrow to message initiating a poll",
    )
    async def quickpoll(
        self,
        ctx: discord.ApplicationContext,
        emoji_type=discord.Option(
            str,
            "Emoji type to add to message.",
            required=True,
            choices=[
                discord.OptionChoice(name="Arrows", value="updown"),
                discord.OptionChoice(name="✅ ❌", value="yesno"),
                discord.OptionChoice(name="👍 👎", value="thumbs"),
            ],
        ),
    ):
        emoji_pairs = {
            "updown": ("⬆️", "⬇️"),
            "yesno": ("✅", "❌"),
            "thumbs": ("👍", "👎"),
        }

        messages = await ctx.channel.history(limit=1).flatten()
        if not messages:
            return await ctx.respond(
                embed=self.embed.error("There is no message above the slash command."),
                ephemeral=True,
            )

        message = messages[0]
        emojis = emoji_pairs.get(emoji_type, ())
        for emoji in emojis:
            await message.add_reaction(emoji)

        await ctx.respond(
            embed=self.embed.success("Done."), ephemeral=True, delete_after=5
        )

    @discord.slash_command(
        name="tts",
        description="Convert text to speech",
    )
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def _tts(
        self,
        ctx: discord.ApplicationContext,
        text=discord.Option(str, "Text to speak", required=True),
        voice=discord.Option(
            str,
            "Voice to speak with",
            required=False,
            choices=[
                discord.OptionChoice(name="Brian", value="Brian"),
                discord.OptionChoice(name="Emma", value="Emma"),
                discord.OptionChoice(name="Ivy", value="Ivy"),
                discord.OptionChoice(name="Joey", value="Joey"),
                discord.OptionChoice(name="Justin", value="Justin"),
                discord.OptionChoice(name="Kendra", value="Kendra"),
                discord.OptionChoice(name="Kimberly", value="Kimberly"),
                discord.OptionChoice(name="Matthew", value="Matthew"),
                discord.OptionChoice(name="Salli", value="Salli"),
            ],
        ),
    ):
        await ctx.defer()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://ttsmp3.com/makemp3_new.php",
                data={
                    "msg": text,
                    "lang": voice,
                    "source": "ttsmp3",
                    "quality": "hi",
                    "speed": "0",
                    "action": "process",
                },
            )
            data = response.json()

            response = await client.get(data["URL"])
            with open("tts.mp3", "wb") as file:
                file.write(response.content)

        await ctx.respond(file=discord.File("tts.mp3"))
        os.remove("tts.mp3")

    @discord.slash_command(name="palette", description="Generate a color palette")
    async def _palette(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        url = "http://colormind.io/api/"
        payload = {"model": "default"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                colors = data.get("result", [])
            except httpx.HTTPError:
                return await ctx.respond(
                    embed=self.embed.error("Failed to fetch colors."),
                    ephemeral=True,
                )

        if not colors:
            return await ctx.respond(
                embed=self.embed.error("No colors were returned."),
                ephemeral=True,
            )

        try:
            image = Image.new("RGB", (200 * len(colors), 200), color=(255, 255, 255))
            draw = ImageDraw.Draw(image)
            font_path = "assets/fonts/sf_mono.otf"
            font = ImageFont.truetype(font_path, 40)

            for i, color in enumerate(colors):
                hex_color = "#%02x%02x%02x" % tuple(color)
                draw.rectangle([(i * 200, 0), ((i + 1) * 200, 200)], fill=tuple(color))

                # use textbbox to get the bounding box of the text
                text_width, text_height = draw.textbbox((0, 0), hex_color, font=font)[
                    2:
                ]

                # calculate the position for the text to be centered
                text_x = (i * 200) + ((200 - text_width) / 2)
                text_y = 100 - text_height / 2

                r, g, b = color
                text_color = (int(r * 0.5), int(g * 0.5), int(b * 0.5))

                draw.text((text_x, text_y), hex_color, font=font, fill=text_color)

            filename = "temp/colors.png"
            image.save(filename, quality=100)

            await ctx.respond(file=discord.File(filename))
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"An error occurred: {e}"), ephemeral=True
            )

        finally:
            os.remove(filename)

    @discord.slash_command(
        name="listeners",
        description="Shows the top listeners of your current Spotify song. (Must be listening to Spotify)",
    )
    async def get_listeners(self, ctx: discord.ApplicationContext):
        await ctx.defer()
        spotify = None
        for activity in ctx.author.activities:
            if isinstance(activity, discord.Spotify):
                spotify = activity

        if not spotify:
            await ctx.respond(
                embed=self.embed.error(
                    "You must be listening to Spotify to use this command."
                ),
                ephemeral=True,
            )
            return

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://beta-api.stats.fm/api/v1/search/elastic",
                    params={
                        "query": spotify.title,
                        "type": "track",
                        "limit": "50",
                    },
                    headers={
                        "accept": "application/json",
                        "User-Agent": "Mozilla/5.0 (U; Linux i654 ) Gecko/20130401 Firefox/46.2",
                    },
                )
                response.raise_for_status()
                data = response.json()

                track_id = None

                if data.get("items") and data["items"].get("tracks"):
                    tracks = data["items"]["tracks"]
                    for track in tracks:
                        track_artists = [artist["name"] for artist in track["artists"]]
                        if spotify.artist in track_artists:
                            track_id = track["id"]
                            break

                if not track_id:
                    return await ctx.respond(
                        embed=self.embed.error(
                            f"Could not find any listeners for {spotify.title}"
                        ),
                        ephemeral=True,
                    )

                response = await client.get(
                    f"https://beta-api.stats.fm/api/v1/tracks/{track_id}/top/listeners",
                    headers={
                        "accept": "application/json",
                        "User-Agent": "Mozilla/5.0 (U; Linux i654 ) Gecko/20130401 Firefox/46.2",
                        "Authorization": f"Bearer {self.config['statsfm']['api_key']}",
                    },
                )
                response.raise_for_status()
                data = response.json()
                if not data.get("items"):
                    return await ctx.respond(
                        embed=self.embed.error(
                            f"Could not find any listeners for {spotify.title}"
                        ),
                        ephemeral=True,
                    )

                listeners = data["items"]
                view = ListenerPaginator(listeners, spotify)

                first_listener = listeners[0]
                embed = discord.Embed(
                    description=first_listener["user"]["profile"]["bio"] or "No bio",
                    color=discord.Color.embed_background(),
                )

                embed.set_author(
                    name=f"{spotify.title} by {spotify.artist}",
                    url=spotify.track_url,
                    icon_url=spotify.album_cover_url,
                )

                if first_listener["user"]["image"]:
                    embed.set_thumbnail(url=first_listener["user"]["image"])

                embed.add_field(
                    name="User",
                    value=f"{first_listener['user']['displayName']} ([Open in Spotify](https://open.spotify.com/user/{first_listener['user']['id']}))",
                )
                embed.add_field(
                    name="Streams",
                    value=f"{first_listener['streams']}x ({ms_to_hours(first_listener['playedMs'])})",
                )

                embed.set_footer(text=f"Page 1/{len(listeners)}")

                await ctx.respond(embed=embed, view=view)

            except httpx.HTTPError:
                return await ctx.respond(
                    embed=self.embed.error(
                        "An error occurred while fetching the listener data."
                    ),
                    ephemeral=True,
                )


def setup(bot: discord.Bot):
    bot.add_cog(Misc(bot))
