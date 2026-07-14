"""RAG 问答模块业务服务。"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.document import crud as document_crud
from api.rag import crud as rag_crud
from api.rag.schema import ConversationCreateRequest, ConversationRead
from api.user import crud as user_crud
from core.exceptions import AppException


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


def create_conversation(db: Session, payload: ConversationCreateRequest) -> ConversationRead:
    """创建问答记录。"""
    user = user_crud.get_user_by_id(db, payload.user_id)
    if user is None:
        raise AppException("用户不存在", status_code=404)

    knowledge_base = document_crud.get_knowledge_base_by_id(db, payload.knowledge_base_id)
    if knowledge_base is None:
        raise AppException("知识库不存在", status_code=404)

    if knowledge_base.owner_id != payload.user_id:
        raise AppException("该用户无权操作当前知识库", status_code=403)

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


def list_conversations_by_knowledge_base(db: Session, knowledge_base_id: int) -> list[ConversationRead]:
    """查询知识库下的问答记录。"""
    knowledge_base = document_crud.get_knowledge_base_by_id(db, knowledge_base_id)
    if knowledge_base is None:
        raise AppException("知识库不存在", status_code=404)

    conversations = rag_crud.list_conversations_by_knowledge_base(db, knowledge_base_id)
    return [build_conversation_read_model(item) for item in conversations]
