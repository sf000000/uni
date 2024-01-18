import discord
import aiosqlite
import aiohttp
import seaborn as sns


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


def create_progress_bar(value, max_blocks=10, full_block="█", empty_block="░"):
    filled_blocks = int(value * max_blocks)
    return full_block * filled_blocks + empty_block * (max_blocks - filled_blocks)


def set_seaborn_style(font_family, background_color, grid_color, text_color):
    sns.set_style(
        {
            "axes.facecolor": background_color,
            "figure.facecolor": background_color,
            "grid.color": grid_color,
            "axes.edgecolor": grid_color,
            "axes.grid": True,
            "axes.axisbelow": True,
            "axes.labelcolor": text_color,
            "text.color": text_color,
            "font.family": font_family,
            "xtick.color": text_color,
            "ytick.color": text_color,
            "xtick.bottom": False,
            "xtick.top": False,
            "ytick.left": False,
            "ytick.right": False,
            "axes.spines.left": False,
            "axes.spines.bottom": True,
            "axes.spines.right": False,
            "axes.spines.top": False,
        }
    )


def create_bar_chart(row, ax):
    num_colors = len(row)
    random_colors = sns.color_palette("husl", n_colors=num_colors)

    chart = sns.barplot(
        y=row.index.str.capitalize().values,
        x=row.values,
        orient="h",
        palette=random_colors,
        hue=row.index.str.capitalize().values,
        ax=ax,
        saturation=1,
        dodge=False,
        width=0.75,
        legend=False,
    )

    for index, value in enumerate(row.values):
        ax.text(value + 0.1, index, f"  {value}", color="white", ha="left", va="center")

    return chart
