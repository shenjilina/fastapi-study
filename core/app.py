"""FastAPI application factory."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from api import api_router
from common.middleware import register_middlewares
from common.response import success_response
from config.log_config import configure_logging, get_logger
from config.settings import get_settings
from core.constants import DEFAULT_HEALTH_PATH, DEFAULT_ROOT_MESSAGE
from core.db import test_database_connection
from core.exceptions import register_exception_handlers


def _register_common_components(app: FastAPI, settings) -> None:
    """统一注册中间件、异常处理器和 API 路由。"""
    register_middlewares(app, settings)
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    logger = get_logger(__name__)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        Path(settings.file_storage_dir).resolve().mkdir(parents=True, exist_ok=True)
        database_ready = False
        try:
            database_ready = test_database_connection()
        except Exception as exc:  # pragma: no cover - defensive logging on startup
            logger.warning("Database connectivity check failed during startup: %s", exc)

        if database_ready:
            try:
                from api.document.recovery import reset_interrupted_parses

                reset_interrupted_parses()
            except Exception as exc:  # pragma: no cover - startup recovery must not block service
                logger.warning("Interrupted parse recovery failed: %s", exc)

        logger.info("Application started. Database ready: %s", database_ready)
        yield
        logger.info("Application shutdown complete.")

    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    _register_common_components(app, settings)

    @app.get("/")
    async def root() -> dict[str, object]:
        """返回服务运行环境的基础信息。"""
        return success_response({"environment": settings.app_env}, DEFAULT_ROOT_MESSAGE)

    @app.get(DEFAULT_HEALTH_PATH)
    async def health_check() -> dict[str, object]:
        """检查应用进程和数据库连接的基础健康状态。"""
        return success_response(
            {
                "status": "ok",
                "database_url": settings.database_url,
            }
        )

    return app
