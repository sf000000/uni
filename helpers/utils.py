import discord
import aiosqlite


async def log(guild: discord.Guild, embed: discord.Embed, conn: aiosqlite.Connection):
    async with conn.execute(
        "SELECT channel_id FROM logging WHERE guild_id = ?", (guild.id,)
    ) as cursor:
        channel_id = await cursor.fetchone()

    if not channel_id:
        return

    if channel := guild.get_channel(channel_id[0]):
        await channel.send(embed=embed)
    else:
        return
