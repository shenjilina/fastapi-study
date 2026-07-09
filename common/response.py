"""Standard API response helpers."""

from typing import Any


def success_response(data: Any = None, message: str = "success") -> dict[str, Any]:
    return {"code": 0, "message": message, "data": data}


def error_response(
    message: str = "error",
    *,
    code: int = 1,
    data: Any = None,
) -> dict[str, Any]:
    return {"code": code, "message": message, "data": data}
