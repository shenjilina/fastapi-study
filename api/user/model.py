"""用户模块 ORM 模型。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base

if TYPE_CHECKING:
    from api.knowledge.model import KnowledgeBase
    from api.rag.model import ConversationRecord


class User(Base):
    """系统用户表。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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

    # 一个用户可以拥有多个知识库和多条问答记录。
    knowledge_bases: Mapped[list["KnowledgeBase"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    conversations: Mapped[list["ConversationRecord"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
