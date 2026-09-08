"""FastAPI application factory."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from api import api_router
from common.middleware import register_middlewares
from common.response import success_response
from config.log_config import configure_logging, get_logger
from config.settings import get_settings
from core.constants import DEFAULT_HEALTH_PATH, DEFAULT_ROOT_MESSAGE
from core.db import test_database_connection
from core.exceptions import register_exception_handlers


def _fix_upload_file_schemas(schema: dict[str, Any]) -> None:
    """修复 Swagger UI 文件上传控件不显示的问题。

    FastAPI 0.129.1 起 UploadFile 字段在 OpenAPI 3.1 中生成
    contentMediaType 而非 format: binary，而 Swagger UI 5.x
    仅根据 format: binary 渲染文件选择器，导致 /docs 页面
    只出现文本输入框。此处后处理转换为旧写法以恢复控件。
    """

    def convert(node: dict[str, Any]) -> None:
        if not isinstance(node, dict):
            return
        items = node.get("items")
        if isinstance(items, dict) and items.get("contentMediaType") == "application/octet-stream":
            del items["contentMediaType"]
            items["format"] = "binary"
        if node.get("contentMediaType") == "application/octet-stream":
            del node["contentMediaType"]
            node["format"] = "binary"

    for component in schema.get("components", {}).get("schemas", {}).values():
        for prop in component.get("properties", {}).values():
            convert(prop)


def _register_openapi_fix(app: FastAPI) -> None:
    """挂载自定义 openapi() 生成函数，在标准生成流程后应用文件字段修复。"""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            description=app.description,
            terms_of_service=app.terms_of_service,
            contact=app.contact,
            license_info=app.license_info,
            routes=app.routes,
            tags=app.openapi_tags,
            servers=app.servers,
        )
        _fix_upload_file_schemas(schema)
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]


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
    _register_openapi_fix(app)

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
