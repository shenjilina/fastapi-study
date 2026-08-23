from enum import StrEnum


class KnowledgeBaseStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DISABLED = "DISABLED"


class KnowledgeBaseVisibility(StrEnum):
    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"
