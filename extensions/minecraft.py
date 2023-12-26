import discord
import aiosqlite
import yaml
import aiohttp
import datetime

from discord.ext import commands, tasks


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class Minecraft(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.db_path = "kino.db"
        self.bot.loop.create_task(self.setup_db())
        self.update_minecraft_status.start()

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

    _minecraft = discord.commands.SlashCommandGroup(
        name="minecraft", description="Minecraft related commands."
    )

    _server = _minecraft.create_subgroup(
        name="serverstatus", description="Set up server status message."
    )

    @_server.command(
        name="set",
        description="Set up server status message.",
    )
    @commands.has_permissions(manage_guild=True)
    async def _set_server_status(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.Option(
            discord.TextChannel,
            description="The channel to send the message to.",
            required=True,
        ),
        ip: discord.Option(str, description="The IP of the server.", required=True),
        port: discord.Option(
            int,
            description="The port of the server.",
            required=False,
            default=25565,
        ),
    ):
        initial_message = await channel.send(
            embed=await self.create_status_embed(ip, port),
            allowed_mentions=discord.AllowedMentions.none(),
        )

        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM minecraft_server_status WHERE guild_id = ?",
                (ctx.guild.id,),
            )

            if await cur.fetchone():
                await cur.execute(
                    "UPDATE minecraft_server_status SET channel_id = ?, message_id = ?, ip = ?, port = ? WHERE guild_id = ?",
                    (
                        channel.id,
                        initial_message.id,
                        ip,
                        port,
                        ctx.guild.id,
                    ),
                )
                await self.conn.commit()
                return await ctx.respond(
                    embed=discord.Embed(
                        description=f"Server status message updated to {channel.mention}.",
                        color=config["COLORS"]["SUCCESS"],
                    )
                )

            await cur.execute(
                "INSERT INTO minecraft_server_status (guild_id, channel_id, message_id, ip, port) VALUES (?, ?, ?, ?, ?)",
                (
                    ctx.guild.id,
                    channel.id,
                    initial_message.id,
                    ip,
                    port,
                ),
            )
            await self.conn.commit()

        await ctx.respond(
            embed=discord.Embed(
                description=f"Server status message set to {channel.mention}.",
                color=config["COLORS"]["SUCCESS"],
            )
        )

    async def create_status_embed(self, ip: str, port: int):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.mcsrvstat.us/3/{ip}:{port}"
            ) as response:
                data = await response.json()

        if data["online"]:
            embed = discord.Embed(
                title=data["motd"]["clean"][0],
                description=data["motd"]["clean"][1],
                color=config["COLORS"]["SUCCESS"],
            )
            embed.add_field(
                name="👥 Players",
                value=f"{data['players']['online']}/{data['players']['max']}",
                inline=False,
            )
            embed.add_field(name="🏷️ Version", value=data["version"], inline=False)
            embed.add_field(name="🌍 IP", value=f"```{ip}```", inline=False)
            embed.add_field(name="🔌 Port", value=f"```{port}```", inline=False)
            embed.add_field(
                name="📅 Updated At",
                value=f"<t:{int(datetime.datetime.now().timestamp())}:R>",
                inline=False,
            )

            return embed

    @tasks.loop(minutes=5)
    async def update_minecraft_status(self):
        await self.bot.wait_until_ready()

        async with self.conn.cursor() as cur:
            await cur.execute("SELECT * FROM minecraft_server_status")
            try:
                async for row in cur:
                    guild = self.bot.get_guild(row[0])
                    channel = guild.get_channel(row[1])
                    message = await channel.fetch_message(row[2])

                    embed = await self.create_status_embed(row[3], row[4])
                    await message.edit(embed=embed)
            except Exception as e:
                print(e)


def setup(bot_: discord.Bot):
    bot_.add_cog(Minecraft(bot_))
