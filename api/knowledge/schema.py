"""知识库模块 Schema。"""

from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from api.knowledge.enums import KnowledgeBaseStatus
from common.base_model import ApiBaseModel
from common.dependencies import strip_text


class KnowledgeBaseCreateRequest(ApiBaseModel):
    """创建知识库请求体。"""

    owner_id: int = Field(gt=0, description="知识库所属用户 ID")
    name: str = Field(min_length=2, max_length=100, description="知识库名称")
    description: str | None = Field(default=None, max_length=1000, description="知识库描述")
    status: KnowledgeBaseStatus = Field(
        default=KnowledgeBaseStatus.ACTIVE,
        description="知识库状态",
    )

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        text = strip_text(value)
        if not text:
            raise ValueError("知识库名称不能为空")
        return text

    @field_validator("description", mode="before")
    @classmethod
    def _strip_description(cls, value: str | None) -> str | None:
        return strip_text(value)


class KnowledgeBaseListRequest(ApiBaseModel):
    """查询知识库列表请求体（GET 转 POST，参数入请求体）。"""

    owner_id: int = Field(gt=0, description="知识库所属用户 ID")


class KnowledgeBaseDetailRequest(ApiBaseModel):
    """查询知识库详情请求体（GET 转 POST，参数入请求体）。"""

    knowledge_base_id: int = Field(gt=0, description="知识库 ID")


class KnowledgeBaseRead(ApiBaseModel):
    """知识库响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    description: str | None
    status: KnowledgeBaseStatus
    created_at: datetime
    updated_at: datetime
