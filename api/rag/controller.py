"""RAG 问答模块控制器。"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from api.rag import service
from api.rag.schema import ConversationCreateRequest
from common.response import success_response
from core.db import get_db

router = APIRouter(tags=["rag"])


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreateRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """创建问答记录接口。"""
    conversation = service.create_conversation(db, payload)
    return success_response(
        conversation.model_dump(mode="json"),
        message="问答记录创建成功",
    )


@router.get("/knowledge-bases/{knowledge_base_id}/conversations", status_code=status.HTTP_200_OK)
def list_conversations_by_knowledge_base(
    knowledge_base_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """查询知识库问答记录列表接口。"""
    conversations = [
        item.model_dump(mode="json")
        for item in service.list_conversations_by_knowledge_base(db, knowledge_base_id)
    ]
    return success_response(conversations, message="问答记录列表获取成功")
