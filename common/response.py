"""统一接口返回格式工具。"""

from typing import Any

from core.constants import DEFAULT_ERROR_CODE, SUCCESS_CODE


def success_response(data: Any = None, message: str = "success") -> dict[str, Any]:
    """返回统一的成功响应结构。"""
    return {
        "code": SUCCESS_CODE,
        "message": message,
        "data": data,
    }


def error_response(
    message: str = "error",
    *,
    code: int = DEFAULT_ERROR_CODE,
    data: Any = None,
) -> dict[str, Any]:
    """返回统一的失败响应结构。"""
    return {
        "code": code,
        "message": message,
        "data": data,
    }
