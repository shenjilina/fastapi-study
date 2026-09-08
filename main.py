"""Project runtime entry used by `uv run main.py`."""

import uvicorn

from config.settings import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "init_app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
        factory=False,
    )


if __name__ == "__main__":
    main()
