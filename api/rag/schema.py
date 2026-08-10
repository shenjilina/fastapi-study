"""RAG 问答模块 Schema。"""

from datetime import datetime
from typing import Any

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
    session_id: str | None = Field(
        default=None,
        max_length=64,
        description="多轮会话标识，空表示单轮记录",
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
    session_id: str | None = None
    status: ConversationRecordStatus
    created_at: datetime


class RAGQuestionRequest(BaseModel):
    """RAG 问答请求体：用户提问 + 知识库 ID + 可选检索 TopK + 可选多轮会话标识。"""

    user_id: int = Field(gt=0, description="提问用户 ID")
    knowledge_base_id: int = Field(gt=0, description="知识库 ID")
    question: str = Field(min_length=1, max_length=2000, description="用户问题")
    top_k: int | None = Field(
        default=None,
        ge=1,
        le=20,
        description="检索结果数量，不传则使用默认配置",
    )
    conversation_session_id: str | None = Field(
        default=None,
        max_length=64,
        description="多轮会话标识，传入后携带该会话最近历史问答作为上下文",
    )

    @field_validator("question", mode="before")
    @classmethod
    def _strip_question(cls, value: str) -> str:
        text = strip_text(value)
        if not text:
            raise ValueError("问题不能为空")
        return text

    @field_validator("conversation_session_id", mode="before")
    @classmethod
    def _normalize_session_id(cls, value: str | None) -> str | None:
        text = strip_text(value)
        return text or None


class RAGSourceDocumentRead(BaseModel):
    """RAG 问答命中的源文档信息，用于前端溯源展示。"""

    page_content: str = Field(description="文档片段内容")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")
    score: float | None = Field(default=None, description="相似度分数（越小越相似）")


class RAGAnswerRead(BaseModel):
    """RAG 问答响应结构：包含回答、源文档、持久化的对话记录 ID。"""

    question: str
    answer: str
    source_documents: list[RAGSourceDocumentRead] = Field(default_factory=list)
    success: bool = Field(description="问答是否成功（True=正常生成，False=兜底回答）")
    error: str | None = Field(default=None, description="错误信息，成功时为 null")
    conversation_id: int | None = Field(
        default=None,
        description="持久化的对话记录 ID，保存失败时为 null",
    )


class ConversationDeleteResponse(BaseModel):
    """问答记录删除响应。"""

    conversation_id: int
    deleted: bool


class RAGHealthCheckRead(BaseModel):
    """RAG 链健康检查响应结构。"""

    chain: str = Field(description="链名称")
    max_context_tokens: int = Field(description="上下文最大 Token 数")
    default_top_k: int = Field(description="默认检索 TopK")
    retriever: dict[str, Any] = Field(default_factory=dict, description="检索器状态")
    llm: dict[str, Any] = Field(default_factory=dict, description="LLM 状态")
