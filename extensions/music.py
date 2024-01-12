import discord
import yaml
import wavelink
import spotipy
import asyncio
import datetime

from spotipy import SpotifyClientCredentials
from discord.ext import commands
from discord.commands import Option, OptionChoice
from typing import List
from typing import cast
from helpers import db_manager


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


def format_time(time: int) -> str:
    return str(datetime.timedelta(milliseconds=time))[2:].split(".")[0]


def truncate_text(text: str, max_length: int) -> str:
    return text if len(text) <= max_length else text[: max_length - 3] + "..."


class MusicPlayerView(discord.ui.View):
    def __init__(
        self,
        player: wavelink.Player,
        bot: commands.Bot,
        playing_messages: dict,
    ):
        super().__init__(timeout=None)
        self.player = player
        self.playing_messages = playing_messages
        self.bot = bot

        queue_button = discord.ui.Button(
            style=discord.ButtonStyle.link,
            label="Queue",
            url=f"{config['web_url']}/queue/{player.ctx.guild.id}",
        )
        self.add_item(queue_button)

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.gray)
    async def pause_resume(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.player.paused:
            button.label = "Pause"
            button.style = discord.ButtonStyle.gray
            await self.player.pause(False)
        else:
            button.label = "Resume"
            button.style = discord.ButtonStyle.green
            await self.player.pause(True)

        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.gray)
    async def skip(self, button: discord.ui.Button, interaction: discord.Interaction):
        player = cast(wavelink.Player, interaction.guild.voice_client)

        if not player:
            return

        if not player.playing:
            return

        await player.skip(force=True)
        await interaction.response.defer()

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.red)
    async def stop(self, button: discord.ui.Button, interaction: discord.Interaction):
        player = cast(wavelink.Player, interaction.guild.voice_client)

        if not player:
            return

        if not player.playing:
            return

        await player.disconnect()

        player_context = self.playing_messages.get(player.ctx.guild.id)

        if player_context is not None:
            message = await self.bot.get_channel(
                player_context["channel_id"]
            ).fetch_message(player_context["message_id"])
            await message.delete()
            del self.playing_messages[player.ctx.guild.id]

        await interaction.response.defer()


class Music(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.bot.loop.create_task(self.connect_nodes())
        self.playing_messages = {}
        self.db_manager = db_manager.DatabaseManager(
            config["mongodb"]["uri"],
            config["mongodb"]["database"],
            config["mongodb"]["collection"],
        )

    async def connect_nodes(self):
        await self.bot.wait_until_ready()
        nodes = [
            wavelink.Node(
                uri="http://localhost:2333",
                password="74f57d6cb9964384de92d6a9892e196afcbeb00daf06f14dd6e69746b338d3df",
            )
        ]
        await wavelink.Pool.connect(nodes=nodes, client=self.bot, cache_capacity=100)

    async def update_queue_db(self, guild_id: int, player: wavelink.Player):
        if not player:
            return

        if not player.playing:
            return

        current_track = {
            "title": player.current.title,
            "author": player.current.author,
            "length": format_time(player.current.length),
            "uri": player.current.uri,
            "artwork": player.current.artwork,
        }

        upcoming_tracks = []
        for index, track in enumerate(player.queue):
            upcoming_tracks.append(
                {
                    "index": index + 1,
                    "title": track.title,
                    "author": track.author,
                    "length": format_time(track.length),
                    "uri": track.uri,
                    "artwork": track.artwork,
                }
            )

        tracks_dict = {
            "guildId": str(guild_id),
            "current_track": current_track,
            "upcoming_tracks": upcoming_tracks,
        }

        self.db_manager.update_queue(str(guild_id), tracks_dict)

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f"🎹 Wavelink node {payload.node.identifier} ready.")

    @commands.Cog.listener()
    async def on_wavelink_track_end(
        self, payload: wavelink.TrackEndEventPayload
    ) -> None:
        player: wavelink.Player = payload.player
        if player is None:
            return

        if player.queue and player.autoplay == wavelink.AutoPlayMode.disabled:
            await player.play(player.queue.get())
        elif not player.queue:
            await player.stop()
            await player.disconnect()

            player_context = self.playing_messages.get(player.ctx.guild.id)

            if player_context is not None:
                message = await self.bot.get_channel(
                    player_context["channel_id"]
                ).fetch_message(player_context["message_id"])
                await message.delete()
                del self.playing_messages[player.ctx.guild.id]

    @commands.Cog.listener()
    async def on_wavelink_track_start(
        self, payload: wavelink.TrackStartEventPayload
    ) -> None:
        player: wavelink.Player = payload.player

        if player is None:
            return

        player_context = self.playing_messages.get(player.ctx.guild.id)

        if player_context is None:
            return

        message = await self.bot.get_channel(
            player_context["channel_id"]
        ).fetch_message(player_context["message_id"])

        embed = discord.Embed(color=discord.Color.embed_background(), description="")

        embed.add_field(
            name="Now Playing",
            value=f"```{format_time(player.current.length)} - {truncate_text(player.current.title, 13)} - {truncate_text(player.current.author, 10)}```",
            inline=False,
        )

        if len(player.queue) > 0:
            next_track = player.queue[0]

            embed.add_field(
                name="Next Up",
                value=f"```{format_time(next_track.length)} - {truncate_text(next_track.title, 13)} - {truncate_text(next_track.author, 10)}```",
                inline=False,
            )

        if player.current.artwork:
            embed.set_image(url=player.current.artwork)

        await self.update_queue_db(player.channel.guild.id, player)
        await message.edit("", embed=embed)

    @commands.Cog.listener()
    async def on_wavelink_player_update(
        self, payload: wavelink.PlayerUpdateEventPayload
    ) -> None:
        if payload.player is None or not payload.connected:
            return
        self.db_manager.delete_queue(str(payload.player.channel.guild.id))

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

    async def ensure_voice(self, ctx: discord.ApplicationContext) -> bool:
        player = cast(wavelink.Player, ctx.voice_client)

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond(
                "You are not connected to any voice channel.",
                ephemeral=True,
                delete_after=10,
            )
            return False
        if player is not None and player.connected:
            if player.channel.id != ctx.author.voice.channel.id:
                await ctx.respond(
                    "We are not in the same voice channel.",
                    ephemeral=True,
                    delete_after=10,
                )
                return False
        else:
            await asyncio.gather(
                ctx.author.voice.channel.connect(cls=wavelink.Player),
                ctx.respond(
                    f"Joined {ctx.author.voice.channel.mention}.",
                ),
            ),

        return True

    @discord.slash_command(name="join", description="Joins a voice channel.")
    async def join_voice(
        self,
        ctx: discord.ApplicationContext,
        channel: Option(
            discord.VoiceChannel,
            "Select a voice channel",
            autocomplete=voice_channel_autocomplete,
            required=False,
        ),
    ):
        if not await self.ensure_voice(ctx):
            return await ctx.respond(
                "You are not connected to any voice channel.",
                ephemeral=True,
                delete_after=10,
            )

        try:
            await channel.connect(cls=wavelink.Player)
            await ctx.respond(
                f"Joined {channel.mention}.",
            )
            await ctx.guild.me.edit(deafen=True)
        except Exception as e:
            await ctx.respond(f"An error occurred: {e}")

    @discord.slash_command(name="stop", description="Leaves a voice channel.")
    async def stop_voice(self, ctx: discord.ApplicationContext):
        if not ctx.voice_client:
            return await ctx.respond(
                "I'm not connected to a voice channel.",
                ephemeral=True,
                delete_after=10,
            )

        await ctx.voice_client.disconnect()
        return await ctx.respond("Disconnected!", ephemeral=True, delete_after=10)

    @discord.slash_command(name="play", description="Plays a song/playlist.")
    async def play_music(
        self,
        ctx: discord.ApplicationContext,
        query: Option(
            str,
            "Enter a song name or a Spotify playlist link.",
            required=True,
        ),
        shuffle: Option(
            bool,
            "Shuffle the playlist?",
            required=False,
            default=False,
        ),
    ):
        if not await self.ensure_voice(ctx):
            return

        tracks: wavelink.Search = await wavelink.Playable.search(query)

        player = cast(wavelink.Player, ctx.voice_client)
        player.ctx = ctx

        if not tracks:
            return await ctx.reply("No tracks were found.", ephemeral=True)

        view = MusicPlayerView(player, self.bot, self.playing_messages)

        if isinstance(tracks, wavelink.Playlist):
            if player.playing:
                response = await ctx.respond(
                    f"Queued **{tracks.name}** (**{len(tracks)}** tracks)", view=view
                )
                self.playing_messages[ctx.guild.id] = {
                    "message_id": response.id,
                    "guild_id": ctx.guild.id,
                    "channel_id": ctx.channel.id,
                }
                await player.queue.put_wait(tracks)
            else:
                response = await ctx.respond(
                    f"Playing **{tracks.name}** (**{len(tracks)}** tracks)", view=view
                )
                self.playing_messages[ctx.guild.id] = {
                    "message_id": response.id,
                    "guild_id": ctx.guild.id,
                    "channel_id": ctx.channel.id,
                }
                await player.play(tracks[0])
                await player.queue.put_wait(tracks[1:])
        elif not player.playing:
            response = await ctx.respond(
                f"Playing **{tracks[0].title}**", delete_after=10
            )
            await player.play(tracks[0])
        else:
            response = await ctx.respond(
                f"Queued **{tracks[0].title}**", delete_after=10
            )
            await player.queue.put_wait(tracks[0])

        if shuffle:
            player.queue.shuffle()


def setup(bot_: discord.Bot):
    bot_.add_cog(Music(bot_))
