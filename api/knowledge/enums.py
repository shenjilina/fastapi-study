"""知识库模块状态枚举。"""

from enum import StrEnum


class KnowledgeBaseStatus(StrEnum):
    """知识库状态。"""

    ACTIVE = "active"
    DISABLED = "disabled"
