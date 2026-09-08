from pydantic import ConfigDict, Field, field_validator

from api.knowledge.enums import KnowledgeBaseStatus, KnowledgeBaseVisibility
from common.base_model import ApiBaseModel, ApiDateTime
from common.dependencies import normalize_optional_text, strip_text


class KnowledgeBaseCreateRequest(ApiBaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    visibility: KnowledgeBaseVisibility = KnowledgeBaseVisibility.PRIVATE

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = strip_text(value) or ""
        if not value:
            raise ValueError("知识库名称不能为空")
        return value

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class KnowledgeBaseUpdateRequest(KnowledgeBaseCreateRequest):
    name: str | None = Field(default=None, min_length=1, max_length=50)


class KnowledgeBaseStatusUpdateRequest(ApiBaseModel):
    knowledge_base_id: int = Field(gt=0)
    status: KnowledgeBaseStatus


class KnowledgeBaseDeleteRequest(ApiBaseModel):
    knowledge_base_id: int = Field(gt=0)
    confirmation_name: str = Field(min_length=1, max_length=50)


class KnowledgeBaseIdRequest(ApiBaseModel):
    knowledge_base_id: int = Field(gt=0)


class KnowledgeBaseListRequest(ApiBaseModel):
    query: str | None = Field(default=None, max_length=50)
    status: KnowledgeBaseStatus | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class KnowledgeBaseUpdateBody(KnowledgeBaseUpdateRequest):
    knowledge_base_id: int = Field(gt=0)


class KnowledgeBaseRead(ApiBaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    description: str | None
    visibility: KnowledgeBaseVisibility
    status: KnowledgeBaseStatus
    created_at: ApiDateTime
    updated_at: ApiDateTime


class KnowledgeBaseSummaryRead(ApiBaseModel):
    knowledge_base: KnowledgeBaseRead
    file_count: int
    valid_document_count: int
    failed_document_count: int


class KnowledgeBasePageRead(ApiBaseModel):
    items: list[KnowledgeBaseRead]
    total: int
    page: int
    page_size: int
