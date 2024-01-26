file_emoji_dict = {
    # Folders and general files
    "dir": "📁",
    "file": "📄",
    # Code and markup languages
    ".py": "🐍",  # Python files
    ".js": "🟨",  # JavaScript files
    ".html": "🌐",  # HTML files
    ".css": "🎨",  # CSS files
    ".md": "📝",  # Markdown files
    ".json": "🔣",  # JSON files
    ".xml": "🔖",  # XML files
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
    # Video
    ".mp4": "🎥",
    ".mov": "🎥",
    # Others
    ".dockerfile": "🐳",
    "Dockerfile": "🐳",
    ".yml": "🔧",
    ".yaml": "🔧",
    ".env": "🔒",
}

commands_with_tips = {
    "/emoji add": {
        "description": "This command allows you to **add new emojis to your server** for quick access. To use it, navigate to [Emoji.gg](<https://emoji.gg>) and browse through the collection of emojis. When you find an emoji you like, click on it to view its details. Look for the **'Emoji ID'** section which typically looks like a number or a short code, such as `5498_catJAM`. **Copy this ID** and use it with the `/emoji add` command by pasting it after the command like so: `/emoji add emoji_id:5498_catJAM`. This will add the emoji to your server.",
        "example": "```/emoji add emoji_id: 5498_catJAM ```",
        "image": "https://i.postimg.cc/MKrY4yqr/image.png",
    }
}
