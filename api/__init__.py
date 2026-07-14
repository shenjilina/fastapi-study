"""API 路由聚合入口。"""

from fastapi import APIRouter

from api.document.controller import router as document_router
from api.rag.controller import router as rag_router
from api.user.controller import router as user_router

api_router = APIRouter()
api_router.include_router(user_router)
api_router.include_router(document_router)
api_router.include_router(rag_router)
