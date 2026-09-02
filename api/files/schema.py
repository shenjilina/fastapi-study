from pydantic import ConfigDict, Field

from api.files.enums import FileStatus, FileStorageStatus
from common.base_model import ApiBaseModel, ApiDateTime


class FileRead(ApiBaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    filename: str
    file_type: str | None
    mime_type: str | None
    file_size: int
    file_md5: str
    status: FileStatus
    storage_status: FileStorageStatus
    created_at: ApiDateTime
    updated_at: ApiDateTime


class FileUploadResult(ApiBaseModel):
    filename: str
    accepted: bool
    file_id: int | None = None
    file: FileRead | None = None
    error: str | None = None


class FilePageRead(ApiBaseModel):
    items: list[FileRead]
    total: int
    page: int
    page_size: int


class SourceDeleteRead(ApiBaseModel):
    file_id: int
    storage_status: FileStorageStatus


class FileIdRequest(ApiBaseModel):
    file_id: int = Field(gt=0)


class FileListRequest(ApiBaseModel):
    file_status: FileStatus | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
