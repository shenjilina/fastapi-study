"""Logging helpers used during application bootstrap."""

import logging
import logging.config
from pathlib import Path

from config.settings import Settings


def configure_logging(settings: Settings) -> None:
    """Configure console and file logging once at startup."""
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": settings.log_level,
                    "formatter": "standard",
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": settings.log_level,
                    "formatter": "standard",
                    "filename": str(log_path),
                    "maxBytes": 1_048_576,
                    "backupCount": 3,
                    "encoding": "utf-8",
                },
            },
            "root": {
                "handlers": ["console", "file"],
                "level": settings.log_level,
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
