"""知识库模块控制器。

职责：仅处理路由接收、参数校验、统一响应、依赖注入，无任何业务、DB、RAG 逻辑。
路由规范：统一使用 prefix="/knowledge-bases"，与 user 模块 prefix="/users" 风格一致。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from api.knowledge import service
from api.knowledge.schema import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseDetailRequest,
    KnowledgeBaseListRequest,
    KnowledgeBaseRead,
)
from common.dependencies import get_current_user
from common.response import ApiResponse, success_response
from core.db import get_db

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[KnowledgeBaseRead])
def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """创建知识库接口。"""
    knowledge_base = service.create_knowledge_base(db, payload, current_user)
    return success_response(
        knowledge_base.model_dump(mode="json"),
        message="知识库创建成功",
    )


@router.post(
    "/list", status_code=status.HTTP_200_OK, response_model=ApiResponse[list[KnowledgeBaseRead]]
)
def list_knowledge_bases(
    payload: KnowledgeBaseListRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """按用户查询知识库列表接口。"""
    knowledge_bases = [
        item.model_dump(mode="json")
        for item in service.list_knowledge_bases(db, payload.owner_id, current_user)
    ]
    return success_response(knowledge_bases, message="知识库列表获取成功")


@router.post(
    "/detail", status_code=status.HTTP_200_OK, response_model=ApiResponse[KnowledgeBaseRead]
)
def get_knowledge_base_detail(
    payload: KnowledgeBaseDetailRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """查询知识库详情接口。"""
    knowledge_base = service.get_knowledge_base_detail(db, payload.knowledge_base_id, current_user)
    return success_response(
        knowledge_base.model_dump(mode="json"),
        message="知识库详情获取成功",
    )
