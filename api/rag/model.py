"""RAG 问答记录 ORM 模型。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.rag.enums import ConversationRecordStatus
from core.db import Base

if TYPE_CHECKING:
    from api.knowledge.model import KnowledgeBase
    from api.user.model import User


class ConversationRecord(Base):
    """问答记录表。"""

    __tablename__ = "conversation_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
    )
    question: Mapped[str] = mapped_column(Text())
    answer: Mapped[str] = mapped_column(Text())
    source_document_ids: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 多轮会话标识（Day12）：同一 session_id 的连续问答共享对话记忆，空表示单轮。
    session_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    status: Mapped[ConversationRecordStatus] = mapped_column(
        Enum(ConversationRecordStatus),
        default=ConversationRecordStatus.GENERATED,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="conversations")
    knowledge_base: Mapped["KnowledgeBase"] = relationship(back_populates="conversations")
