import logging
import os

from logging.config import dictConfig


class CustomFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, style="%"):
        super().__init__(fmt, datefmt, style)
        self.fmt = fmt
        self.err_fmt = "📅 %(asctime)s - 🤖 %(name)s - ⚙️ %(levelname)s - 📁 %(pathname)s - 📝 %(lineno)d - %(message)s"

    def format(self, record):
        if record.levelno >= logging.ERROR:
            record.pathname = os.path.relpath(record.pathname)
            format_orig = self._style._fmt
            self._style._fmt = self.err_fmt
            result = super().format(record)
            self._style._fmt = format_orig
            return result
        return super().format(record)


def configure_logger():
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "()": CustomFormatter,
                    "format": "📅 %(asctime)s - 🤖 %(name)s - ⚙️ %(levelname)s - %(message)s",
                    "datefmt": "%Y-%m-%d %I:%M %p",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "DEBUG",
                    "formatter": "standard",
                },
                "file": {
                    "class": "logging.FileHandler",
                    "filename": "bot.log",
                    "level": "DEBUG",
                    "formatter": "standard",
                    "encoding": "utf-8",
                },
            },
            "loggers": {
                "uni_bot": {
                    "handlers": ["console", "file"],
                    "level": "DEBUG",
                    "propagate": True,
                },
            },
        }
    )

    return logging.getLogger("uni_bot")
