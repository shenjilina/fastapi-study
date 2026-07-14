"""全局异常类型与注册逻辑。"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from common.response import error_response
from core.constants import (
    DEFAULT_ERROR_CODE,
    INTERNAL_ERROR_CODE,
    REQUEST_ID_HEADER,
    VALIDATION_ERROR_CODE,
)

logger = logging.getLogger(__name__)


class AppException(Exception):
    """项目统一业务异常。"""

    def __init__(
        self,
        message: str,
        *,
        code: int = DEFAULT_ERROR_CODE,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        data: object | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.data = data
        super().__init__(message)


def _format_validation_errors(exc: RequestValidationError) -> list[dict[str, object]]:
    """把 FastAPI 的校验错误转换成更易读的统一结构。"""
    formatted_errors: list[dict[str, object]] = []
    for item in exc.errors():
        formatted_errors.append(
            {
                "field": ".".join(str(part) for part in item.get("loc", [])),
                "message": item.get("msg", ""),
                "type": item.get("type", ""),
            }
        )
    return formatted_errors


def register_exception_handlers(app: FastAPI) -> None:
    """注册应用级全局异常处理器。"""

    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        payload = error_response(
            exc.message,
            code=exc.code,
            data={"detail": exc.data, "request_id": request_id},
        )
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        payload = error_response(
            "请求参数校验失败",
            code=VALIDATION_ERROR_CODE,
            data={
                "errors": _format_validation_errors(exc),
                "request_id": request_id,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=payload,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.exception("Unhandled exception [request_id=%s]: %s", request_id, exc)
        payload = error_response(
            "服务器内部错误",
            code=INTERNAL_ERROR_CODE,
            data={"request_id": request_id},
        )
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=payload,
        )
        if request_id:
            response.headers[REQUEST_ID_HEADER] = request_id
        return response
