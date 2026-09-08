"""Security helpers: password hashing and JWT token issuing/verification."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from config.settings import get_settings


class JWTTokenError(RuntimeError):
    """JWT 令牌无效、过期或解析失败。"""


def hash_password(password: str, *, iterations: int = 100_000) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"{iterations}${salt}${digest.hex()}"


def verify_password(password: str, hashed_password: str) -> bool:
    iterations_text, salt, expected = hashed_password.split("$", maxsplit=2)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations_text),
    )
    return hmac.compare_digest(digest.hex(), expected)


def create_access_token(
    *,
    user_id: int,
    username: str,
    expires_minutes: int | None = None,
) -> str:
    """签发 JWT 访问令牌，携带用户身份与过期时间。

    Args:
        user_id: 用户主键。
        username: 用户名，仅用于载荷可读性，鉴权以 user_id 为准。
        expires_minutes: 过期时长（分钟），缺省读配置。
    """
    settings = get_settings()
    expire_minutes = expires_minutes if expires_minutes is not None else settings.jwt_expire_minutes
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """解析并验证 JWT 令牌，失败时统一抛出 JWTTokenError。

    Returns:
        令牌载荷字典，含 sub（用户 ID 字符串）与 username。
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise JWTTokenError("登录状态已过期，请重新登录") from exc
    except jwt.InvalidTokenError as exc:
        raise JWTTokenError("无效的认证凭证") from exc

    if not payload.get("sub"):
        raise JWTTokenError("无效的认证凭证")
    return payload


def get_token_ttl_seconds() -> int:
    """返回当前配置的令牌有效期（秒），供响应体告知前端。"""
    return get_settings().jwt_expire_minutes * 60
