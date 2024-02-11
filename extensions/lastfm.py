import discord
import aiosqlite
import yaml
import aiohttp
import spotipy
import asyncio

from discord.ext import commands
from spotipy import SpotifyClientCredentials
from helpers.utils import create_progress_bar, json_to_base64, get_dominant_color
from playwright.async_api import async_playwright


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()

sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=config["SPOTIFY_CLIENT_ID"],
        client_secret=config["SPOTIFY_CLIENT_SECRET"],
    )
)


class RefreshButton(discord.ui.Button):
    def __init__(self, tracks, current_track: discord.Spotify, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tracks = tracks
        self.current_track = current_track

    async def callback(self, interaction):
        if not self.tracks:
            self.disabled = True  # Disable the button if no tracks are left
            return await interaction.response.edit_message(view=self.view)

        track = self.tracks.pop(0)

        embed = discord.Embed(
            color=config["COLORS"]["SUCCESS"],
        )
        embed.add_field(
            name="Song",
            value=track["name"],
        )
        embed.add_field(
            name="Artist",
            value=track["artists"][0]["name"],
        )
        embed.add_field(
            name="Album",
            value=track["album"]["name"],
        )
        embed.add_field(
            name="Duration",
            value=f"{track['duration_ms'] // 60000}:{(track['duration_ms'] // 1000) % 60:02}",
        )

        embed.set_thumbnail(url=track["album"]["images"][0]["url"])

        open_in_spotify = discord.ui.Button(
            label="Open in Spotify",
            url=track["external_urls"]["spotify"],
            style=discord.ButtonStyle.link,
        )

        self.view.clear_items()
        self.view.add_item(self)
        self.view.add_item(open_in_spotify)

        await interaction.response.edit_message(
            content=f"Recommended song based on **{self.current_track.title}** by **{self.current_track.artists[0]}**",
            embed=embed,
            view=self.view,
        )


class PlaylistButton(discord.ui.Button):
    def __init__(self, playlists, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.playlists = playlists
        self.current_index = 0

    async def update_embed(self, interaction: discord.Interaction):
        playlist = self.playlists[self.current_index]
        playlist_tracks = sp.playlist_tracks(playlist["id"])
        tracks = playlist_tracks["items"][:5]

        embed = discord.Embed(
            title=playlist["name"],
            description=playlist["description"]
            + "\n\n"
            + "\n".join(
                f"{index + 1}. [{track['track']['name']}]({track['track']['external_urls']['spotify']})"
                for index, track in enumerate(tracks)
            ),
            color=config["COLORS"]["SUCCESS"],
        )
        embed.add_field(
            name="Total Tracks",
            value=playlist_tracks["total"],
            inline=False,
        )

        open_in_spotify = discord.ui.Button(
            label="Open in Spotify",
            url=playlist["external_urls"]["spotify"],
            style=discord.ButtonStyle.link,
        )

        self.view.clear_items()
        self.view.add_item(self)
        self.view.add_item(open_in_spotify)

        if playlist["images"]:
            embed.set_thumbnail(url=playlist["images"][0]["url"])
        await interaction.response.edit_message(embed=embed, view=self.view)


class NextButton(PlaylistButton):
    async def callback(self, interaction: discord.Interaction):
        self.current_index = (self.current_index + 1) % len(self.playlists)
        await self.update_embed(interaction)


class LastFM(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.db_path = "kino.db"
        self.bot.loop.create_task(self.setup_db())

    async def setup_db(self):
        self.conn = await aiosqlite.connect(self.db_path)

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        command_name = ctx.command.name

        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM disabled_commands WHERE command = ?", (command_name,)
            )
            if await cur.fetchone():
                embed = discord.Embed(
                    title="Command Disabled",
                    description=f"The command `{command_name}` is currently disabled in this guild.",
                    color=discord.Color.red(),
                )
                embed.set_footer(text="This message will be deleted in 10 seconds.")
                embed.set_author(
                    name=self.bot.user.display_name, icon_url=self.bot.user.avatar.url
                )
                await ctx.respond(embed=embed, ephemeral=True, delete_after=10)
                raise commands.CommandInvokeError(
                    f"Command `{command_name}` is disabled."
                )

    _lastfm = discord.commands.SlashCommandGroup(
        name="lastfm", description="LastFM related commands."
    )

    @_lastfm.command(
        name="set",
        description="Set your LastFM username.",
        username=discord.Option(
            str,
            description="Your LastFM username.",
            required=True,
        ),
    )
    async def _set(self, ctx: discord.ApplicationContext, username: str):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "CREATE TABLE IF NOT EXISTS lastfm (user_id INTEGER PRIMARY KEY, username TEXT)"
            )

            await cur.execute(
                "SELECT 1 FROM lastfm WHERE user_id = ?", (ctx.author.id,)
            )
            if await cur.fetchone():
                await cur.execute(
                    "UPDATE lastfm SET username = ? WHERE user_id = ?",
                    (username, ctx.author.id),
                )
                return await ctx.respond(
                    f"Successfully updated your LastFM username to `{username}`.",
                    ephemeral=True,
                )

            await cur.execute(
                "INSERT INTO lastfm (user_id, username) VALUES (?, ?)",
                (ctx.author.id, username),
            )
            await ctx.respond(
                f"Successfully set your LastFM username to `{username}`.",
                ephemeral=True,
            )
        await self.conn.commit()

    @_lastfm.command(
        name="spotify",
        description="Gives Spotify link for the current song playing.",
    )
    async def _spotify(self, ctx: discord.ApplicationContext):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT username FROM lastfm WHERE user_id = ?", (ctx.author.id,)
            )
            username = await cur.fetchone()
            if not username:
                return await ctx.respond(
                    "You haven't set your LastFM username yet. Use `/lastfm set` to set it.",
                    ephemeral=True,
                )

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={username[0]}&api_key={config['LASTFM_API_KEY']}&format=json"
            ) as response:
                data = await response.json()

        if "error" in data:
            return await ctx.respond(
                f"Error: {data['message']}",
                ephemeral=True,
            )

        if not data["recenttracks"]["track"]:
            return await ctx.respond(
                "You haven't listened to any songs yet.",
                ephemeral=True,
            )

        track = data["recenttracks"]["track"][0]
        results = sp.search(
            q=f"track:{track['name']} artist:{track['artist']['#text']}"
        )
        if not results["tracks"]["items"]:
            return await ctx.respond(
                "Couldn't find the song on Spotify.",
                ephemeral=True,
            )

        track = results["tracks"]["items"][0]
        await ctx.respond(track["external_urls"]["spotify"])

    @_lastfm.command(
        name="np",
        description="Shows the song you're currently listening to.",
    )
    async def _np(self, ctx: discord.ApplicationContext):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT username FROM lastfm WHERE user_id = ?", (ctx.author.id,)
            )
            username = await cur.fetchone()
            if not username:
                return await ctx.respond(
                    "You haven't set your LastFM username yet. Use `/lastfm set` to set it.",
                    ephemeral=True,
                )

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={username[0]}&api_key={config['LASTFM_API_KEY']}&format=json"
            ) as response:
                data = await response.json()

        if "error" in data:
            return await ctx.respond(
                f"Error: {data['message']}",
                ephemeral=True,
            )

        if not data["recenttracks"]["track"]:
            return await ctx.respond(
                "You haven't listened to any songs yet.",
                ephemeral=True,
            )

        track = data["recenttracks"]["track"][0]
        embed = discord.Embed(
            description=f"[{track['name']}]({track['url']})",
            color=config["COLORS"]["SUCCESS"],
        )

        results = sp.search(
            q=f"track:{track['name']} artist:{track['artist']['#text']}"
        )
        if results["tracks"]["items"]:
            spotify_track = results["tracks"]["items"][0]
            embed.set_thumbnail(url=spotify_track["album"]["images"][0]["url"])

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://ws.audioscrobbler.com/2.0/?method=track.getInfo&api_key={config['LASTFM_API_KEY']}&artist={track['artist']['#text']}&track={track['name']}&format=json"
            ) as response:
                data = await response.json()

        if "error" in data:
            return await ctx.respond(
                f"Error: {data['message']}",
                ephemeral=True,
            )

        embed.add_field(
            name="Artist",
            value=track["artist"]["#text"],
            inline=True,
        )

        embed.add_field(
            name="Total Scrobbles",
            value=data["track"]["playcount"],
            inline=True,
        )

        if "@attr" not in track:
            embed.add_field(
                name="Last Played",
                value=f"<t:{int(track['date']['uts'])}:R>",
                inline=True,
            )

        listen_on_spotify = discord.ui.Button(
            label="Listen on Spotify",
            url=spotify_track["external_urls"]["spotify"],
            style=discord.ButtonStyle.link,
        )

        view = discord.ui.View()
        view.add_item(listen_on_spotify)

        await ctx.respond(embed=embed, view=view)

    @_lastfm.command(
        name="whois",
        description="View Last.fm profile information",
    )
    async def lastfm_whois(
        self,
        ctx: discord.ApplicationContext,
        username: discord.Option(
            str, description="The username to search for.", required=True
        ),
    ):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://ws.audioscrobbler.com/2.0/?method=user.getinfo&user={username}&api_key={config['LASTFM_API_KEY']}&format=json"
            ) as response:
                data = await response.json()

        if "error" in data:
            return await ctx.respond(
                f"Error: {data['message']}",
                ephemeral=True,
            )

        user = data["user"]
        embed = discord.Embed(
            description=f"User profile for **{user['name']}**",
            color=config["COLORS"]["SUCCESS"],
        )

        embed.add_field(name="Play Count", value=user["playcount"])
        embed.add_field(name="Artist Count", value=user.get("artist_count", "N/A"))
        embed.add_field(name="Track Count", value=user.get("track_count", "N/A"))
        embed.add_field(name="Album Count", value=user.get("album_count", "N/A"))
        embed.add_field(name="Country", value=user.get("country", "N/A"))
        embed.add_field(
            name="User Registered", value=f"<t:{user['registered']['unixtime']}:R>"
        )

        go_to_profile = discord.ui.Button(
            label="Go to Profile",
            url=user["url"],
            style=discord.ButtonStyle.link,
        )

        view = discord.ui.View()
        view.add_item(go_to_profile)

        if user["image"]:
            embed.set_thumbnail(url=user["image"][3]["#text"])

        await ctx.respond(embed=embed, view=view)

    @_lastfm.command(
        name="topartists",
        description="View your most listened to artists",
    )
    async def lastfm_topartists(self, ctx: discord.ApplicationContext):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT username FROM lastfm WHERE user_id = ?", (ctx.author.id,)
            )
            username = await cur.fetchone()
            if not username:
                return await ctx.respond(
                    "You haven't set your LastFM username yet. Use `/lastfm set` to set it.",
                    ephemeral=True,
                )
            username = username[0]

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://ws.audioscrobbler.com/2.0/?method=user.gettopartists&user={username}&api_key={config['LASTFM_API_KEY']}&format=json"
            ) as response:
                data = await response.json()

        if "error" in data:
            return await ctx.respond(
                f"Error: {data['message']}",
                ephemeral=True,
            )

        artists = data["topartists"]["artist"]
        embed = discord.Embed(
            color=config["COLORS"]["SUCCESS"],
        )
        description = "".join(
            f"{index + 1}. [{artist['name']}]({artist['url']}) - {artist['playcount']} plays\n"
            for index, artist in enumerate(artists[:10])
        )
        embed.description = description
        await ctx.respond(embed=embed)

    @_lastfm.command(
        name="topalbums",
        description="View your most listened to albums",
    )
    async def lastfm_topalbums(self, ctx: discord.ApplicationContext):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT username FROM lastfm WHERE user_id = ?", (ctx.author.id,)
            )
            username = await cur.fetchone()
            if not username:
                return await ctx.respond(
                    "You haven't set your LastFM username yet. Use `/lastfm set` to set it.",
                    ephemeral=True,
                )
            username = username[0]

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://ws.audioscrobbler.com/2.0/?method=user.gettopalbums&user={username}&api_key={config['LASTFM_API_KEY']}&format=json"
            ) as response:
                data = await response.json()

        if "error" in data:
            return await ctx.respond(
                f"Error: {data['message']}",
                ephemeral=True,
            )

        albums = data["topalbums"]["album"]

        top_albums = []
        for album in albums[:10]:
            top_albums.append(
                {
                    "name": album["name"],
                    "artist": album["artist"]["name"],
                    "playcount": album["playcount"],
                    "image": album["image"][2]["#text"],
                }
            )

        data = json_to_base64(top_albums)
        url = f"https://uni-ui-nine.vercel.app/lastfm/topalbums?data={data}"

        await ctx.defer()
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(
                device_scale_factor=4.0,
                viewport={"width": 800, "height": 600},
            )
            await page.goto(url)
            await asyncio.sleep(2)
            await page.locator(".card").screenshot(
                path="temp/top-albums.png", type="jpeg", quality=100
            )
            await browser.close()

        await ctx.respond(file=discord.File("temp/top-albums.png"))

    @_lastfm.command(
        name="toptracks",
        description="View your most listened to tracks.",
    )
    async def lastfm_toptracks(
        self,
        ctx: discord.ApplicationContext,
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT username FROM lastfm WHERE user_id = ?", (ctx.author.id,)
            )
            username = await cur.fetchone()
            if not username:
                return await ctx.respond(
                    "You haven't set your LastFM username yet. Use `/lastfm set` to set it.",
                    ephemeral=True,
                )
            username = username[0]

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://ws.audioscrobbler.com/2.0/?method=user.gettoptracks&user={username}&api_key={config['LASTFM_API_KEY']}&format=json"
            ) as response:
                data = await response.json()

        if "error" in data:
            return await ctx.respond(
                f"Error: {data['message']}",
                ephemeral=True,
            )

        tracks = data["toptracks"]["track"]

        top_tracks = []
        for track in tracks[:10]:
            top_tracks.append(
                {
                    "name": track["name"],
                    "artist": track["artist"]["name"],
                    "playcount": track["playcount"],
                    "image": track["image"][2]["#text"],
                }
            )

        data = json_to_base64(top_tracks)
        url = f"https://uni-ui-nine.vercel.app/lastfm/toptracks?data={data}"

        await ctx.defer()

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(
                device_scale_factor=4.0,
                viewport={"width": 800, "height": 600},
            )
            await page.goto(url)
            await asyncio.sleep(2)
            await page.locator(".card").screenshot(
                path="temp/top-tracks.png", type="jpeg", quality=100
            )
            await browser.close()

        await ctx.respond(file=discord.File("temp/top-tracks.png"))

    _spotify = discord.commands.SlashCommandGroup(
        name="spotify", description="Spotify related commands."
    )

    @_spotify.command(
        name="search",
        description="Search for a song on Spotify.",
    )
    async def spotify_search(
        self,
        ctx: discord.ApplicationContext,
        query: discord.Option(
            str, description="The song to search for.", required=True
        ),
    ):
        results = sp.search(q=query)
        tracks = results.get("tracks", {}).get("items")

        if not tracks:
            await ctx.respond(
                "Couldn't find the song on Spotify.",
                ephemeral=True,
            )
            return

        track_url = tracks[0].get("external_urls", {}).get("spotify", "URL not found")
        await ctx.respond(track_url)

    @_spotify.command(
        name="np",
        description="Shows the song you're currently listening to.",
    )
    async def spotify_np(self, ctx: discord.ApplicationContext):
        spotify_activity = next(
            (
                activity
                for activity in ctx.author.activities
                if isinstance(activity, discord.Spotify)
            ),
            None,
        )

        if not spotify_activity:
            return await ctx.respond("You are not currently listening to Spotify.")

        data = json_to_base64(
            {
                "title": spotify_activity.title,
                "artists": spotify_activity.artists,
                "album": spotify_activity.album,
                "album_cover_url": spotify_activity.album_cover_url,
                "start_time": spotify_activity.start.isoformat(),
                "end_time": spotify_activity.end.isoformat(),
                "duration": spotify_activity.duration.total_seconds(),
            }
        )

        url = f"https://uni-ui-nine.vercel.app/spotify/np?data={data}"

        print(url)

        await ctx.defer()
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(
                device_scale_factor=4.0,
                viewport={"width": 800, "height": 600},
            )
            await page.goto(url)
            await asyncio.sleep(2)
            await page.locator(".card").screenshot(
                path="temp/spotify-np.png", type="jpeg", quality=100
            )
            await browser.close()

        await ctx.respond(file=discord.File("temp/spotify-np.png"))

    @_spotify.command(
        name="recommend",
        description="Recommends you a song based on what you're currently listening to.",
    )
    async def spotify_recommend(self, ctx: discord.ApplicationContext):
        if spotify_activity := next(
            (
                activity
                for activity in ctx.author.activities
                if isinstance(activity, discord.Spotify)
            ),
            None,
        ):
            await ctx.defer()

            results = sp.recommendations(
                seed_tracks=[spotify_activity.track_id], limit=20
            )

            tracks = results["tracks"]
            refresh_button = RefreshButton(
                tracks=tracks,
                current_track=spotify_activity,
                label="Refresh",
                style=discord.ButtonStyle.primary,
            )

            initial_track = tracks.pop(0)

            open_in_spotify = discord.ui.Button(
                label="Open in Spotify",
                url=initial_track["external_urls"]["spotify"],
                style=discord.ButtonStyle.link,
            )

            view = discord.ui.View()
            view.add_item(refresh_button)
            view.add_item(open_in_spotify)

            embed = discord.Embed(
                color=config["COLORS"]["SUCCESS"],
            )
            embed.add_field(
                name="Song",
                value=initial_track["name"],
            )
            embed.add_field(
                name="Artist",
                value=initial_track["artists"][0]["name"],
            )
            embed.add_field(
                name="Album",
                value=initial_track["album"]["name"],
            )
            embed.add_field(
                name="Duration",
                value=f"{initial_track['duration_ms'] // 60000}:{(initial_track['duration_ms'] // 1000) % 60:02}",
            )

            embed.set_thumbnail(url=initial_track["album"]["images"][0]["url"])

            await ctx.respond(
                content=f"Recommended song based on **{spotify_activity.title}** by **{spotify_activity.artists[0]}**",
                embed=embed,
                view=view,
            )

        else:
            return await ctx.respond("You are not currently listening to Spotify.")

    @_spotify.command(
        name="features",
        description="Gets audio features for the song you're currently listening to.",
    )
    async def spotify_features(self, ctx: discord.ApplicationContext):
        spotify_activity = next(
            (
                activity
                for activity in ctx.author.activities
                if isinstance(activity, discord.Spotify)
            ),
            None,
        )

        if not spotify_activity:
            return await ctx.respond("You are not currently listening to Spotify.")

        results = sp.audio_features(spotify_activity.track_id)
        features = results[0]

        embed = discord.Embed(
            color=config["COLORS"]["SUCCESS"],
        )

        embed.add_field(
            name="Danceability",
            value=f"`{create_progress_bar(features['danceability'])}` {round(features['danceability'], 2)}",
        )
        embed.add_field(
            name="Energy",
            value=f"`{create_progress_bar(features['energy'])}` {round(features['energy'], 2)}",
        )

        embed.add_field(
            name="Speechiness",
            value=f"`{create_progress_bar(features['speechiness'])}` {round(features['speechiness'], 2)}",
        )
        embed.add_field(
            name="Acousticness",
            value=f"`{create_progress_bar(features['acousticness'])}` {round(features['acousticness'], 2)}",
        )
        embed.add_field(
            name="Instrumentalness",
            value=f"`{create_progress_bar(features['instrumentalness'])}` {round(features['instrumentalness'], 2)}",
        )
        embed.add_field(
            name="Liveness",
            value=f"`{create_progress_bar(features['liveness'])}` {round(features['liveness'], 2)}",
        )
        embed.add_field(
            name="Valence",
            value=f"`{create_progress_bar(features['valence'])}` {round(features['valence'], 2)}",
        )
        embed.add_field(
            name="Tempo",
            value=features["tempo"],
        )
        embed.add_field(
            name="Time Signature",
            value=features["time_signature"],
        )
        embed.add_field(
            name="Key",
            value=features["key"],
        )
        embed.add_field(
            name="Loudness",
            value=features["loudness"],
        )
        embed.add_field(
            name="Mode",
            value=features["mode"],
        )

        await ctx.respond(embed=embed)

    @_spotify.command(
        name="whois",
        description="Get information about a Spotify user.",
    )
    async def spotify_whois(
        self,
        ctx: discord.ApplicationContext,
        username: discord.Option(
            str, description="The username to search for.", required=True
        ),
    ):
        user = sp.user(username)
        playlists = sp.user_playlists(username)
        total_playlists = playlists["total"]

        embed = discord.Embed(
            color=config["COLORS"]["SUCCESS"],
        )
        embed.set_thumbnail(url=user["images"][0]["url"])
        embed.add_field(name="ID", value=user["id"])
        embed.add_field(name="Followers", value=user["followers"]["total"])
        embed.add_field(name="Playlists", value=total_playlists)

        if user["images"]:
            embed.set_thumbnail(url=user["images"][1]["url"])

        open_in_spotify = discord.ui.Button(
            label="Open in Spotify",
            url=user["external_urls"]["spotify"],
            style=discord.ButtonStyle.link,
        )

        view = discord.ui.View()
        view.add_item(open_in_spotify)

        await ctx.respond(embed=embed, view=view)

    @_spotify.command(name="featured", description="Get Spotify's featured playlists.")
    async def spotify_featured(self, ctx: discord.ApplicationContext):
        playlists = sp.featured_playlists()["playlists"]["items"]

        playlist_tracks = sp.playlist_tracks(playlists[0]["id"])
        tracks = playlist_tracks["items"][:5]

        next_button = NextButton(
            playlists, label="Next", style=discord.ButtonStyle.primary
        )

        view = discord.ui.View()
        view.add_item(next_button)

        if playlists:
            initial_playlist = playlists[0]
            embed = discord.Embed(
                title=initial_playlist["name"],
                description=initial_playlist["description"]
                + "\n\n"
                + "\n".join(
                    f"{index + 1}. [{track['track']['name']}]({track['track']['external_urls']['spotify']})"
                    for index, track in enumerate(tracks)
                ),
                color=config["COLORS"]["SUCCESS"],
            )
            embed.add_field(
                name="Total Tracks",
                value=f"{playlist_tracks['total']} tracks",
                inline=False,
            )
            if initial_playlist["images"]:
                embed.set_thumbnail(url=initial_playlist["images"][0]["url"])

            open_in_spotify = discord.ui.Button(
                label="Open in Spotify",
                url=initial_playlist["external_urls"]["spotify"],
                style=discord.ButtonStyle.link,
            )

            view.add_item(open_in_spotify)

            await ctx.respond(embed=embed, view=view)
        else:
            await ctx.respond(content="No featured playlists found!", ephemeral=True)


def setup(bot_: discord.Bot):
    bot_.add_cog(LastFM(bot_))
