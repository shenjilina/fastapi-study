"""用户模块基础 CRUD 示例。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.user.model import User


def create_user(
    db: Session,
    *,
    username: str,
    email: str,
    hashed_password: str,
    is_active: bool = True,
) -> User:
    """创建用户。"""
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """按主键查询用户。"""
    return db.get(User, user_id)


def get_user_by_username(db: Session, username: str) -> User | None:
    """按用户名查询用户。"""
    statement = select(User).where(User.username == username)
    return db.scalar(statement)


def list_users(db: Session) -> list[User]:
    """查询全部用户。"""
    statement = select(User).order_by(User.id.asc())
    return list(db.scalars(statement))
