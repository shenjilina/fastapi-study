"""用户模块控制器。"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from api.user import service
from api.user.schema import UserCreateRequest, UserRead
from common.response import success_response
from core.db import get_db

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """创建用户接口。"""
    user = service.create_user(db, payload)
    return success_response(
        UserRead.model_validate(user).model_dump(mode="json"),
        message="用户创建成功",
    )


@router.get("", status_code=status.HTTP_200_OK)
def list_users(db: Session = Depends(get_db)) -> dict[str, object]:
    """查询用户列表接口。"""
    users = [UserRead.model_validate(item).model_dump(mode="json") for item in service.list_users(db)]
    return success_response(users, message="用户列表获取成功")


@router.get("/{user_id}", status_code=status.HTTP_200_OK)
def get_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """查询用户详情接口。"""
    user = service.get_user_detail(db, user_id)
    return success_response(
        UserRead.model_validate(user).model_dump(mode="json"),
        message="用户详情获取成功",
    )
