from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.document.enums import DocumentParseStatus
from core.db import Base

if TYPE_CHECKING:
    from api.chunk.model import Chunk
    from api.files.model import FileRecord


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(
        ForeignKey("files.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parse_status: Mapped[DocumentParseStatus] = mapped_column(
        Enum(DocumentParseStatus), default=DocumentParseStatus.PENDING, nullable=False
    )
    error_msg: Mapped[str | None] = mapped_column(Text(), nullable=True)
    vector_cleaned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        Index(
            "uq_documents_active_file_id",
            "file_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_documents_parse_status", "parse_status"),
        Index("ix_documents_deleted_at", "deleted_at"),
    )

    file: Mapped["FileRecord"] = relationship()
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
