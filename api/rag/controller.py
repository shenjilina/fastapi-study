"""RAG 问答模块控制器。

职责：仅处理路由接收、参数校验、统一响应、依赖注入，无任何业务、DB、RAG 逻辑。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from api.rag import service
from api.rag.schema import (
    ConversationCreateRequest,
    ConversationDeleteResponse,
    RAGQuestionRequest,
)
from common.response import success_response
from core.db import get_db

router = APIRouter(tags=["rag"])


@router.post("/rag/ask", status_code=status.HTTP_200_OK)
def ask_question(
    payload: RAGQuestionRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """RAG 问答接口：知识库隔离检索 -> 上下文拼接 -> LLM 生成 -> 持久化问答记录。"""
    answer = service.ask_question(db, payload)
    return success_response(
        answer.model_dump(mode="json"),
        message="问答完成",
    )


@router.get("/rag/health", status_code=status.HTTP_200_OK)
def rag_health_check() -> dict[str, object]:
    """RAG 链健康检查接口：返回检索器、LLM、链参数状态。"""
    health = service.get_rag_health()
    return success_response(health, message="RAG 链状态获取成功")


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


@router.get("/conversations/{conversation_id}", status_code=status.HTTP_200_OK)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """查询单条问答记录接口。"""
    conversation = service.get_conversation(db, conversation_id)
    return success_response(
        conversation.model_dump(mode="json"),
        message="问答记录详情获取成功",
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


@router.get("/users/{user_id}/conversations", status_code=status.HTTP_200_OK)
def list_conversations_by_user(
    user_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """查询用户全部问答记录接口。"""
    conversations = [
        item.model_dump(mode="json")
        for item in service.list_conversations_by_user(db, user_id)
    ]
    return success_response(conversations, message="用户问答记录列表获取成功")


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_200_OK)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """删除问答记录接口。"""
    result = service.delete_conversation(db, conversation_id)
    return success_response(
        ConversationDeleteResponse(
            conversation_id=result["conversation_id"],
            deleted=result["deleted"],
        ).model_dump(mode="json"),
        message="问答记录删除成功",
    )
