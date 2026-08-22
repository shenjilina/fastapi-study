"""API 路由聚合入口。

鉴权策略：除登录与注册外，所有业务接口必须携带有效 JWT 令牌，
通过受保护路由器的全局依赖 get_current_user 统一强制校验。
"""

from fastapi import APIRouter, Depends

from api.document.controller import router as document_router
from api.files.controller import router as files_router
from api.knowledge.controller import router as knowledge_router
from api.rag.controller import health_router as rag_health_router
from api.rag.controller import router as rag_router
from api.user.controller import auth_router as user_auth_router
from api.user.controller import router as user_router
from common.dependencies import get_current_user

api_router = APIRouter()
# 免鉴权白名单：登录签发令牌，注册时用户尚无令牌，两者必须匿名可访问。
api_router.include_router(user_auth_router)
api_router.include_router(user_router, dependencies=[Depends(get_current_user)])

# 受保护业务路由：全局依赖强制校验令牌，缺失/无效统一返回 401/403。
protected_router = APIRouter(dependencies=[Depends(get_current_user)])
protected_router.include_router(knowledge_router)
protected_router.include_router(document_router)
protected_router.include_router(files_router)
protected_router.include_router(rag_router)
protected_router.include_router(rag_health_router)
api_router.include_router(protected_router)
