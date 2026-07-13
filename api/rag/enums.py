"""RAG 模块使用的状态枚举。"""

from enum import StrEnum


class KnowledgeBaseStatus(StrEnum):
    """知识库状态。"""

    ACTIVE = "active"
    DISABLED = "disabled"


class ConversationRecordStatus(StrEnum):
    """问答记录生成状态。"""

    GENERATED = "generated"
    FAILED = "failed"
