from sqlalchemy import func, or_, select
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
    item = KnowledgeBase(
        owner_id=owner_id, name=name, description=description, visibility=visibility, status=status
    )
    db.add(item)
    db.flush()
    return item


def get_by_id(
    db: Session, knowledge_base_id: int, *, include_deleted: bool = False
) -> KnowledgeBase | None:
    stmt = select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
    if not include_deleted:
        stmt = stmt.where(KnowledgeBase.deleted_at.is_(None))
    return db.scalar(stmt)


def list_visible(
    db: Session,
    *,
    user_id: int,
    query: str | None,
    status: KnowledgeBaseStatus | None,
    page: int,
    page_size: int,
) -> tuple[list[KnowledgeBase], int]:
    filters = [
        KnowledgeBase.deleted_at.is_(None),
        or_(
            KnowledgeBase.owner_id == user_id,
            KnowledgeBase.visibility == KnowledgeBaseVisibility.PUBLIC,
        ),
    ]
    if query:
        filters.append(KnowledgeBase.name.ilike(f"%{query}%"))
    if status:
        filters.append(KnowledgeBase.status == status)
    total = db.scalar(select(func.count()).select_from(KnowledgeBase).where(*filters)) or 0
    rows = db.scalars(
        select(KnowledgeBase)
        .where(*filters)
        .order_by(KnowledgeBase.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), total


# CRUD compatibility for internal RAG callers and historical model tests. HTTP compatibility is removed.
def get_knowledge_base_by_id(db: Session, knowledge_base_id: int) -> KnowledgeBase | None:
    return get_by_id(db, knowledge_base_id)


def list_knowledge_bases_by_owner(db: Session, owner_id: int) -> list[KnowledgeBase]:
    return list(
        db.scalars(
            select(KnowledgeBase).where(
                KnowledgeBase.owner_id == owner_id, KnowledgeBase.deleted_at.is_(None)
            )
        )
    )
