"""用户模块控制器。

Day12：登录接口签发 JWT；新增 /users/me 鉴权端点（必选令牌）。
路由顺序注意：/me 必须先于 /{user_id} 注册，避免路径被整型参数路由拦截。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from api.user import service
from api.user.schema import LoginRequest, UserCreateRequest, UserRead
from common.dependencies import get_current_user
from common.response import success_response
from core.db import get_db

router = APIRouter(prefix="/users", tags=["users"])
auth_router = APIRouter(tags=["auth"])


@auth_router.post("/login", status_code=status.HTTP_200_OK)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """用户登录接口：校验用户名与密码，成功后签发 JWT 访问令牌。"""
    user = service.login(db, payload)
    return success_response(
        service.build_login_response(user).model_dump(mode="json"),
        message="登录成功",
    )


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


@router.get("/me", status_code=status.HTTP_200_OK)
def get_current_user_profile(
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """查询当前登录用户信息：必选 JWT 鉴权，令牌无效/缺失返回 401。"""
    return success_response(
        UserRead.model_validate(current_user).model_dump(mode="json"),
        message="当前用户信息获取成功",
    )


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
