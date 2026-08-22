from enum import StrEnum


class KnowledgeBaseStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DISABLED = "disabled"


class KnowledgeBaseVisibility(StrEnum):
    PRIVATE = "private"
    PUBLIC = "public"
