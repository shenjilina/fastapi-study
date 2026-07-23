"""知识库模块 CRUD。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.knowledge.enums import KnowledgeBaseStatus
from api.knowledge.model import KnowledgeBase


def create_knowledge_base(
    db: Session,
    *,
    owner_id: int,
    name: str,
    description: str | None = None,
    status: KnowledgeBaseStatus = KnowledgeBaseStatus.ACTIVE,
) -> KnowledgeBase:
    """创建知识库。"""
    knowledge_base = KnowledgeBase(
        owner_id=owner_id,
        name=name,
        description=description,
        status=status,
    )
    db.add(knowledge_base)
    db.flush()
    db.refresh(knowledge_base)
    return knowledge_base


def get_knowledge_base_by_id(db: Session, knowledge_base_id: int) -> KnowledgeBase | None:
    """按主键查询知识库。"""
    return db.get(KnowledgeBase, knowledge_base_id)


def list_knowledge_bases_by_owner(db: Session, owner_id: int) -> list[KnowledgeBase]:
    """查询某个用户名下的全部知识库。"""
    statement = (
        select(KnowledgeBase)
        .where(KnowledgeBase.owner_id == owner_id)
        .order_by(KnowledgeBase.id.asc())
    )
    return list(db.scalars(statement))
