from pydantic import ConfigDict, Field, field_validator

from api.knowledge.enums import KnowledgeBaseStatus, KnowledgeBaseVisibility
from common.base_model import ApiBaseModel, ApiDateTime
from common.dependencies import strip_text


class KnowledgeBaseCreateRequest(ApiBaseModel):
    owner_id: int = Field(gt=0, description="所属用户 ID")
    name: str = Field(min_length=2, max_length=255, description="知识库名称")
    description: str | None = Field(default=None, max_length=1000, description="知识库描述")
    visibility: KnowledgeBaseVisibility = Field(
        default=KnowledgeBaseVisibility.PRIVATE, description="知识库可见性"
    )
    status: KnowledgeBaseStatus = Field(
        default=KnowledgeBaseStatus.ACTIVE, description="知识库状态"
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: str) -> str:
        text = strip_text(value)
        if not text:
            raise ValueError("知识库名称不能为空")
        return text

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return strip_text(value)


class KnowledgeBaseListRequest(ApiBaseModel):
    owner_id: int = Field(gt=0, description="所属用户 ID")


class KnowledgeBaseDetailRequest(ApiBaseModel):
    knowledge_base_id: int = Field(gt=0, description="知识库 ID")


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
    deleted_at: ApiDateTime | None
