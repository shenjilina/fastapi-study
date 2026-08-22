from sqlalchemy import select
from sqlalchemy.orm import Session

from api.knowledge.enums import KnowledgeBaseStatus, KnowledgeBaseVisibility
from api.knowledge.model import KnowledgeBase


def create_knowledge_base(
    db: Session,
    *,
    owner_id: int,
    name: str,
    description: str | None = None,
    visibility: KnowledgeBaseVisibility = KnowledgeBaseVisibility.PRIVATE,
    status: KnowledgeBaseStatus = KnowledgeBaseStatus.ACTIVE,
) -> KnowledgeBase:
    knowledge_base = KnowledgeBase(
        owner_id=owner_id,
        name=name,
        description=description,
        visibility=visibility,
        status=status,
    )
    db.add(knowledge_base)
    db.flush()
    db.refresh(knowledge_base)
    return knowledge_base


def get_knowledge_base_by_id(db: Session, knowledge_base_id: int) -> KnowledgeBase | None:
    statement = select(KnowledgeBase).where(
        KnowledgeBase.id == knowledge_base_id,
        KnowledgeBase.deleted_at.is_(None),
    )
    return db.scalar(statement)


def list_knowledge_bases_by_owner(db: Session, owner_id: int) -> list[KnowledgeBase]:
    statement = (
        select(KnowledgeBase)
        .where(KnowledgeBase.owner_id == owner_id, KnowledgeBase.deleted_at.is_(None))
        .order_by(KnowledgeBase.id.asc())
    )
    return list(db.scalars(statement))
