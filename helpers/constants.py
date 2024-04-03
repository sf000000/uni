from typing import Dict

# Custom emojis need to be replaced if self-hosting
emojis: Dict[str, str] = {
    "check": "✅",
    "github": "<:github:1189774714592313475>",
    "pr_open": "<:pr_open:1224776505582948433>",
    "pr_merged": "<:pr_merged:1224778251461722284>",
    "pr_closed": "<:pr_closed:1224779022186319953>",
    "issue_open": "<:issue_open:1224787851431116840>",
    "issue_closed": "<:issue_closed:1224787850529210488>",
}

file_emoji_dict: Dict[str, str] = {
    "dir": "📁",
    "file": "📄",
    ".py": "🐍",
    ".js": "🟨",
    ".html": "🌐",
    ".css": "🎨",
    ".md": "📝",
    ".json": "🔣",
    ".xml": "🔖",
    ".tsx": "🟦",
    ".ts": "🟦",
    ".java": "☕",
    ".c": "🅲",
    # Images
    ".jpg": "🖼️",
    ".jpeg": "🖼️",
    ".png": "🖼️",
    ".gif": "🖼️",
    ".svg": "📊",
    # Data
    ".csv": "📊",
    ".xlsx": "📊",
    ".sql": "💾",
    # Documents
    ".pdf": "📕",
    ".docx": "📄",
    ".txt": "📄",
    # Archives
    ".zip": "🗜️",
    ".tar": "🗜️",
    ".gz": "🗜️",
    ".rar": "🗜️",
    # Executables and binaries
    ".exe": "🔨",
    ".bin": "🔨",
    # Scripts
    ".sh": "🐚",
    ".bat": "🦇",
    # Version control
    ".gitignore": "🚫",
    # Audio
    ".mp3": "🎵",
    ".wav": "🎵",
    # Others
    ".dockerfile": "🐳",
    "Dockerfile": "🐳",
    ".yml": "🔧",
    ".yaml": "🔧",
}

commit_emojis: Dict[str, str] = {
    "feat": "✨",
    "fix": "🐛",
    "docs": "📚",
    "style": "💄",
    "refactor": "♻️",
    "test": "🧪",
    "chore": "🔧",
}
