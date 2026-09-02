"""用户模块业务服务。"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.user import crud
from api.user.schema import ChangePasswordRequest, LoginRequest, LoginResponse, UserCreateRequest
from core.constants import ACCOUNT_DISABLED_CODE, AUTHENTICATION_ERROR_CODE
from core.exceptions import AppException
from core.security import create_access_token, get_token_ttl_seconds, hash_password, verify_password


def create_user(db: Session, payload: UserCreateRequest):
    """创建用户，并在 Service 层统一控制事务。"""
    if crud.get_user_by_username(db, payload.username) is not None:
        raise AppException("用户名已存在", status_code=409)

    if crud.get_user_by_email(db, payload.email) is not None:
        raise AppException("邮箱已存在", status_code=409)

    try:
        user = crud.create_user(
            db,
            username=payload.username,
            email=payload.email,
            hashed_password=hash_password(payload.password),
            is_active=payload.is_active,
        )
        db.commit()
        return user
    except SQLAlchemyError as exc:
        db.rollback()
        raise AppException("创建用户失败，请稍后重试", status_code=500) from exc


def login(db: Session, payload: LoginRequest):
    """用户登录：校验用户名、密码及启用状态。

    用户名不存在与密码错误返回同一错误信息，避免账号枚举。
    """
    user = crud.get_user_by_username(db, payload.username)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise AppException(
            "用户名或密码错误",
            code=AUTHENTICATION_ERROR_CODE,
            status_code=401,
        )

    if not user.is_active:
        raise AppException(
            "用户已被禁用",
            code=ACCOUNT_DISABLED_CODE,
            status_code=401,
        )

    return user


def build_login_response(user) -> LoginResponse:
    """登录成功后签发 JWT 并组装统一响应。"""
    access_token = create_access_token(user_id=user.id, username=user.username)
    return LoginResponse(
        user_id=user.id,
        username=user.username,
        email=user.email,
        access_token=access_token,
        token_type="bearer",
        expires_in=get_token_ttl_seconds(),
    )


def change_password(db: Session, user, payload: ChangePasswordRequest) -> None:
    """校验当前密码并保存新密码。"""
    if not verify_password(payload.old_password, user.hashed_password):
        raise AppException(
            "当前密码错误",
            code=AUTHENTICATION_ERROR_CODE,
            status_code=401,
        )

    user.hashed_password = hash_password(payload.new_password)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise AppException("修改密码失败，请稍后重试", status_code=500) from exc


def get_user_detail(db: Session, user_id: int):
    """查询用户详情。"""
    user = crud.get_user_by_id(db, user_id)
    if user is None:
        raise AppException("用户不存在", status_code=404)
    return user


def list_users(db: Session):
    """查询全部用户。"""
    return crud.list_users(db)
