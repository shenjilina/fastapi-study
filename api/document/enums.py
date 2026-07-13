"""文档模块使用的状态枚举。"""

from enum import StrEnum


class DocumentParseStatus(StrEnum):
    """文档解析状态。"""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
