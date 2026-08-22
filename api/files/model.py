from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.files.enums import FileStatus
from core.db import Base

if TYPE_CHECKING:
    from api.document.model import Document
    from api.knowledge.model import KnowledgeBase
    from api.user.model import User


class FileRecord(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE")
    )
    filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    file_md5: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[FileStatus] = mapped_column(
        Enum(FileStatus), default=FileStatus.UPLOADING, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_files_knowledge_base_id", "knowledge_base_id"),
        Index("ix_files_owner_id", "owner_id"),
    )

    owner: Mapped["User"] = relationship()
    knowledge_base: Mapped["KnowledgeBase"] = relationship()
    document: Mapped["Document | None"] = relationship(back_populates="file", uselist=False)
