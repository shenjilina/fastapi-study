from enum import StrEnum


class DocumentParseStatus(StrEnum):
    PENDING = "pending"
    PARSING = "parsing"
    SUCCESS = "success"
    FAILED = "failed"
