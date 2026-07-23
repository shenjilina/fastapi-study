"""RAG 问答模块控制器。

职责：仅处理路由接收、参数校验、统一响应、依赖注入，无任何业务、DB、RAG 逻辑。

路由规范：
- 对话记录资源统一使用 prefix="/conversations"，收敛到单一命名空间，
  不侵入 /knowledge-bases/ 或 /users/ 等其他模块的路径。
- 列表查询通过查询参数过滤（knowledge_base_id / user_id），替代跨模块嵌套路由。
- RAG 健康检查为运维端点，独立于业务资源，使用单独路由注册。
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from api.rag import service
from api.rag.schema import (
    ConversationCreateRequest,
    ConversationDeleteResponse,
    RAGQuestionRequest,
)
from common.response import success_response
from core.db import get_db
from core.exceptions import AppException

# 对话记录资源路由：统一使用 /conversations 前缀
router = APIRouter(prefix="/conversations", tags=["rag"])

# RAG 运维路由：健康检查等非业务资源端点，不归属对话资源
health_router = APIRouter(tags=["rag"])


@router.post("/ask", status_code=status.HTTP_200_OK)
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


@health_router.get("/rag/health", status_code=status.HTTP_200_OK)
def rag_health_check() -> dict[str, object]:
    """RAG 链健康检查接口：返回检索器、LLM、链参数状态。"""
    health = service.get_rag_health()
    return success_response(health, message="RAG 链状态获取成功")


@router.post("", status_code=status.HTTP_201_CREATED)
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


@router.get("", status_code=status.HTTP_200_OK)
def list_conversations(
    knowledge_base_id: int | None = Query(default=None, gt=0, description="按知识库 ID 过滤"),
    user_id: int | None = Query(default=None, gt=0, description="按用户 ID 过滤"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """查询对话记录列表，支持按知识库或用户过滤。

    至少提供 knowledge_base_id 或 user_id 中的一个过滤条件。
    """
    if knowledge_base_id is not None:
        conversations = service.list_conversations_by_knowledge_base(db, knowledge_base_id)
    elif user_id is not None:
        conversations = service.list_conversations_by_user(db, user_id)
    else:
        raise AppException("请提供 knowledge_base_id 或 user_id 过滤条件", status_code=400)

    conversations_data = [item.model_dump(mode="json") for item in conversations]
    return success_response(conversations_data, message="问答记录列表获取成功")


@router.get("/{conversation_id}", status_code=status.HTTP_200_OK)
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


@router.delete("/{conversation_id}", status_code=status.HTTP_200_OK)
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
