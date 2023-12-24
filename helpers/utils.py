import discord
import aiosqlite
import aiohttp


from datetime import datetime, timezone


def iso_to_discord_timestamp(iso_date) -> str:
    date_obj = datetime.fromisoformat(iso_date.rstrip("Z")).replace(tzinfo=timezone.utc)
    timestamp = int(date_obj.timestamp())
    return f"<t:{timestamp}:R>"


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


async def fetch_latest_commit_info() -> dict:
    repo_url = "https://api.github.com/repos/notjawad/uni/commits/main"
    async with aiohttp.ClientSession() as session:
        async with session.get(repo_url) as response:
            if response.status != 200:
                return "Error: Unable to fetch commit info"
            json_response = await response.json()
            return {
                "id": json_response["sha"],
                "message": json_response["commit"]["message"],
                "author": json_response["commit"]["committer"]["name"],
                "date": json_response["commit"]["committer"]["date"],
                "url": json_response["html_url"],
            }


async def is_premium(member: discord.Member, conn: aiosqlite.Connection) -> bool:
    async with conn.execute(
        "SELECT * FROM premium_users WHERE user_id = ?", (member.id,)
    ) as cursor:
        return await cursor.fetchone() is not None
