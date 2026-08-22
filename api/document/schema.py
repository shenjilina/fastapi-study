from pydantic import ConfigDict, Field

from api.document.enums import DocumentParseStatus
from common.base_model import ApiBaseModel, ApiDateTime


class DocumentCreateRequest(ApiBaseModel):
    file_id: int = Field(gt=0, description="已上传文件 ID")
    title: str = Field(min_length=1, max_length=255, description="文档标题")
    description: str | None = Field(default=None, max_length=2000, description="文档描述")


class DocumentStatusUpdateRequest(ApiBaseModel):
    document_id: int = Field(gt=0, description="文档 ID")
    parse_status: DocumentParseStatus = Field(description="目标解析状态")
    chunk_count: int | None = Field(default=None, ge=0, description="切片数量")


class DocumentListRequest(ApiBaseModel):
    knowledge_base_id: int = Field(gt=0, description="所属知识库 ID")


class DocumentRead(ApiBaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_id: int
    title: str
    description: str | None
    chunk_count: int
    parse_status: DocumentParseStatus
    error_msg: str | None
    vector_cleaned: bool
    file_size: int
    created_at: ApiDateTime
    updated_at: ApiDateTime
    deleted_at: ApiDateTime | None
