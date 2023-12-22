import discord
import aiosqlite
import yaml
import aiohttp

from discord.ext import commands, tasks


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class Twitch(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.db_path = "kino.db"
        self.bot.loop.create_task(self.setup_db())
        self.check_streams.start()

    async def setup_db(self):
        self.conn = await aiosqlite.connect(self.db_path)

    async def channel_autocomplete(self, ctx: discord.ApplicationContext, string: str):
        channels = ctx.guild.channels
        return [
            channel for channel in channels if string.lower() in channel.name.lower()
        ]

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

    async def get_stream(self, twitch_channel: str):
        headers = {
            "Client-ID": config["TWITCH"]["CLIENT_ID"],
            "Authorization": f"Bearer {config['TWITCH']['ACCESS_TOKEN']}",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.twitch.tv/helix/streams?user_login={twitch_channel}",
                headers=headers,
            ) as response:
                return await response.json() if response.status == 200 else None

    _twitch = discord.commands.SlashCommandGroup(
        name="twitch", description="Twitch related commands."
    )

    @_twitch.command(
        name="enable",
        description="Enables Twitch notifications",
    )
    @commands.has_permissions(administrator=True)
    async def _enable(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.Option(
            discord.TextChannel, "Select a channel", autocomplete=channel_autocomplete
        ),
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO twitch_notifications (guild_id, channel_id) VALUES (?, ?)",
                (ctx.guild.id, channel.id),
            )
            await self.conn.commit()

        embed = discord.Embed(
            description=f"Twitch notifications will now be sent to {channel.mention}.",
            color=config["COLORS"]["BLURPLE"],
        )
        await ctx.respond(embed=embed)

    @_twitch.command(
        name="disable",
        description="Disables Twitch notifications",
    )
    @commands.has_permissions(administrator=True)
    async def _disable(
        self,
        ctx: discord.ApplicationContext,
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM twitch_notifications WHERE guild_id = ?", (ctx.guild.id,)
            )
            await self.conn.commit()

        embed = discord.Embed(
            description="Twitch notifications have been disabled.",
            color=config["COLORS"]["SUCCESS"],
        )
        await ctx.respond(embed=embed)

    @_twitch.command(
        name="add",
        description="Adds a Twitch channel to the notification list.",
    )
    @commands.has_permissions(administrator=True)
    async def _add(
        self,
        ctx: discord.ApplicationContext,
        channel_name: discord.Option(
            name="channel",
            description="The channel to add to the notification list.",
            required=True,
        ),
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO twitch_streamers (channel_name, guild_id) VALUES (?, ?)",
                (channel_name, ctx.guild.id),
            )
            await self.conn.commit()

        embed = discord.Embed(
            description=f"Added `{channel_name}` to the notification list.",
            color=config["COLORS"]["BLURPLE"],
        )
        await ctx.respond(embed=embed)

    @_twitch.command(
        name="remove",
        description="Removes a Twitch channel from the notification list.",
    )
    @commands.has_permissions(administrator=True)
    async def _remove(
        self,
        ctx: discord.ApplicationContext,
        channel_name: discord.Option(
            name="channel",
            description="The channel to remove from the notification list.",
            required=True,
        ),
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM twitch_streamers WHERE channel_name = ? AND guild_id = ?",
                (channel_name, ctx.guild.id),
            )
            await self.conn.commit()

        embed = discord.Embed(
            description=f"Removed `{channel_name}` from the notification list.",
            color=config["COLORS"]["SUCCESS"],
        )
        await ctx.respond(embed=embed)

    @_twitch.command(
        name="list",
        description="Lists all Twitch channels in the notification list.",
    )
    @commands.has_permissions(administrator=True)
    async def _list(
        self,
        ctx: discord.ApplicationContext,
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT channel_name FROM twitch_streamers WHERE guild_id = ?",
                (ctx.guild.id,),
            )
            streamers = await cur.fetchall()

        embed = discord.Embed(
            description="\n".join([f"• {streamer[0]}" for streamer in streamers]),
            color=config["COLORS"]["BLURPLE"],
        )
        await ctx.respond(embed=embed)

    @tasks.loop(minutes=2)
    async def check_streams(self):
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                SELECT ts.channel_name, ts.guild_id, tn.channel_id, ts.is_live, ts.notification_sent
                FROM twitch_streamers ts
                INNER JOIN twitch_notifications tn ON ts.guild_id = tn.guild_id
            """
            )
            streamers = await cur.fetchall()

            for streamer in streamers:
                (
                    channel_name,
                    guild_id,
                    notification_channel_id,
                    is_live,
                    notification_sent,
                ) = streamer
                stream_data = await self.get_stream(channel_name)

                currently_live = (
                    len(stream_data.get("data", [])) > 0 if stream_data else False
                )

                if currently_live and not notification_sent:
                    if guild := self.bot.get_guild(int(guild_id)):
                        if channel := guild.get_channel(int(notification_channel_id)):
                            embed = discord.Embed(
                                description=f"**{stream_data['data'][0]['user_name']}** is now live on Twitch!",
                                color=config["COLORS"]["BLURPLE"],
                            )
                            embed.set_image(
                                url=stream_data["data"][0]["thumbnail_url"].format(
                                    width=1280, height=720
                                )
                            )
                            embed.add_field(
                                name="Stream Title",
                                value=stream_data["data"][0]["title"],
                            )
                            embed.add_field(
                                name="Game",
                                value=stream_data["data"][0]["game_name"],
                            )
                            embed.add_field(
                                name="Viewers",
                                value=f"{stream_data['data'][0]['viewer_count']:,}",
                            )
                            watch_button = discord.ui.Button(
                                style=discord.ButtonStyle.link,
                                label="Watch",
                                url=f"https://twitch.tv/{channel_name}",
                            )
                            view = discord.ui.View()
                            view.add_item(watch_button)

                            await channel.send(embed=embed, view=view)
                            await cur.execute(
                                "UPDATE twitch_streamers SET notification_sent = TRUE WHERE channel_name = ?",
                                (channel_name,),
                            )
                            await cur.execute(
                                "UPDATE twitch_streamers SET is_live = TRUE WHERE channel_name = ?",
                                (channel_name,),
                            )

                elif not currently_live and is_live:
                    await cur.execute(
                        "UPDATE twitch_streamers SET is_live = FALSE, notification_sent = FALSE WHERE channel_name = ?",
                        (channel_name,),
                    )

            await self.conn.commit()


def setup(bot_: discord.Bot):
    bot_.add_cog(Twitch(bot_))
