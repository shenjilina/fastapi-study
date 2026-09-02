"""用户模块请求与响应 Schema。"""

from pydantic import ConfigDict, Field, field_validator, model_validator

from common.base_model import ApiBaseModel, ApiDateTime
from common.dependencies import strip_text


class UserCreateRequest(ApiBaseModel):
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


class UserDetailRequest(ApiBaseModel):
    """查询用户详情请求体（GET 转 POST，参数入请求体）。"""

    user_id: int = Field(gt=0, description="用户 ID")


class LoginRequest(ApiBaseModel):
    """登录请求体。"""

    username: str = Field(min_length=1, max_length=50, description="用户名")
    password: str = Field(min_length=1, max_length=128, description="用户密码")

    @field_validator("username", "password", mode="before")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        text = strip_text(value)
        if not text:
            raise ValueError("字段不能为空")
        return text


class ChangePasswordRequest(ApiBaseModel):
    """修改密码请求体。"""

    old_password: str = Field(min_length=1, max_length=128, description="当前密码")
    new_password: str = Field(min_length=8, max_length=128, description="新密码")

    @field_validator("old_password", "new_password", mode="before")
    @classmethod
    def _strip_password(cls, value: str) -> str:
        text = strip_text(value)
        if not text:
            raise ValueError("密码不能为空")
        return text

    @model_validator(mode="after")
    def _ensure_password_changed(self) -> "ChangePasswordRequest":
        if self.old_password == self.new_password:
            raise ValueError("新密码不能与当前密码相同")
        return self


class LoginResponse(ApiBaseModel):
    """登录成功响应结构，携带 JWT 访问令牌。"""

    user_id: int
    username: str
    email: str
    access_token: str = Field(description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(description="令牌有效期（秒）")


class UserRead(ApiBaseModel):
    """用户响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    is_active: bool
    created_at: ApiDateTime
    updated_at: ApiDateTime
