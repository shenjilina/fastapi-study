"""应用级中间件注册。"""

import time
from typing import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from config.log_config import get_logger
from config.settings import Settings
from core.constants import REQUEST_ID_HEADER

logger = get_logger(__name__)


def register_middlewares(app: FastAPI, settings: Settings) -> None:
    """注册 CORS 与请求日志中间件。"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )

    @app.middleware("http")
    async def log_request_time(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "[request_id=%s] %s %s completed in %.2f ms",
                request_id,
                request.method,
                request.url.path,
                duration_ms,
            )

        response.headers[REQUEST_ID_HEADER] = request_id
        return response
