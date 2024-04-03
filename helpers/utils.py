import base64
import json
import random
import re
import string
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Union

import httpx
import yaml

from helpers.constants import commit_emojis


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


def iso_to_discord(iso_date: str) -> str:
    """
    Converts an ISO 8601 date string to a Discord timestamp.

    Args:
        iso_date (str): The ISO 8601 date string to be converted.

    Returns:
        str: The Discord timestamp string.
    """
    date_obj = datetime.fromisoformat(iso_date.rstrip("Z")).replace(tzinfo=timezone.utc)
    timestamp = int(date_obj.timestamp())
    return f"<t:{timestamp}:R>"


async def latest_commit() -> Dict[str, str]:
    """
    Fetches the latest commit information from a GitHub repository.

    Returns:
        A dictionary containing the latest commit information with the following keys:
        - "id": The SHA of the commit.
        - "message": The commit message.
        - "author": The name of the committer.
        - "date": The date of the commit.
        - "url": The URL to view the commit on GitHub.

        If an error occurs, a dictionary containing the following keys is returned:
        - "error": The error message.
        - "status": The status code of the response.
    """
    config = load_config()

    repo_url = f"https://api.github.com/repos/{config['repo']}/commits/main"
    async with httpx.AsyncClient() as client:
        response = await client.get(repo_url)

        if response.status_code != 200:
            return {
                "error": f"Failed to fetch commit info: {response.text}",
                "status": f"{response.status_code}",
            }
        json_response = response.json()

        return {
            "id": json_response["sha"],
            "message": json_response["commit"]["message"],
            "author": json_response["commit"]["committer"]["name"],
            "date": json_response["commit"]["committer"]["date"],
            "url": json_response["html_url"],
        }


def create_progress_bar(
    value: Union[int, float],
    max_blocks: int = 10,
    full_block: str = "█",
    empty_block: str = "░",
) -> str:
    """
    Creates a progress bar string based on the given value and maximum blocks.

    Args:
        value (int or float): The current value to be represented in the progress bar.
        max_blocks (int, optional): The maximum number of blocks in the progress bar. Defaults to 10.
        full_block (str, optional): The character to use for filled blocks. Defaults to "█".
        empty_block (str, optional): The character to use for empty blocks. Defaults to "░".

    Returns:
        str: The progress bar string.
    """
    filled_blocks = int(value * max_blocks)
    return full_block * filled_blocks + empty_block * (max_blocks - filled_blocks)


def json_to_base64(json_obj: Dict[str, Union[str, int, float, bool, None]]) -> str:
    """
    Converts a JSON object to a base64-encoded string.

    Args:
        json_obj (dict): The JSON object to be converted.

    Returns:
        str: The base64-encoded string.
    """
    json_str = json.dumps(json_obj)
    return base64.b64encode(json_str.encode("utf-8")).decode("utf-8")


def commit_to_emoji(commit_msg: str) -> str:
    """
    Replaces the commit type with an emoji in the given commit message.

    Args:
        commit_msg (str): The commit message to be processed.

    Returns:
        str: The updated commit message with the commit type replaced by an emoji.
    """
    commit_msg = commit_msg.lstrip("* ").strip()

    match: Optional[Tuple[str, str, str]] = re.match(
        r"(feat|fix|docs|style|refactor|test|chore)\((.*?)\):(.*)", commit_msg
    )
    if match:
        commit_type, extension_name, description = match.groups()

        if extension_name.endswith(".py"):
            extension_name = f"**{extension_name}**"

        if commit_type in commit_emojis:
            return f"{commit_emojis[commit_type]}: ({extension_name}):{description}"

    return commit_msg


def nano_id():
    """
    Generates a 6-character ID.

    Returns:
        str: A 6-character ID.
    """
    characters = string.ascii_letters + string.digits
    nano_id = "".join(random.choice(characters) for _ in range(6))
    return nano_id


def localize_number(number: int) -> str:
    """
    Localizes a number by adding commas to the thousands, millions, etc.

    Args:
        number (int): The number to be localized.

    Returns:
        str: The localized number as a string.
    """
    if number < 1000:
        return str(number)
    else:
        return localize_number(number // 1000) + "," + "{:03d}".format(number % 1000)


def ms_to_hours(milliseconds: int) -> float:
    hours = milliseconds / (1000 * 60 * 60)
    return hours


def format_time(time: int) -> str:
    return str(datetime.timedelta(milliseconds=time))[2:].split(".")[0]


def truncate_text(text: str, max_length: int) -> str:
    return text if len(text) <= max_length else f"{text[:max_length - 3]}..."
