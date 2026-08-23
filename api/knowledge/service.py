from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.audit.service import record as audit
from api.document.enums import DocumentParseStatus
from api.document.model import Document
from api.knowledge import crud
from api.knowledge.enums import KnowledgeBaseStatus, KnowledgeBaseVisibility
from api.knowledge.model import KnowledgeBase
from api.knowledge.schema import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseDeleteRequest,
    KnowledgeBaseRead,
    KnowledgeBaseStatusUpdateRequest,
    KnowledgeBaseSummaryRead,
    KnowledgeBaseUpdateRequest,
)
from core.exceptions import AppException


def get_readable(db: Session, knowledge_base_id: int, current_user) -> KnowledgeBase:
    item = crud.get_by_id(db, knowledge_base_id)
    if item is None:
        raise AppException("知识库不存在", status_code=404)
    if item.owner_id != current_user.id and item.visibility != KnowledgeBaseVisibility.PUBLIC:
        raise AppException("无权访问该知识库", status_code=403)
    return item


def get_owned_active(db: Session, knowledge_base_id: int, current_user) -> KnowledgeBase:
    item = get_readable(db, knowledge_base_id, current_user)
    if item.owner_id != current_user.id:
        raise AppException("无权操作其他用户的知识库", status_code=403)
    if item.status != KnowledgeBaseStatus.ACTIVE:
        raise AppException("知识库已禁用或归档，不可操作", status_code=403)
    return item


def create(db: Session, payload: KnowledgeBaseCreateRequest, current_user) -> KnowledgeBaseRead:
    item = KnowledgeBase(owner_id=current_user.id, **payload.model_dump())
    db.add(item)
    db.flush()
    audit(
        db,
        action="knowledge_base.created",
        target_type="knowledge_base",
        target_id=item.id,
        operator_id=current_user.id,
    )
    db.commit()
    return KnowledgeBaseRead.model_validate(item)


def list_items(
    db: Session,
    current_user,
    *,
    query: str | None,
    status: KnowledgeBaseStatus | None,
    page: int,
    page_size: int,
):
    rows, total = crud.list_visible(
        db, user_id=current_user.id, query=query, status=status, page=page, page_size=page_size
    )
    return [KnowledgeBaseRead.model_validate(row) for row in rows], total


def update(
    db: Session, knowledge_base_id: int, payload: KnowledgeBaseUpdateRequest, current_user
) -> KnowledgeBaseRead:
    item = get_owned_active(db, knowledge_base_id, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    audit(
        db,
        action="knowledge_base.updated",
        target_type="knowledge_base",
        target_id=item.id,
        operator_id=current_user.id,
    )
    db.commit()
    return KnowledgeBaseRead.model_validate(item)


def change_status(
    db: Session, knowledge_base_id: int, payload: KnowledgeBaseStatusUpdateRequest, current_user
) -> KnowledgeBaseRead:
    item = get_readable(db, knowledge_base_id, current_user)
    if item.owner_id != current_user.id:
        raise AppException("无权操作其他用户的知识库", status_code=403)
    if (
        item.status == KnowledgeBaseStatus.DISABLED
        and payload.status == KnowledgeBaseStatus.ARCHIVED
    ):
        raise AppException("禁用知识库需先启用后归档", status_code=409)
    item.status = payload.status
    audit(
        db,
        action="knowledge_base.status_changed",
        target_type="knowledge_base",
        target_id=item.id,
        operator_id=current_user.id,
        detail={"status": payload.status},
    )
    db.commit()
    return KnowledgeBaseRead.model_validate(item)


def delete(
    db: Session, knowledge_base_id: int, payload: KnowledgeBaseDeleteRequest, current_user
) -> None:
    item = get_readable(db, knowledge_base_id, current_user)
    if item.owner_id != current_user.id:
        raise AppException("无权操作其他用户的知识库", status_code=403)
    if item.name != payload.confirmation_name:
        raise AppException("确认名称不匹配", status_code=422)
    item.deleted_at = datetime.now(timezone.utc)
    audit(
        db,
        action="knowledge_base.deleted",
        target_type="knowledge_base",
        target_id=item.id,
        operator_id=current_user.id,
    )
    db.commit()


def summary(db: Session, knowledge_base_id: int, current_user) -> KnowledgeBaseSummaryRead:
    item = get_readable(db, knowledge_base_id, current_user)
    files = (
        db.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.knowledge_base_id == item.id, Document.deleted_at.is_(None))
        )
        or 0
    )
    valid = (
        db.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.knowledge_base_id == item.id, Document.deleted_at.is_(None))
        )
        or 0
    )
    failed = (
        db.scalar(
            select(func.count())
            .select_from(Document)
            .where(
                Document.knowledge_base_id == item.id,
                Document.deleted_at.is_(None),
                Document.parse_status == DocumentParseStatus.FAILED,
            )
        )
        or 0
    )
    return KnowledgeBaseSummaryRead(
        knowledge_base=KnowledgeBaseRead.model_validate(item),
        file_count=files,
        valid_document_count=valid,
        failed_document_count=failed,
    )
