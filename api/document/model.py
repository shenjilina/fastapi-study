"""文档相关 ORM 模型。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.document.enums import DocumentParseStatus
from core.db import Base

if TYPE_CHECKING:
    from api.knowledge.model import KnowledgeBase


class Document(Base):
    """知识库中的文档元数据表。"""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(20))
    file_size: Mapped[int] = mapped_column(Integer)
    file_md5: Mapped[str] = mapped_column(String(32), index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parse_status: Mapped[DocumentParseStatus] = mapped_column(
        Enum(DocumentParseStatus),
        default=DocumentParseStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    knowledge_base: Mapped["KnowledgeBase"] = relationship(back_populates="documents")
