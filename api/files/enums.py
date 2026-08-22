from enum import StrEnum


class FileStatus(StrEnum):
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    PARSE_PENDING = "parse_pending"
    PARSE_FAILED = "parse_failed"
    PHYSICAL_DELETED = "physical_deleted"
