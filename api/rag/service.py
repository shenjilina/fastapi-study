"""RAG 问答模块业务服务。

职责：
- 组装 RAG 问答流程：校验 -> 调用 rag_chain 生成 -> 持久化问答记录。
- 提供对话记录的查询、删除能力。
- 所有底层能力均通过 core/langchain 封装调用，禁止在此实例化 LangChain 对象。
"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.knowledge import crud as knowledge_crud
from api.knowledge.enums import KnowledgeBaseStatus
from api.rag import crud as rag_crud
from api.rag.enums import ConversationRecordStatus
from api.rag.schema import (
    ConversationCreateRequest,
    ConversationRead,
    RAGAnswerRead,
    RAGQuestionRequest,
    RAGSourceDocumentRead,
)
from api.user import crud as user_crud
from config.log_config import get_logger
from core.exceptions import AppException
from core.langchain.rag_chain import RAGChainError, get_rag_chain

logger = get_logger(__name__)


def _parse_source_document_ids(raw_value: str | None) -> list[int]:
    """把数据库中的字符串形式文档 ID 转换为整型列表。"""
    if not raw_value:
        return []

    result = []
    for item in raw_value.split(","):
        text = item.strip()
        if text.isdigit():
            result.append(int(text))
    return result


def build_conversation_read_model(conversation) -> ConversationRead:
    """把 ORM 对象转换为响应模型。"""
    return ConversationRead(
        id=conversation.id,
        user_id=conversation.user_id,
        knowledge_base_id=conversation.knowledge_base_id,
        question=conversation.question,
        answer=conversation.answer,
        source_document_ids=_parse_source_document_ids(conversation.source_document_ids),
        status=conversation.status,
        created_at=conversation.created_at,
    )


def _validate_question_access(db: Session, payload: RAGQuestionRequest | ConversationCreateRequest):
    """校验用户存在性、知识库存在性、归属权以及知识库状态。

    Day8 新增：知识库处于 disabled 状态时拒绝问答，防止使用已下线的知识库。
    """
    user = user_crud.get_user_by_id(db, payload.user_id)
    if user is None:
        raise AppException("用户不存在", status_code=404)

    knowledge_base = knowledge_crud.get_knowledge_base_by_id(db, payload.knowledge_base_id)
    if knowledge_base is None:
        raise AppException("知识库不存在", status_code=404)

    if knowledge_base.owner_id != payload.user_id:
        raise AppException("该用户无权操作当前知识库", status_code=403)

    if knowledge_base.status == KnowledgeBaseStatus.DISABLED:
        raise AppException("知识库已禁用，无法进行问答", status_code=403)

    return knowledge_base


def _extract_document_ids(source_documents: list) -> list[int]:
    """从 RAG 源文档的 metadata 中提取去重后的 document_id 列表。"""
    document_ids: list[int] = []
    for doc in source_documents:
        metadata = getattr(doc, "metadata", {}) or {}
        raw_id = metadata.get("document_id")
        if raw_id is None:
            continue
        try:
            doc_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if doc_id > 0 and doc_id not in document_ids:
            document_ids.append(doc_id)
    return document_ids


def ask_question(db: Session, payload: RAGQuestionRequest) -> RAGAnswerRead:
    """执行 RAG 问答：校验 -> 调用 rag_chain 生成 -> 持久化问答记录。

    即使 LLM 兜底返回失败回答，也会以 FAILED 状态落库，保证可追溯。
    """
    _validate_question_access(db, payload)

    # 调用底层 RAG 链生成回答（内部已含检索异常、LLM 异常兜底）。
    rag_chain = get_rag_chain()
    try:
        rag_answer = rag_chain.ask(
            payload.question,
            knowledge_base_id=payload.knowledge_base_id,
            top_k=payload.top_k,
        )
    except RAGChainError as exc:
        # 输入参数级错误，直接返回 400。
        raise AppException(str(exc), status_code=400) from exc

    # 从源文档元数据中提取 document_id，用于持久化溯源。
    source_document_ids = _extract_document_ids(rag_answer.source_documents)
    source_document_ids_str = ",".join(str(item) for item in source_document_ids) or None

    # 根据问答结果决定落库状态：成功 -> GENERATED，兜底 -> FAILED。
    record_status = (
        ConversationRecordStatus.GENERATED
        if rag_answer.success
        else ConversationRecordStatus.FAILED
    )

    conversation_id: int | None = None
    try:
        conversation = rag_crud.create_conversation_record(
            db,
            user_id=payload.user_id,
            knowledge_base_id=payload.knowledge_base_id,
            question=rag_answer.question,
            answer=rag_answer.answer,
            source_document_ids=source_document_ids_str,
            status=record_status,
        )
        db.commit()
        conversation_id = conversation.id
    except SQLAlchemyError as exc:
        # 落库失败不影响问答结果返回，仅记录错误并回滚。
        db.rollback()
        logger.exception("Failed to persist conversation record: %s", exc)

    return RAGAnswerRead(
        question=rag_answer.question,
        answer=rag_answer.answer,
        source_documents=[
            RAGSourceDocumentRead(
                page_content=doc.page_content,
                metadata=doc.metadata,
                score=doc.score,
            )
            for doc in rag_answer.source_documents
        ],
        success=rag_answer.success,
        error=rag_answer.error,
        conversation_id=conversation_id,
    )


def create_conversation(db: Session, payload: ConversationCreateRequest) -> ConversationRead:
    """创建问答记录。"""
    _validate_question_access(db, payload)

    source_document_ids = ",".join(str(item) for item in payload.source_document_ids)

    try:
        conversation = rag_crud.create_conversation_record(
            db,
            user_id=payload.user_id,
            knowledge_base_id=payload.knowledge_base_id,
            question=payload.question,
            answer=payload.answer,
            source_document_ids=source_document_ids or None,
            status=payload.status,
        )
        db.commit()
        return build_conversation_read_model(conversation)
    except SQLAlchemyError as exc:
        db.rollback()
        raise AppException("创建问答记录失败，请稍后重试", status_code=500) from exc


def get_conversation(db: Session, conversation_id: int) -> ConversationRead:
    """查询单条问答记录。"""
    conversation = rag_crud.get_conversation_by_id(db, conversation_id)
    if conversation is None:
        raise AppException("问答记录不存在", status_code=404)
    return build_conversation_read_model(conversation)


def list_conversations_by_knowledge_base(db: Session, knowledge_base_id: int) -> list[ConversationRead]:
    """查询知识库下的问答记录。"""
    knowledge_base = knowledge_crud.get_knowledge_base_by_id(db, knowledge_base_id)
    if knowledge_base is None:
        raise AppException("知识库不存在", status_code=404)

    conversations = rag_crud.list_conversations_by_knowledge_base(db, knowledge_base_id)
    return [build_conversation_read_model(item) for item in conversations]


def list_conversations_by_user(db: Session, user_id: int) -> list[ConversationRead]:
    """查询用户的全部问答记录。"""
    user = user_crud.get_user_by_id(db, user_id)
    if user is None:
        raise AppException("用户不存在", status_code=404)

    conversations = rag_crud.list_conversations_by_user(db, user_id)
    return [build_conversation_read_model(item) for item in conversations]


def delete_conversation(db: Session, conversation_id: int) -> dict:
    """删除问答记录。"""
    try:
        deleted = rag_crud.delete_conversation(db, conversation_id)
        if not deleted:
            raise AppException("问答记录不存在", status_code=404)
        db.commit()
    except AppException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise AppException("删除问答记录失败，请稍后重试", status_code=500) from exc

    return {"conversation_id": conversation_id, "deleted": True}


def get_rag_health() -> dict:
    """获取 RAG 链运行状态，用于运维监控。"""
    rag_chain = get_rag_chain()
    return rag_chain.health_check()
