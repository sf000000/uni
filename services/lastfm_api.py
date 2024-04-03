from typing import Dict, Optional, Union

import httpx


class LastFMAPI:
    def __init__(
        self, api_key: str, base_url: str = "https://ws.audioscrobbler.com/2.0/"
    ):
        self.api_key = api_key
        self.base_url = base_url

    async def get_user_info(self, username: str) -> Optional[Dict[str, any]]:
        """
        Get information about a LastFM user.

        Args:
            username (str): The LastFM username.

        Returns:
            Optional[Dict[str, any]]: The user information, or None if the request fails.
        """
        params = {
            "method": "user.getinfo",
            "user": username,
            "api_key": self.api_key,
            "format": "json",
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(self.base_url, params=params)
            if response.status_code != 200:
                return None
            return response.json()["user"]

    async def get_recent_tracks(
        self, username: str, limit: int = 10
    ) -> Union[Dict[str, any], str]:
        """
        Get the recent tracks listened to by a LastFM user.

        Args:
            username (str): The LastFM username.
            limit (int): The maximum number of tracks to return (default is 10).

        Returns:
            Union[Dict[str, any], str]: The recent tracks information, or an error message if the request fails.
        """
        params = {
            "method": "user.getrecenttracks",
            "user": username,
            "limit": limit,
            "api_key": self.api_key,
            "format": "json",
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(self.base_url, params=params)
            if response.status_code != 200:
                return "Invalid username or API key."
            return response.json()["recenttracks"]

    async def get_top_artists(
        self, username: str, period: str = "overall", limit: int = 10
    ) -> Union[Dict[str, any], str]:
        """
        Get the top artists for a LastFM user.

        Args:
            username (str): The LastFM username.
            period (str): The time period to get the top artists for (default is "overall").
            limit (int): The maximum number of artists to return (default is 10).

        Returns:
            Union[Dict[str, any], str]: The top artists information, or an error message if the request fails.
        """
        params = {
            "method": "user.gettopartists",
            "user": username,
            "period": period,
            "limit": limit,
            "api_key": self.api_key,
            "format": "json",
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(self.base_url, params=params)
            if response.status_code != 200:
                return "Invalid username or API key."
            return response.json()["topartists"]
