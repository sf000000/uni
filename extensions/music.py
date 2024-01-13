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
    return text if len(text) <= max_length else f"{text[:max_length - 3]}..."


class EffectsSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Bass Boost", value="bass-boost"),
            discord.SelectOption(label="8D", value="8d"),
            discord.SelectOption(label="Slowed & reverb ", value="reverb"),
            discord.SelectOption(label="Reset", value="reset"),
        ]
        super().__init__(
            placeholder="Apply an effect",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.effect_emojis = {
            "bass-boost": "🔊",
            "8d": "🌀",
            "reverb": "🐌",
            "reset": "",
        }
        self.active_effects = []

    async def callback(self, interaction: discord.Interaction):
        player = cast(wavelink.Player, interaction.guild.voice_client)

        if not player or not player.connected or not player.playing:
            return

        filters: wavelink.Filters = player.filters
        selected_effect = self.values[0]

        embed = interaction.message.embeds[0]

        if selected_effect == "reset":
            self.active_effects = []
            if len(embed.fields) > 0 and embed.fields[-1].name == "Effects":
                embed.remove_field(-1)
        else:
            if self.effect_emojis[selected_effect] in self.active_effects:
                await interaction.response.send_message(
                    "This effect is already active.", ephemeral=True
                )
                return

            self.active_effects.append(self.effect_emojis[selected_effect])
            if len(embed.fields) > 0 and embed.fields[-1].name == "Effects":
                embed.set_field_at(
                    -1,
                    name="Effects",
                    value=" ➔ ".join(self.active_effects),
                    inline=False,
                )
            else:
                embed.add_field(
                    name="Effects", value=" ".join(self.active_effects), inline=False
                )

        if selected_effect == "bass-boost":
            await self.apply_bass_boost(filters, player)
        elif selected_effect == "8d":
            await self.apply_8d(filters, player)
        elif selected_effect == "reverb":
            await self.apply_reverb(filters, player)
        elif selected_effect == "reset":
            filters.reset()
            await player.set_filters(filters, seek=True)

        await interaction.response.edit_message(embed=embed, view=self.view)

    async def apply_bass_boost(self, filters, player):
        if filters.equalizer.payload[0]["gain"] == 1:
            filters.reset()
            await player.set_filters(filters, seek=True),
            return

        # TODO improve this
        filters.equalizer.set(bands=[{"band": 0, "gain": 1}])
        await player.set_filters(filters, seek=True)

    async def apply_8d(self, filters, player):
        if (
            filters.rotation.payload.get("rotationHz") == 0.125
            and filters.tremolo.payload.get("depth") == 0.3
            and filters.tremolo.payload.get("frequency") == 14
        ):
            filters.reset()
            await player.set_filters(filters, seek=True),
            return

        filters.timescale.set(pitch=1.05)
        filters.tremolo.set(depth=0.3, frequency=14)
        filters.rotation.set(rotation_hz=0.125)
        filters.equalizer.set(bands=[{"band": 1, "gain": -0.2}])

        await player.set_filters(filters, seek=True),

    async def apply_reverb(self, filters, player):
        if (
            filters.timescale.payload.get("pitch") == 0.8
            and filters.timescale.payload.get("rate") == 0.9
            and filters.reverb.payload.get("wet") == 0.35
        ):
            filters.reset()
            await player.set_filters(filters, seek=True),
            return

        filters.timescale.set(pitch=0.8, rate=0.9)
        await player.set_filters(filters, seek=True),


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

        select_menu = EffectsSelect()
        self.add_item(select_menu)

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

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.gray)
    async def shuffle(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        player = cast(wavelink.Player, interaction.guild.voice_client)

        if not player:
            return

        if not player.playing:
            return

        player.queue.shuffle()
        button.style = discord.ButtonStyle.green

        await interaction.response.edit_message(view=self)


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

        upcoming_tracks = [
            {
                "index": index + 1,
                "title": track.title,
                "author": track.author,
                "length": format_time(track.length),
                "uri": track.uri,
                "artwork": track.artwork,
            }
            for index, track in enumerate(player.queue)
        ]
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

        now_playing = f"{format_time(player.current.length)} - " + (
            f"{truncate_text(player.current.title, 13)}"
            if player.current.source != "youtube"
            else player.current.title
        )
        now_playing += (
            f" - {truncate_text(player.current.author, 10)}"
            if player.current.source != "youtube"
            else ""
        )
        now_playing = f"{now_playing: <31}"

        description = f"**Now Playing**\n```{now_playing}```\n"

        if len(player.queue) > 0:
            next_track = player.queue[0]
            next_up = f"{format_time(next_track.length)} - " + (
                f"{truncate_text(next_track.title, 13)}"
                if next_track.source != "youtube"
                else next_track.title
            )
            next_up += (
                f" - {truncate_text(next_track.author, 10)}"
                if next_track.source != "youtube"
                else ""
            )
            next_up = f"{next_up: <31}"
            description += f"**Next Up**\n```{next_up}```"

        embed.description = description

        filters: wavelink.Filters = player.filters
        active_effects = []
        if filters.equalizer.payload[0]["gain"] == 1:
            active_effects.append("🔊")
        if (
            filters.rotation.payload.get("rotationHz") == 0.125
            and filters.tremolo.payload.get("depth") == 0.3
            and filters.tremolo.payload.get("frequency") == 14
        ):
            active_effects.append("🌀")
        if (
            filters.timescale.payload.get("pitch") == 0.8
            and filters.timescale.payload.get("rate") == 0.9
            and filters.reverb.payload.get("wet") == 0.35
        ):
            active_effects.append("🐌")

        if active_effects:
            embed.add_field(
                name="Effects", value=" ➔ ".join(active_effects), inline=False
            )

        if player.current.artwork:
            embed_method = (
                embed.set_image
                if player.current.source == "youtube"
                else embed.set_thumbnail
            )
            embed_method(url=player.current.artwork)

        await self.update_queue_db(player.channel.guild.id, player)
        await message.edit("", embed=embed)
        await message.edit("", embed=embed)

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
            return await ctx.respond("No tracks were found.", ephemeral=True)

        self.view = MusicPlayerView(player, self.bot, self.playing_messages)

        if isinstance(tracks, wavelink.Playlist):
            if player.playing:
                response = await ctx.respond(
                    f"Queued **{tracks.name}** (**{len(tracks)}** tracks)",
                    view=self.view,
                )
                self.playing_messages[ctx.guild.id] = {
                    "message_id": response.id,
                    "guild_id": ctx.guild.id,
                    "channel_id": ctx.channel.id,
                }
                await player.queue.put_wait(tracks)
            else:
                response = await ctx.respond(
                    f"Playing **{tracks.name}** (**{len(tracks)}** tracks)",
                    view=self.view,
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
