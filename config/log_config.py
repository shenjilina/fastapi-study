"""Logging helpers used during application bootstrap."""

import logging
import logging.config
from pathlib import Path

from config.settings import Settings


def configure_logging(settings: Settings) -> None:
    """在应用启动时统一初始化控制台与文件日志。"""
    log_path = Path(settings.log_file)
    # 确保日志目录存在，避免文件处理器初始化失败。
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    # 统一日志格式，便于本地排查和线上追踪。
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                }
            },
            "handlers": {
                "console": {
                    # 控制台输出，方便开发阶段实时查看日志。
                    "class": "logging.StreamHandler",
                    "level": settings.log_level,
                    "formatter": "standard",
                },
                "file": {
                    # 滚动文件日志，控制单个日志文件体积。
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
    # 按模块名称获取 logger，便于区分日志来源。
    return logging.getLogger(name)
