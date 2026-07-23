"""RAG 模块使用的状态枚举。"""

from enum import StrEnum


class ConversationRecordStatus(StrEnum):
    """问答记录生成状态。"""

    GENERATED = "generated"
    FAILED = "failed"
