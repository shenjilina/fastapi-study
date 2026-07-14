"""RAG 问答记录基础 CRUD 示例。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.rag.enums import ConversationRecordStatus
from api.rag.model import ConversationRecord


def create_conversation_record(
    db: Session,
    *,
    user_id: int,
    knowledge_base_id: int,
    question: str,
    answer: str,
    source_document_ids: str | None = None,
    status: ConversationRecordStatus = ConversationRecordStatus.GENERATED,
) -> ConversationRecord:
    """创建一条问答记录。"""
    conversation = ConversationRecord(
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        question=question,
        answer=answer,
        source_document_ids=source_document_ids,
        status=status,
    )
    db.add(conversation)
    db.flush()
    db.refresh(conversation)
    return conversation


def list_conversations_by_knowledge_base(
    db: Session,
    knowledge_base_id: int,
) -> list[ConversationRecord]:
    """查询某个知识库下的全部问答记录。"""
    statement = (
        select(ConversationRecord)
        .where(ConversationRecord.knowledge_base_id == knowledge_base_id)
        .order_by(ConversationRecord.id.asc())
    )
    return list(db.scalars(statement))
