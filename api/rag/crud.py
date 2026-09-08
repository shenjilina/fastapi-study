"""RAG 问答记录 CRUD：完整的增删改查能力。"""

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
    session_id: str | None = None,
    status: ConversationRecordStatus = ConversationRecordStatus.GENERATED,
) -> ConversationRecord:
    """创建一条问答记录，session_id 用于标记多轮会话归属。"""
    conversation = ConversationRecord(
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        question=question,
        answer=answer,
        source_document_ids=source_document_ids,
        session_id=session_id,
        status=status,
    )
    db.add(conversation)
    db.flush()
    db.refresh(conversation)
    return conversation


def get_conversation_by_id(db: Session, conversation_id: int) -> ConversationRecord | None:
    """按主键查询问答记录。"""
    return db.get(ConversationRecord, conversation_id)


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


def list_conversations_by_user(db: Session, user_id: int) -> list[ConversationRecord]:
    """查询某个用户的全部问答记录。"""
    statement = (
        select(ConversationRecord)
        .where(ConversationRecord.user_id == user_id)
        .order_by(ConversationRecord.id.asc())
    )
    return list(db.scalars(statement))


def list_recent_conversations_by_session(
    db: Session,
    *,
    user_id: int,
    knowledge_base_id: int,
    session_id: str,
    limit: int,
) -> list[ConversationRecord]:
    """查询某会话最近 limit 条成功问答记录，按时间正序返回。

    严格限定 user_id + knowledge_base_id + session_id 三元组，
    保证多轮记忆不跨用户、不跨知识库泄漏。
    仅取 GENERATED 记录：兜底失败回答无参考价值且会污染上下文。
    """
    statement = (
        select(ConversationRecord)
        .where(
            ConversationRecord.user_id == user_id,
            ConversationRecord.knowledge_base_id == knowledge_base_id,
            ConversationRecord.session_id == session_id,
            ConversationRecord.status == ConversationRecordStatus.GENERATED,
        )
        .order_by(ConversationRecord.id.desc())
        .limit(limit)
    )
    records = list(db.scalars(statement))
    records.reverse()
    return records


def delete_conversation(db: Session, conversation_id: int) -> bool:
    """按主键删除问答记录，返回是否删除成功。"""
    conversation = get_conversation_by_id(db, conversation_id)
    if conversation is None:
        return False
    db.delete(conversation)
    db.flush()
    return True
