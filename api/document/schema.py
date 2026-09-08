from pydantic import ConfigDict, Field

from api.document.enums import DocumentParseStatus
from api.files.enums import FileStatus
from common.base_model import ApiBaseModel, ApiDateTime


class DocumentRead(ApiBaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_id: int
    knowledge_base_id: int
    title: str
    description: str | None
    chunk_count: int
    parse_status: DocumentParseStatus
    error_msg: str | None
    vector_cleaned: bool
    file_size: int
    created_at: ApiDateTime
    updated_at: ApiDateTime


class DocumentPageRead(ApiBaseModel):
    items: list[DocumentRead]
    total: int
    page: int
    page_size: int


class DocumentCreateRequest(ApiBaseModel):
    file_id: int = Field(gt=0)
    knowledge_base_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class ChunkRead(ApiBaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chunk_index: int
    content: str
    created_at: ApiDateTime


class ChunkPageRead(ApiBaseModel):
    items: list[ChunkRead]
    total: int
    page: int
    page_size: int


class DocumentDeleteRead(ApiBaseModel):
    document_id: int
    vector_cleanup_queued: bool


class BatchRetryRead(ApiBaseModel):
    queued_file_ids: list[int]


class DocumentIdRequest(ApiBaseModel):
    document_id: int = Field(gt=0)


class ChunkListRequest(DocumentIdRequest):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class KnowledgeBaseIdRequest(ApiBaseModel):
    knowledge_base_id: int = Field(gt=0)


class DocumentListRequest(KnowledgeBaseIdRequest):
    parse_status: DocumentParseStatus | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class FileParseRequest(ApiBaseModel):
    file_id: int = Field(gt=0)
    retry: bool = False


class ParseQueueRead(ApiBaseModel):
    file_id: int
    document_id: int
    status: FileStatus
