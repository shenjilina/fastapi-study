from pydantic import Field

from api.files.enums import FileStatus
from common.base_model import ApiBaseModel, ApiDateTime


class FileUploadRead(ApiBaseModel):
    file_id: int
    filename: str
    stored_filename: str | None
    file_size: int
    file_md5: str
    mime_type: str | None
    status: FileStatus
    created_at: ApiDateTime


class FileDeleteRequest(ApiBaseModel):
    file_id: int = Field(gt=0)


class FileRead(FileUploadRead):
    knowledge_base_id: int
    owner_id: int
    file_type: str | None
    storage_path: str | None
    updated_at: ApiDateTime
