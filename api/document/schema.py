"""文档模块 Schema。"""

from pydantic import ConfigDict, Field, field_validator

from api.document.enums import DocumentParseStatus
from common.base_model import ApiBaseModel, ApiDateTime
from common.dependencies import strip_text


class DocumentCreateRequest(ApiBaseModel):
    """创建文档请求体。"""

    knowledge_base_id: int = Field(gt=0, description="所属知识库 ID")
    filename: str = Field(min_length=1, max_length=255, description="原始文件名")
    file_type: str = Field(min_length=2, max_length=20, description="文件类型，如 txt / pdf")
    file_size: int = Field(gt=0, le=10 * 1024 * 1024, description="文件大小，单位字节")
    file_md5: str = Field(min_length=32, max_length=32, description="文件 MD5 摘要")
    chunk_count: int = Field(default=0, ge=0, description="切片数量")
    parse_status: DocumentParseStatus = Field(
        default=DocumentParseStatus.PENDING,
        description="文档解析状态",
    )

    @field_validator("filename", "file_type", "file_md5", mode="before")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        text = strip_text(value)
        if not text:
            raise ValueError("字段不能为空")
        return text

    @field_validator("file_type")
    @classmethod
    def _validate_file_type(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"txt", "pdf"}:
            raise ValueError("文件类型仅支持 txt 或 pdf")
        return normalized

    @field_validator("file_md5")
    @classmethod
    def _validate_file_md5(cls, value: str) -> str:
        normalized = value.lower()
        if len(normalized) != 32 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError("file_md5 必须是 32 位十六进制字符串")
        return normalized


class DocumentStatusUpdateRequest(ApiBaseModel):
    """更新文档解析状态请求体。"""

    parse_status: DocumentParseStatus = Field(description="目标解析状态")
    chunk_count: int | None = Field(default=None, ge=0, description="切片数量")


class DocumentListRequest(ApiBaseModel):
    """查询知识库文档列表请求体（GET 转 POST，参数入请求体）。"""

    knowledge_base_id: int = Field(gt=0, description="所属知识库 ID")


class DocumentUploadResponse(ApiBaseModel):
    """文档上传响应结构。"""

    document: "DocumentRead"
    vector_ids: list[str] = Field(default_factory=list, description="向量库中的 ID 列表")
    chunk_count: int = Field(ge=0, description="实际切片数量")


class DocumentDeleteResponse(ApiBaseModel):
    """文档删除响应结构。"""

    document_id: int
    filename: str
    deleted: bool = True


class DocumentRead(ApiBaseModel):
    """文档响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    knowledge_base_id: int
    filename: str
    file_type: str
    file_size: int
    file_md5: str
    chunk_count: int
    parse_status: DocumentParseStatus
    created_at: ApiDateTime
    updated_at: ApiDateTime


DocumentUploadResponse.model_rebuild()
