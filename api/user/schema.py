"""用户模块请求与响应 Schema。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from common.dependencies import strip_text


class UserCreateRequest(BaseModel):
    """创建用户请求体。"""

    username: str = Field(min_length=3, max_length=50, description="用户名，3 到 50 个字符")
    email: str = Field(max_length=120, description="用户邮箱")
    password: str = Field(min_length=8, max_length=128, description="用户明文密码")
    is_active: bool = Field(default=True, description="是否启用用户")

    @field_validator("username", "email", "password", mode="before")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        text = strip_text(value)
        if not text:
            raise ValueError("字段不能为空")
        return text

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str) -> str:
        if not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError("用户名仅支持字母、数字、下划线和中划线")
        return value

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        normalized = value.lower()
        if "@" not in normalized or "." not in normalized.split("@")[-1]:
            raise ValueError("邮箱格式不正确")
        return normalized


class UserRead(BaseModel):
    """用户响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
