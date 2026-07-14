"""用户模块业务服务。"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.user import crud
from api.user.schema import UserCreateRequest
from core.exceptions import AppException
from core.security import hash_password


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


def get_user_detail(db: Session, user_id: int):
    """查询用户详情。"""
    user = crud.get_user_by_id(db, user_id)
    if user is None:
        raise AppException("用户不存在", status_code=404)
    return user


def list_users(db: Session):
    """查询全部用户。"""
    return crud.list_users(db)
