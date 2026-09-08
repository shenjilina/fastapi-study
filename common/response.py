"""统一接口返回格式工具。

包含两部分：
- success_response / error_response：端点运行时组装统一响应 dict；
- ApiResponse[T]：泛型响应包装模型，供各端点 response_model 声明使用，
  使 OpenAPI/Swagger 能完整描述 {code, message, data} 结构。

序列化约定：ApiResponse 继承 ApiBaseModel（alias_generator=to_camel），
FastAPI 路由的 response_model_by_alias 默认为 True，响应序列化自动按
别名输出，即嵌套 data 中的多词字段以 camelCase 下发（等价于对整棵响应
树执行 model_dump(by_alias=True)），无需在每个装饰器上重复声明。
"""

from typing import Any, Generic, TypeVar

from pydantic import Field

from common.base_model import ApiBaseModel
from core.constants import DEFAULT_ERROR_CODE, SUCCESS_CODE

T = TypeVar("T")


class ApiResponse(ApiBaseModel, Generic[T]):
    """统一响应包装模型：code + message + data。

    用法：response_model=ApiResponse[UserRead]、
    response_model=ApiResponse[list[DocumentRead]] 等，
    泛型参数描述 data 载荷的具体结构。
    """

    code: int = Field(default=SUCCESS_CODE, description="业务状态码，0 表示成功")
    message: str = Field(default="success", description="响应描述信息")
    data: T | None = Field(default=None, description="业务数据载荷")


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
