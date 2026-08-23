from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.knowledge.enums import KnowledgeBaseStatus, KnowledgeBaseVisibility
from core.db import Base

if TYPE_CHECKING:
    from api.rag.model import ConversationRecord
    from api.user.model import User


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    visibility: Mapped[KnowledgeBaseVisibility] = mapped_column(
        Enum(KnowledgeBaseVisibility), default=KnowledgeBaseVisibility.PRIVATE, nullable=False
    )
    status: Mapped[KnowledgeBaseStatus] = mapped_column(
        Enum(KnowledgeBaseStatus), default=KnowledgeBaseStatus.ACTIVE, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_knowledge_bases_deleted_at", "deleted_at"),)

    owner: Mapped["User"] = relationship(back_populates="knowledge_bases")
    conversations: Mapped[list["ConversationRecord"]] = relationship(
        back_populates="knowledge_base", cascade="all, delete-orphan"
    )
