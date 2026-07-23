"""知识库模块业务服务。"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.knowledge import crud as knowledge_crud
from api.knowledge.schema import KnowledgeBaseCreateRequest, KnowledgeBaseRead
from api.user import crud as user_crud
from core.exceptions import AppException


def create_knowledge_base(db: Session, payload: KnowledgeBaseCreateRequest) -> KnowledgeBaseRead:
    """创建知识库。"""
    owner = user_crud.get_user_by_id(db, payload.owner_id)
    if owner is None:
        raise AppException("所属用户不存在", status_code=404)

    try:
        knowledge_base = knowledge_crud.create_knowledge_base(
            db,
            owner_id=payload.owner_id,
            name=payload.name,
            description=payload.description,
            status=payload.status,
        )
        db.commit()
        return KnowledgeBaseRead.model_validate(knowledge_base)
    except SQLAlchemyError as exc:
        db.rollback()
        raise AppException("创建知识库失败，请稍后重试", status_code=500) from exc


def get_knowledge_base_detail(db: Session, knowledge_base_id: int) -> KnowledgeBaseRead:
    """查询知识库详情。"""
    knowledge_base = knowledge_crud.get_knowledge_base_by_id(db, knowledge_base_id)
    if knowledge_base is None:
        raise AppException("知识库不存在", status_code=404)
    return KnowledgeBaseRead.model_validate(knowledge_base)


def list_knowledge_bases(db: Session, owner_id: int) -> list[KnowledgeBaseRead]:
    """按用户查询知识库列表。"""
    owner = user_crud.get_user_by_id(db, owner_id)
    if owner is None:
        raise AppException("所属用户不存在", status_code=404)
    knowledge_bases = knowledge_crud.list_knowledge_bases_by_owner(db, owner_id)
    return [KnowledgeBaseRead.model_validate(item) for item in knowledge_bases]
