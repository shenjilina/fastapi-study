"""Application logging configuration."""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path

from config.settings import Settings

_CONFIGURED_LOGGER = "fastapi-study.logging"


def configure_logging(settings: Settings) -> None:
    """Configure console and rotating file logging exactly once per target file."""
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(_CONFIGURED_LOGGER)
    marker = f"{log_path.resolve()}:{settings.log_level}"
    if getattr(logger, "_fastapi_study_marker", None) == marker:
        return

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
    logger._fastapi_study_marker = marker  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
