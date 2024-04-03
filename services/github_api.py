from typing import Dict, List, Optional, Union

import httpx


class GitHubAPI:
    def __init__(self, base_url: str = "https://api.github.com"):
        self.base_url = base_url

    async def get_pr_info(self, repo: str, pr_number: int) -> Optional[Dict[str, any]]:
        """
        Get information about a pull request.

        Args:
            repo (str): The repository to get the pull request from. (e.g. uni-bot/uni)
            pr_number (int): The pull request number.

        Returns:
            Optional[Dict[str, any]]: The pull request information, or None if the request fails.
        """
        url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code != 200:
                return None
            return response.json()

    async def get_issue_info(
        self, repo: str, issue_number: int
    ) -> Union[Dict[str, any], str]:
        """
        Get information about an issue.

        Args:
            repo (str): The repository to get the issue from. (e.g. uni-bot/uni)
            issue_number (int): The issue number.

        Returns:
            Union[Dict[str, any], str]: The issue information, or an error message if the request fails.
        """
        url = f"{self.base_url}/repos/{repo}/issues/{issue_number}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code != 200:
                return "Invalid repository or issue number."
            return response.json()

    async def get_repo_info(self, repo: str) -> Union[Dict[str, any], str]:
        """
        Get information about a repository.

        Args:
            repo (str): The repository to get the information for. (e.g. uni-bot/uni)

        Returns:
            Union[Dict[str, any], str]: The repository information, or an error message if the request fails.
        """
        url = f"{self.base_url}/repos/{repo}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code != 200:
                return "Invalid repository."
            return response.json()

    async def get_user_info(self, user: str) -> Union[Dict[str, any], str]:
        """
        Get information about a user.

        Args:
            user (str): The username of the user to get the information for.

        Returns:
            Union[Dict[str, any], str]: The user information, or an error message if the request fails.
        """
        url = f"{self.base_url}/users/{user}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code != 200:
                return "Invalid user."
            return response.json()

    async def get_latest_commit_info(
        self, repo: str
    ) -> Union[List[Dict[str, any]], str]:
        """
        Get information about the latest 10 commits in a repository.

        Args:
            repo (str): The repository to get the commit information for. (e.g. uni-bot/uni)

        Returns:
            Union[List[Dict[str, any]], str]: A list of the latest 10 commit information, or an error message if the request fails.
        """
        url = f"{self.base_url}/repos/{repo}/commits"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code != 200:
                return "Invalid repository."
            return response.json()[:10]
