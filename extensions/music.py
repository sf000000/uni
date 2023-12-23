import contextlib
import discord
import yaml
import wavelink
import spotipy
import random
import datetime

from spotipy import SpotifyClientCredentials
from discord.ext import commands
from discord.commands import Option, OptionChoice
from colorama import Fore, Style
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

    async def add_spotify_playlist_to_queue(self, ctx, playlist_id, shuffle=False):
        playlist = sp.playlist(playlist_id)
        tracks = playlist["tracks"]["items"]

        if shuffle:
            random.shuffle(tracks)

        player: wavelink.Player = ctx.interaction.guild.voice_client
        if not player.connected:
            await player.connect(cls=wavelink.Player)

        first_track_added = False
        for track_item in tracks:
            track_info = track_item["track"]
            track_name = track_info["name"]
            track_artist = track_info["artists"][0]["name"]
            query = f"{track_name} {track_artist}"

            search_result = await wavelink.Playable.search(query)
            if search_result:
                await player.queue.put_wait(search_result[0])
                if not first_track_added:
                    if not player.playing:
                        await player.play(player.queue.get())
                    first_track_added = True

        if len(player.queue) > 1:
            queue_embed = self.create_queue_embed(player)
            if hasattr(self, "current_track_message") and self.current_track_message:
                try:
                    await self.current_track_message.edit(embed=queue_embed)
                except discord.NotFound:
                    skip_button = discord.ui.Button(
                        style=discord.ButtonStyle.gray,
                        label="Skip",
                    )
                    skip_button.callback = lambda interaction: self.skip_track(
                        interaction, skip_button
                    )

                    pause_button = discord.ui.Button(
                        style=discord.ButtonStyle.gray,
                        label="Pause",
                    )
                    pause_button.callback = lambda interaction: self.pause_track(
                        interaction, pause_button
                    )

                    resume_button = discord.ui.Button(
                        style=discord.ButtonStyle.blurple,
                        label="Resume",
                    )
                    resume_button.callback = lambda interaction: self.resume_track(
                        interaction, resume_button
                    )

                    disconnect_button = discord.ui.Button(
                        style=discord.ButtonStyle.red,
                        label="Disconnect",
                    )
                    disconnect_button.callback = (
                        lambda interaction: self.disconnect_bot(
                            interaction, disconnect_button
                        )
                    )

                    view = discord.ui.View(timeout=None)
                    view.add_item(pause_button)
                    view.add_item(resume_button)
                    view.add_item(skip_button)
                    view.add_item(disconnect_button)

                    self.current_track_message = await ctx.channel.send(
                        embed=queue_embed, view=view
                    )

    def create_queue_embed(self, player: wavelink.Player):
        if player is None or player.current is None:
            return discord.Embed(
                description="No track currently playing",
                color=config["COLORS"]["ERROR"],
            )

        embed = discord.Embed(color=config["COLORS"]["DEFAULT"])
        current_track = player.current
        track_length = str(datetime.timedelta(milliseconds=current_track.length))[2:]

        embed.add_field(
            name="Now Playing",
            value=f"```{track_length} - {current_track.title} - {current_track.author}```",
            inline=False,
        )

        if len(player.queue) > 0:
            next_track = player.queue.get()
            track_length = str(datetime.timedelta(milliseconds=next_track.length))[2:]
            embed.add_field(
                name="Up Next",
                value=f"```{track_length} - {next_track.title} - {next_track.author}```",
                inline=False,
            )

        try:
            embed.set_image(url=current_track.artwork)
        except Exception as e:
            print(f"Error setting thumbnail: {e}")

        return embed

    async def skip_track(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        player: wavelink.Player = interaction.guild.voice_client
        if not player:
            return

        if not player.current:
            return

        skipped = await player.skip(force=True)
        if not skipped:
            return await interaction.followup.send(
                "There's nothing to skip", ephemeral=True
            )

        try:
            await player.play(player.queue.get())
        except wavelink.exceptions.QueueEmpty:
            await player.disconnect()
            await interaction.message.delete()

        await interaction.followup.send(ephemeral=True, delete_after=2)

    async def pause_track(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        player: wavelink.Player = interaction.guild.voice_client
        if not player:
            return

        if not player.current:
            return

        await player.pause(True)
        await interaction.followup.send(ephemeral=True, delete_after=2)

    async def resume_track(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        player: wavelink.Player = interaction.guild.voice_client
        if not player:
            return

        if not player.current:
            return

        await player.pause(False)
        await interaction.followup.send(ephemeral=True, delete_after=2)

    async def loop_track(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        player: wavelink.Player = interaction.guild.voice_client
        if not player:
            return

        if player.queue.mode != wavelink.QueueMode.loop:
            player.loop = wavelink.QueueMode.loop

        else:
            player.loop = wavelink.QueueMode.normal

        await interaction.followup.send(ephemeral=True, delete_after=2)

    async def disconnect_bot(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        player: wavelink.Player = interaction.guild.voice_client
        if not player:
            return

        player.queue.clear()
        await player.disconnect()

        await interaction.message.delete()
        await interaction.followup.send(ephemeral=True, delete_after=2)

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
        if not channel:
            if ctx.author.voice:
                channel = ctx.author.voice.channel
            else:
                await ctx.respond(
                    "You are not in a voice channel and no channel was provided."
                )
                return

        if ctx.voice_client and ctx.voice_client.channel.id == channel.id:
            await ctx.respond("I'm already connected to this voice channel!")
            return
        elif ctx.voice_client:
            await ctx.voice_client.disconnect()

        try:
            await channel.connect(cls=wavelink.Player)
            await ctx.respond(
                f"Joined {channel.mention}! Use **/play** to play a song/playlist.",
            )
            await ctx.guild.me.edit(deafen=True)
        except Exception as e:
            await ctx.respond(f"An error occurred: {e}")

    @discord.slash_command(name="play", description="Plays a song/playlist.")
    async def play_voice(
        self,
        ctx: discord.ApplicationContext,
        query: Option(str, "Enter a song/playlist name or URL"),
        shuffle: Option(bool, "Shuffle the playlist", required=False),
        autoplay: Option(bool, "Autoplay", required=False),
    ):
        self.current_channel_id = ctx.channel.id

        if not ctx.author.voice:
            await ctx.respond("You are not in a voice channel.")
            return

        player: wavelink.Player = ctx.interaction.guild.voice_client

        if player is None or not player.connected:
            channel = ctx.author.voice.channel
            player = await channel.connect(cls=wavelink.Player)

        if ctx.author.voice.channel.id != player.channel.id:
            await ctx.respond(
                "You are not in the same voice channel as me.", ephemeral=True
            )
            return

        await ctx.defer()

        if autoplay:
            player.autoplay = wavelink.AutoPlayMode.enabled

        tracks = None

        if "open.spotify.com" in query:
            playlist_id = query.split("/")[-1].split("?")[0]
            await self.add_spotify_playlist_to_queue(ctx, playlist_id, shuffle)
        else:
            tracks = await wavelink.Playable.search(query)

        if tracks and not isinstance(tracks, wavelink.Playable):
            track: wavelink.Playable = tracks[0]
            await player.queue.put_wait(track)

            queue_embed = self.create_queue_embed(player)
            if hasattr(self, "current_track_message"):
                await self.current_track_message.edit(embed=queue_embed)

        if not player.playing:
            await player.play(player.queue.get())

        await ctx.followup.send(
            f"Added {len(player.queue)} songs to the queue.",
            ephemeral=True,
            delete_after=2,
        )

    @discord.slash_command(name="pause", description="Pauses the current song.")
    async def pause_voice(self, ctx: discord.ApplicationContext):
        player: wavelink.Player = ctx.interaction.guild.voice_client

        if not player:
            await ctx.respond("I'm not connected to a voice channel!", ephemeral=True)
            return

        if player.paused:
            await ctx.respond("The player is already paused.", ephemeral=True)
            return

        await player.pause(True)
        await ctx.respond("Paused the player.")

    @discord.slash_command(name="resume", description="Resumes the current song.")
    async def resume_voice(self, ctx: discord.ApplicationContext):
        player: wavelink.Player = ctx.interaction.guild.voice_client

        if not player:
            await ctx.respond("I'm not connected to a voice channel!", ephemeral=True)
            return

        if not player.paused:
            await ctx.respond("The player is not paused.")
            return

        await player.pause(False)
        await ctx.respond("Resumed the player.")

    @discord.slash_command(name="skip", description="Skips the current song.")
    async def skip_voice(self, ctx: discord.ApplicationContext):
        player: wavelink.Player = ctx.guild.voice_client

        if not player:
            await ctx.respond("I'm not connected to a voice channel!", ephemeral=True)
            return

        if not player.current:
            await ctx.respond("Nothing is currently playing.", ephemeral=True)
            return

        skipped = await player.skip(force=True)
        if not skipped:
            return await ctx.respond("There's nothing to skip", delete_after=5)

        await player.play(player.queue.get())

    @discord.slash_command(
        name="equalizer",
        description="An equalizer with 6 bands for adjusting the volume of different frequency.",
    )
    async def equalizer(
        self,
        ctx: discord.ApplicationContext,
        sub_bass: Option(
            float,
            "16 - 60Hz(must be between -0.25 and 1.0)",
        ),
        bass: Option(
            float,
            "60 - 250Hz (must be between -0.25 and 1.0)",
        ),
        low_mids: Option(
            float,
            "250 - 500Hz (must be between -0.25 and 1.0)",
        ),
        mids: Option(
            float,
            "500 - 2kHz (must be between -0.25 and 1.0)",
        ),
        upper_mids: Option(
            float,
            "2 - 4kHz (must be between -0.25 and 1.0)",
        ),
        presence: Option(
            float,
            "4 - 6kHz (must be between -0.25 and 1.0)",
        ),
        brilliance: Option(
            float,
            "6 - 20kHz (must be between -0.25 and 1.0)",
        ),
        reset: Option(
            bool,
            "Reset all filters",
            required=False,
        ),
    ):
        player: wavelink.Player = ctx.interaction.guild.voice_client

        if not player:
            return

        filters: wavelink.Filters = player.filters

        if reset:
            filters.equalizer.reset()
        else:
            bands_value = {
                0: sub_bass,
                2: bass,
                4: low_mids,
                6: mids,
                8: upper_mids,
                10: presence,
                12: brilliance,
            }
            filters: wavelink.Filters = player.filters
            equalizer = filters.equalizer

            for band, gain in bands_value.items():
                if not gain or gain < -0.25 or gain > 1.0:
                    return await ctx.respond(
                        "Values must be between `-0.25` and `1.0`.",
                        ephemeral=True,
                        delete_after=5.0,
                    )

                equalizer.payload[band] = gain

        await player.set_filters(filters)
        await ctx.respond(
            "The filter will be applied in a few seconds!",
            ephemeral=True,
            delete_after=5.0,
        )

    @discord.slash_command(
        name="timescale", description="Change the speed, pitch and rate of audio."
    )
    async def timescale(
        self,
        ctx: discord.ApplicationContext,
        speed: Option(
            float,
            "Speed (must be between 0.0 and 1.0)",
        ),
        pitch: Option(
            float,
            "Pitch (must be between 0.0 and 1.0)",
        ),
        rate: Option(
            float,
            "Rate (must be between 0.0 and 1.0)",
        ),
    ):
        player: wavelink.Player = ctx.interaction.guild.voice_client

        if not player:
            return await ctx.respond(
                "I'm not connected to a voice channel!", ephemeral=True
            )

        if (
            speed
            and (speed > 1.0 or speed < 0.0)
            or pitch
            and (pitch > 1.0 or pitch < 0.0)
            or rate
            and (rate > 1.0 or rate < 0.0)
        ):
            return await ctx.respond(
                embed="Values must be between`0.0` and `1.0`.",
                ephemeral=True,
                delete_after=5.0,
            )

        filters = player.filters
        filters.timescale.set(speed=speed, pitch=pitch, rate=rate)

        await player.set_filters(filters)
        await ctx.respond(
            "The filter will be applied in a few seconds!",
            ephemeral=True,
            delete_after=5.0,
        )

    @discord.slash_command(
        name="lowpass",
        description="High frequencies are suppressed, while low frequencies are passed through. (this defaults to 0.0)",
    )
    async def lowpass(
        self,
        ctx: discord.ApplicationContext,
        smoothing: Option(
            float,
        ),
    ):
        player: wavelink.Player = ctx.interaction.guild.voice_client
        if not player:
            return await ctx.respond(
                "I'm not connected to a voice channel!", ephemeral=True
            )

        filters = player.filters
        try:
            filters.low_pass.set(smoothing)
            await player.set_filters(filters)

        except Exception as e:
            return await ctx.respond(f"An error occurred: {e}")

        await ctx.respond(
            "The filter will be applied in a few seconds!",
            ephemeral=True,
            delete_after=5.0,
        )

    @discord.slash_command(
        name="rotation",
        description="Rotates the sound around the stereo channels. The rotation speed in Hz. (1.0 is fast)",
    )
    async def rotation(
        self,
        ctx: discord.ApplicationContext,
        rotation_hz: Option(
            float,
        ),
    ):
        player: wavelink.Player = ctx.interaction.guild.voice_client
        if not player:
            return await ctx.respond(
                "I'm not connected to a voice channel!", ephemeral=True
            )

        if rotation_hz < 0.0:
            return await ctx.respond(
                "The rotation_hz value must be at least 0.0.",
                ephemeral=True,
                delete_after=5.0,
            )

        filters = player.filters
        filters.low_pass.set(rotation_hz)

        await player.set_filters(filters)

        await ctx.respond(
            embed="The filter will be applied in a few seconds!",
            delete_after=5.0,
        )

    @discord.slash_command(
        name="volume",
        description="Adjust the volume of the player.",
    )
    async def volume(
        self,
        ctx: discord.ApplicationContext,
        volume: Option(
            int,
            "Volume (must be between 0 and 1000)",
        ),
    ):
        player: wavelink.Player = ctx.interaction.guild.voice_client
        if not player:
            return await ctx.respond(
                "I'm not connected to a voice channel!", ephemeral=True
            )

        if volume < 0 or volume > 1000:
            return await ctx.respond(
                "The volume value must be between 0 and 1000.",
                ephemeral=True,
                delete_after=5.0,
            )

        await player.set_volume(volume)
        await ctx.respond(
            embed="The volume will be applied in a few seconds!",
            delete_after=5.0,
        )

    @discord.slash_command(
        name="resetfilters",
        description="Reset all filters.",
    )
    async def resetfilters(
        self,
        ctx: discord.ApplicationContext,
    ):
        player: wavelink.Player = ctx.interaction.guild.voice_client
        if not player:
            return await ctx.respond(
                "I'm not connected to a voice channel!", ephemeral=True
            )

        filters = player.filters
        filters.reset()

        await player.set_filters(filters)

    @discord.slash_command(
        name="stop",
        description="Leaves the voice channel.",
    )
    async def leave(
        self,
        ctx: discord.ApplicationContext,
    ):
        player: wavelink.Player = ctx.interaction.guild.voice_client

        if not player:
            return await ctx.respond(
                "I'm not connected to a voice channel!", ephemeral=True
            )

        await player.disconnect()
        player.queue.clear()
        try:
            await self.current_track_message.delete()
        except Exception:
            print("No current track message to delete.")

        await ctx.respond("Disconnected from the voice channel.")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        """Edit or send new message when a new track starts."""
        if (
            self.current_channel_id is None
            or payload.player is None
            or payload.track is None
        ):
            return

        channel = self.bot.get_channel(self.current_channel_id)
        if channel is None:
            return

        queue_embed = self.create_queue_embed(payload.player)
        if hasattr(self, "current_track_message"):
            with contextlib.suppress(discord.NotFound):
                await self.current_track_message.edit(embed=queue_embed)
        else:
            queue_embed = self.create_queue_embed(payload.player)

            skip_button = discord.ui.Button(
                style=discord.ButtonStyle.gray,
                label="Skip",
            )
            skip_button.callback = lambda interaction: self.skip_track(
                interaction, skip_button
            )

            pause_button = discord.ui.Button(
                style=discord.ButtonStyle.gray,
                label="Pause",
            )
            pause_button.callback = lambda interaction: self.pause_track(
                interaction, pause_button
            )

            resume_button = discord.ui.Button(
                style=discord.ButtonStyle.gray,
                label="Resume",
            )
            resume_button.callback = lambda interaction: self.resume_track(
                interaction, resume_button
            )

            disconnect_button = discord.ui.Button(
                style=discord.ButtonStyle.red,
                label="Disconnect",
            )
            disconnect_button.callback = lambda interaction: self.disconnect_bot(
                interaction, disconnect_button
            )

            view = discord.ui.View(timeout=None)
            view.add_item(pause_button)
            view.add_item(resume_button)
            view.add_item(skip_button)
            view.add_item(disconnect_button)

            self.current_track_message = await channel.send(
                embed=queue_embed, view=view
            )

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """Handle when a track ends."""
        player = payload.player

        if payload.reason == "finished":
            try:
                await payload.player.play(payload.player.queue.get())

            except wavelink.exceptions.QueueEmpty:
                await payload.player.disconnect()
                await self.current_track_message.delete()

        if hasattr(self, "current_track_message"):
            queue_embed = self.create_queue_embed(player)
            await self.current_track_message.edit(embed=queue_embed)

    @commands.Cog.listener()
    async def on_wavelink_node_ready(
        self, payload: wavelink.NodeReadyEventPayload
    ) -> None:
        print(
            f"🎵 Wavelink node {Fore.GREEN}{payload.node.identifier}{Style.RESET_ALL} is ready."
        )

    @commands.Cog.listener()
    async def on_wavelink_websocket_closed(
        self, payload: wavelink.WebsocketClosedEventPayload
    ) -> None:
        player = payload.player
        if player is None or (not player.playing and not player.paused):
            return

        await player.queue.clear()
        await player.disconnect(force=True)
        if hasattr(self, "current_track_message"):
            await self.current_track_message.delete()
        print(
            f"""🎵 Wavelink node {Fore.RED}{payload.node.identifier}{Style.RESET_ALL} is disconnected.
                """
        )


def setup(bot_: discord.Bot):
    bot_.add_cog(Music(bot_))
