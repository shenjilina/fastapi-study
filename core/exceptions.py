"""全局异常类型与注册逻辑。"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from common.response import error_response
from core.constants import (
    DEFAULT_ERROR_CODE,
    INTERNAL_ERROR_CODE,
    REQUEST_ID_HEADER,
    VALIDATION_ERROR_CODE,
)

logger = logging.getLogger(__name__)


# 常见 HTTP 状态码对应的统一中文文案，未命中时使用通用文案。
_HTTP_STATUS_MESSAGES: dict[int, str] = {
    404: "请求的资源不存在",
    405: "请求方法不被允许",
    408: "请求超时",
    413: "请求体过大",
    415: "不支持的媒体类型",
}


def _build_error_json_response(
    *,
    status_code: int,
    message: str,
    code: int,
    request_id: str | None,
    data: object | None = None,
) -> JSONResponse:
    """构造统一格式的错误响应，并统一携带 request_id 响应头。"""
    payload = error_response(message, code=code, data=data)
    response = JSONResponse(status_code=status_code, content=payload)
    if request_id:
        response.headers[REQUEST_ID_HEADER] = request_id
    return response


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
        error_type = item.get("type", "")
        context = item.get("ctx", {}) or {}
        formatted_errors.append(
            {
                "field": ".".join(str(part) for part in item.get("loc", [])),
                "message": _translate_validation_message(error_type, item.get("msg", ""), context),
                "type": error_type,
            }
        )
    return formatted_errors


def _translate_validation_message(
    error_type: str,
    message: str,
    context: dict[str, object],
) -> str:
    """将 Pydantic 常见的英文校验提示转换为中文。"""
    if error_type == "missing":
        return "字段为必填项"
    if error_type in {"string_type", "str_type"}:
        return "请输入字符串"
    if error_type == "string_too_short":
        return f"长度不能少于 {context.get('min_length')} 个字符"
    if error_type == "string_too_long":
        return f"长度不能超过 {context.get('max_length')} 个字符"
    if error_type in {
        "int_type",
        "float_type",
        "number_type",
        "int_parsing",
        "float_parsing",
        "number_parsing",
    }:
        return "请输入有效的数字"
    if error_type == "bool_type":
        return "请输入布尔值"
    if error_type in {"greater_than", "greater_equal"}:
        operator = "大于" if error_type == "greater_than" else "大于或等于"
        return f"数值必须{operator} {context.get('gt', context.get('ge'))}"
    if error_type in {"less_than", "less_equal"}:
        operator = "小于" if error_type == "less_than" else "小于或等于"
        return f"数值必须{operator} {context.get('lt', context.get('le'))}"
    if error_type in {"list_type", "list_parsing"}:
        return "请输入列表"
    if error_type == "dict_type":
        return "请输入对象"
    return message


def register_exception_handlers(app: FastAPI) -> None:
    """注册应用级全局异常处理器。"""

    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return _build_error_json_response(
            status_code=exc.status_code,
            message=exc.message,
            code=exc.code,
            request_id=request_id,
            data={"detail": exc.data, "request_id": request_id},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """兜底框架层 HTTP 异常（如未知路由 404、方法不允许 405），对齐统一响应格式。"""
        request_id = getattr(request.state, "request_id", None)
        # 优先使用统一中文文案，未命中状态码映射时回退到框架原始 detail。
        message = _HTTP_STATUS_MESSAGES.get(exc.status_code) or (
            str(exc.detail) if exc.detail else "请求处理失败"
        )
        return _build_error_json_response(
            status_code=exc.status_code,
            message=message,
            code=DEFAULT_ERROR_CODE,
            request_id=request_id,
            data={"detail": exc.detail, "request_id": request_id},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return _build_error_json_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            message="请求参数校验失败",
            code=VALIDATION_ERROR_CODE,
            request_id=request_id,
            data={
                "errors": _format_validation_errors(exc),
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.exception("Unhandled exception [request_id=%s]: %s", request_id, exc)
        return _build_error_json_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="服务器内部错误",
            code=INTERNAL_ERROR_CODE,
            request_id=request_id,
            data={"request_id": request_id},
        )
