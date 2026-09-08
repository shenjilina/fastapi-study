from enum import StrEnum


class DocumentParseStatus(StrEnum):
    PENDING = "PENDING"
    PARSING = "PARSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
