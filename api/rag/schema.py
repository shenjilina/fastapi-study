"""RAG 问答模块 Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from api.rag.enums import ConversationRecordStatus
from common.dependencies import strip_text


class ConversationCreateRequest(BaseModel):
    """创建问答记录请求体。"""

    user_id: int = Field(gt=0, description="用户 ID")
    knowledge_base_id: int = Field(gt=0, description="知识库 ID")
    question: str = Field(min_length=1, max_length=2000, description="用户问题")
    answer: str = Field(min_length=1, max_length=5000, description="回答内容")
    source_document_ids: list[int] = Field(
        default_factory=list,
        description="命中的文档 ID 列表",
    )
    status: ConversationRecordStatus = Field(
        default=ConversationRecordStatus.GENERATED,
        description="问答记录状态",
    )

    @field_validator("question", "answer", mode="before")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        text = strip_text(value)
        if not text:
            raise ValueError("字段不能为空")
        return text

    @field_validator("source_document_ids")
    @classmethod
    def _validate_document_ids(cls, value: list[int]) -> list[int]:
        normalized = []
        for item in value:
            if item <= 0:
                raise ValueError("source_document_ids 中的值必须大于 0")
            if item not in normalized:
                normalized.append(item)
        return normalized


class ConversationRead(BaseModel):
    """问答记录响应结构。"""

    id: int
    user_id: int
    knowledge_base_id: int
    question: str
    answer: str
    source_document_ids: list[int]
    status: ConversationRecordStatus
    created_at: datetime
