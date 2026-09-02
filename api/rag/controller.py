"""RAG 问答模块控制器。

职责：仅处理路由接收、参数校验、统一响应、依赖注入，无任何业务、DB、RAG 逻辑。

路由规范：
- 对话记录资源统一使用 prefix="/conversations"，收敛到单一命名空间，
  不侵入 /knowledge-bases/ 或 /users/ 等其他模块的路径。
- 列表查询通过查询参数过滤（knowledge_base_id / user_id），替代跨模块嵌套路由。
- RAG 健康检查为运维端点，独立于业务资源，使用单独路由注册。
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.rag import service
from api.rag.schema import (
    ConversationCreateRequest,
    ConversationDeleteResponse,
    ConversationDetailRequest,
    ConversationListRequest,
    ConversationRead,
    RAGAnswerRead,
    RAGHealthCheckRead,
    RAGQuestionRequest,
)
from common.dependencies import get_current_user
from common.response import ApiResponse, success_response
from core.db import get_db

# 对话记录资源路由：统一使用 /conversations 前缀
router = APIRouter(prefix="/conversations", tags=["rag"])

# RAG 运维路由：健康检查等非业务资源端点，不归属对话资源
health_router = APIRouter(tags=["rag"])


@router.post("/ask", status_code=status.HTTP_200_OK, response_model=ApiResponse[RAGAnswerRead])
def ask_question(
    payload: RAGQuestionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """RAG 问答接口：知识库隔离检索 -> 上下文拼接 -> LLM 生成 -> 持久化问答记录。

    Day12：必选 JWT 鉴权，强制校验提问身份与会话记忆隔离。
    """
    answer = service.ask_question(db, payload, current_user)
    return success_response(
        answer.model_dump(mode="json"),
        message="问答完成",
    )


# SSE 流式例外：不声明 response_model。SSE 逐块推送 text/event-stream，
# 响应体非单一 JSON 对象，无法被 response_model 校验/序列化；若声明会破坏流式输出。
@router.post("/ask/stream", status_code=status.HTTP_200_OK)
def ask_question_stream(
    payload: RAGQuestionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> StreamingResponse:
    """流式 RAG 问答接口（SSE 打字机效果）。

    事件序列：sources -> chunk* -> (error?) -> done（携带 conversation_id）。
    校验失败在流开始前同步抛出，由全局异常处理器输出统一 JSON。
    """
    event_stream = service.ask_question_stream(db, payload, current_user)
    return StreamingResponse(
        event_stream,
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # 禁用 Nginx 等反向代理的响应缓冲，保证逐块实时推送。
            "X-Accel-Buffering": "no",
        },
    )


@health_router.get(
    "/rag/health",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[RAGHealthCheckRead],
)
def rag_health_check() -> dict[str, object]:
    """RAG 链健康检查接口：返回检索器、LLM、链参数状态。"""
    health = service.get_rag_health()
    return success_response(health, message="RAG 链状态获取成功")


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[ConversationRead])
def create_conversation(
    payload: ConversationCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """创建问答记录接口。"""
    conversation = service.create_conversation(db, payload, current_user)
    return success_response(
        conversation.model_dump(mode="json"),
        message="问答记录创建成功",
    )


@router.post(
    "/list", status_code=status.HTTP_200_OK, response_model=ApiResponse[list[ConversationRead]]
)
def list_conversations(
    payload: ConversationListRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """查询对话记录列表。

    至少提供 knowledge_base_id 或 user_id 中的一个过滤条件（schema 层已校验）。
    """
    if payload.knowledge_base_id is not None:
        conversations = service.list_conversations_by_knowledge_base(
            db, payload.knowledge_base_id, current_user
        )
    else:
        conversations = service.list_conversations_by_user(db, payload.user_id, current_user)

    conversations_data = [item.model_dump(mode="json") for item in conversations]
    return success_response(conversations_data, message="问答记录列表获取成功")


@router.post(
    "/get_conversation",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ConversationRead],
)
def get_conversation(
    payload: ConversationDetailRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """查询单条问答记录接口。"""
    conversation = service.get_conversation(db, payload.conversation_id, current_user)
    return success_response(
        conversation.model_dump(mode="json"),
        message="问答记录详情获取成功",
    )


@router.delete(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ConversationDeleteResponse],
)
def delete_conversation(
    payload: ConversationDetailRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """删除问答记录接口。"""
    result = service.delete_conversation(db, payload.conversation_id, current_user)
    return success_response(
        ConversationDeleteResponse(
            conversation_id=result["conversation_id"],
            deleted=result["deleted"],
        ).model_dump(mode="json"),
        message="问答记录删除成功",
    )
