"""全局依赖与参数清洗工具。

JWT 鉴权全局依赖（必选/可选两种形态），
统一输出 User ORM 对象供 controller/service 使用。
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from core.db import get_db
from core.exceptions import AppException
from core.security import JWTTokenError, decode_access_token

if TYPE_CHECKING:
    from api.user.model import User

# auto_error=False：缺失 Authorization 头时返回 None 而非框架 403，
# 由本依赖抛出符合项目统一格式的 401 响应。
_bearer_scheme = HTTPBearer(auto_error=False)


def strip_text(value: str | None) -> str | None:
    """去掉字符串首尾空白字符。"""
    if value is None:
        return None
    return value.strip()


def ensure_text(value: str | None, *, field_name: str = "text") -> str:
    """确保字符串非空，常用于业务层参数防御。"""
    text = strip_text(value)
    if not text:
        raise ValueError(f"{field_name} cannot be empty")
    return text


def normalize_optional_text(value: str | None) -> str | None:
    """把空字符串归一化为 `None`，方便数据库层处理可空字段。"""
    text = strip_text(value)
    if text == "":
        return None
    return text


def sanitize_string_list(values: Iterable[str]) -> list[str]:
    """清洗字符串列表，移除空项并保留原始顺序。"""
    items: list[str] = []
    for value in values:
        text = strip_text(value)
        if text and text not in items:
            items.append(text)
    return items


def split_csv_text(value: str | None) -> list[str]:
    """把逗号分隔字符串转换为清洗后的列表。"""
    if value is None:
        return []
    return sanitize_string_list(value.split(","))


def _resolve_user_from_credentials(
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
) -> "User | None":
    """解析 Bearer 令牌并返回对应用户，凭证缺失时返回 None。

    凭证存在但无效（伪造/过期/用户不存在/已禁用）时抛出 401/403，
    避免静默降级为匿名访问。
    """
    if credentials is None:
        return None

    try:
        payload = decode_access_token(credentials.credentials)
    except JWTTokenError as exc:
        raise AppException(str(exc), status_code=401) from exc

    try:
        user_id = int(payload.get("sub", ""))
    except (TypeError, ValueError) as exc:
        raise AppException("无效的认证凭证", status_code=401) from exc

    # 延迟导入：避免 common 层在模块加载期静态依赖 api 业务层。
    from api.user import crud as user_crud

    user = user_crud.get_user_by_id(db, user_id)
    if user is None:
        raise AppException("令牌对应的用户不存在", status_code=401)
    if not user.is_active:
        raise AppException("用户已被禁用", status_code=403)
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> "User":
    """必选鉴权依赖：未携带有效令牌时拒绝访问（401）。"""
    user = _resolve_user_from_credentials(credentials, db)
    if user is None:
        raise AppException("未提供认证凭证，请先登录", status_code=401)
    return user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> "User | None":
    """可选鉴权依赖：携带令牌时严格校验，未携带时返回 None 兼容旧客户端。

    用于平滑过渡：接口既支持令牌态下的身份强制校验，
    也保留无令牌时由请求体 user_id 驱动的既有调用方式。
    """
    return _resolve_user_from_credentials(credentials, db)


def ensure_resource_owner(
    resource_user_id: int,
    current_user: "User | None",
    *,
    action: str = "操作",
) -> None:
    """令牌态下的水平越权拦截：请求体 user_id 必须与令牌身份一致。

    未携带令牌（current_user 为 None）时不做限制，由既有业务校验兜底。
    """
    if current_user is not None and resource_user_id != current_user.id:
        raise AppException(f"无权以其他用户身份{action}", status_code=403)


def ensure_owner(resource_owner_id: int, current_user: "User", *, resource: str = "资源") -> None:
    """确保已认证用户拥有目标资源。"""
    if resource_owner_id != current_user.id:
        raise AppException(f"无权访问其他用户的{resource}", status_code=403)


def token_payload_to_user_id(payload: dict[str, Any]) -> int | None:
    """从 JWT 载荷提取用户 ID，非法时返回 None（供非依赖场景复用）。"""
    try:
        return int(payload.get("sub", ""))
    except (TypeError, ValueError):
        return None
