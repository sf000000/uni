import datetime
from io import BytesIO

import discord
import httpx
import pytz
from httpx import Timeout

from helpers.utils import json_to_base64, truncate_text


class UI:
    def __init__(self, base_url: str = "http://localhost:3000/api"):
        self.base_url = base_url

    async def welcome_card(
        self,
        avatar: str,
        member_count: str,
        username: str,
        created_at: datetime.datetime,
        accent_color: str,
        avatar_decoration: str = None,
    ) -> discord.File:
        delta = datetime.datetime.now(tz=pytz.utc) - created_at

        data = json_to_base64(
            {
                "avatar": avatar,
                "member_count": member_count,
                "username": truncate_text(username, 10),
                "created_at": f"{delta.days} days ago",
                "accent_color": accent_color,
                "avatar_decoration": avatar_decoration,
            }
        )

        url = f"{self.base_url}/welcome?data={data}&nodeId=capture"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=Timeout(10.0, connect=60.0))
            return discord.File(BytesIO(response.content), "welcome.png")
