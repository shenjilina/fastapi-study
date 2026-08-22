"""用户模块控制器。

Day12：登录接口签发 JWT；新增 /users/me 鉴权端点（必选令牌）。
路由顺序注意：/me 必须先于 /{user_id} 注册，避免路径被整型参数路由拦截。
鉴权策略：auth_router 为免鉴权白名单（登录 + 注册），注册接口路径保持 /users 不变。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from api.user import service
from api.user.schema import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    UserCreateRequest,
    UserDetailRequest,
    UserRead,
)
from common.dependencies import ensure_owner, get_current_user
from common.response import ApiResponse, success_response
from core.db import get_db

router = APIRouter(prefix="/users", tags=["users"])
auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post(
    "/login", status_code=status.HTTP_200_OK, response_model=ApiResponse[LoginResponse]
)
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


@auth_router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[None],
)
def logout(current_user=Depends(get_current_user)) -> dict[str, object]:
    """退出登录确认接口；客户端收到成功响应后应删除本地 JWT。"""
    return success_response(None, message="退出登录成功")


@auth_router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[None],
)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """修改当前登录用户密码。"""
    service.change_password(db, current_user, payload)
    return success_response(None, message="密码修改成功")


@auth_router.post(
    "/register", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[UserRead]
)
@auth_router.post(
    "/create_user", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[UserRead]
)
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """创建用户（注册）接口：注册时用户尚无令牌，需匿名可访问。"""
    user = service.create_user(db, payload)
    return success_response(
        UserRead.model_validate(user).model_dump(mode="json"),
        message="用户创建成功",
    )


@router.get("/list", status_code=status.HTTP_200_OK, response_model=ApiResponse[list[UserRead]])
def list_users(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """查询用户列表接口。"""
    users = [UserRead.model_validate(current_user).model_dump(mode="json")]
    return success_response(users, message="用户列表获取成功")


@router.get("/info", status_code=status.HTTP_200_OK, response_model=ApiResponse[UserRead])
def get_current_user_profile(
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """查询当前登录用户信息：必选 JWT 鉴权，令牌无效/缺失返回 401。"""
    return success_response(
        UserRead.model_validate(current_user).model_dump(mode="json"),
        message="当前用户信息获取成功",
    )


@router.post("/detail", status_code=status.HTTP_200_OK, response_model=ApiResponse[UserRead])
def get_user_detail(
    payload: UserDetailRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """查询用户详情接口。"""
    user = service.get_user_detail(db, payload.user_id)
    ensure_owner(user.id, current_user, resource="用户")
    return success_response(
        UserRead.model_validate(user).model_dump(mode="json"),
        message="用户详情获取成功",
    )
