from typing import List, Optional, Dict, Union
import httpx


class TopGGManager:
    """
    A class that provides asynchronous methods to interact with the Top.gg API.

    Args:
        api_token (str): The API token for authentication.

    Attributes:
        api_base_url (str): The base URL of the Top.gg API.
        headers (dict): The headers for API requests.
    """

    def __init__(self, api_token: str):
        self.api_base_url = "https://top.gg/api/"
        self.headers = {"Authorization": api_token}

    async def search_bots(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0,
        sort: Optional[str] = None,
        fields: Optional[str] = None,
    ) -> Dict[str, Union[List[Dict], int]]:
        params = {"limit": limit, "offset": offset, "search": query}
        if sort:
            params["sort"] = sort
        if fields:
            params["fields"] = fields

        async with httpx.AsyncClient() as client:
            response = await self._get_request(client, "bots", params=params)
        return response.json()

    async def find_bot(self, bot_id: str) -> Dict:
        async with httpx.AsyncClient() as client:
            response = await self._get_request(client, f"bots/{bot_id}")
        return response.json()

    async def get_last_1000_votes(self, bot_id: str) -> List[Dict[str, str]]:
        async with httpx.AsyncClient() as client:
            response = await self._get_request(client, f"bots/{bot_id}/votes")
        return response.json()

    async def get_bot_stats(self, bot_id: str) -> Dict:
        async with httpx.AsyncClient() as client:
            response = await self._get_request(client, f"bots/{bot_id}/stats")
        return response.json()

    async def check_user_vote(self, bot_id: str, user_id: str) -> Dict[str, int]:
        params = {"userId": user_id}
        async with httpx.AsyncClient() as client:
            response = await self._get_request(
                client, f"bots/{bot_id}/check", params=params
            )
        return response.json()

    async def post_bot_stats(
        self,
        bot_id: str,
        server_count: int,
        shards: Optional[List[int]] = None,
        shard_id: Optional[int] = None,
        shard_count: Optional[int] = None,
    ) -> Dict:
        data = {"server_count": server_count}
        if shards:
            data["shards"] = shards
        if shard_id is not None:
            data["shard_id"] = shard_id
        if shard_count is not None:
            data["shard_count"] = shard_count

        async with httpx.AsyncClient() as client:
            response = await self._post_request(
                client, f"bots/{bot_id}/stats", data=data
            )
        return response.json()

    async def _get_request(
        self, client: httpx.AsyncClient, endpoint: str, params: Optional[Dict] = None
    ) -> httpx.Response:
        url = f"{self.api_base_url}{endpoint}"
        response = await client.get(url, params=params, headers=self.headers)
        response.raise_for_status()
        return response

    async def _post_request(
        self, client: httpx.AsyncClient, endpoint: str, data: Optional[Dict] = None
    ) -> httpx.Response:
        url = f"{self.api_base_url}{endpoint}"
        response = await client.post(url, json=data, headers=self.headers)
        response.raise_for_status()
        return response
