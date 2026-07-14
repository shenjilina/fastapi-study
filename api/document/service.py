"""知识库和文档模块业务服务。"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.document import crud as document_crud
from api.document.schema import (
    DocumentCreateRequest,
    DocumentStatusUpdateRequest,
    KnowledgeBaseCreateRequest,
)
from api.user import crud as user_crud
from core.exceptions import AppException


def create_knowledge_base(db: Session, payload: KnowledgeBaseCreateRequest):
    """创建知识库。"""
    owner = user_crud.get_user_by_id(db, payload.owner_id)
    if owner is None:
        raise AppException("所属用户不存在", status_code=404)

    try:
        knowledge_base = document_crud.create_knowledge_base(
            db,
            owner_id=payload.owner_id,
            name=payload.name,
            description=payload.description,
            status=payload.status,
        )
        db.commit()
        return knowledge_base
    except SQLAlchemyError as exc:
        db.rollback()
        raise AppException("创建知识库失败，请稍后重试", status_code=500) from exc


def get_knowledge_base_detail(db: Session, knowledge_base_id: int):
    """查询知识库详情。"""
    knowledge_base = document_crud.get_knowledge_base_by_id(db, knowledge_base_id)
    if knowledge_base is None:
        raise AppException("知识库不存在", status_code=404)
    return knowledge_base


def list_knowledge_bases(db: Session, owner_id: int):
    """按用户查询知识库列表。"""
    owner = user_crud.get_user_by_id(db, owner_id)
    if owner is None:
        raise AppException("所属用户不存在", status_code=404)
    return document_crud.list_knowledge_bases_by_owner(db, owner_id)


def create_document(db: Session, payload: DocumentCreateRequest):
    """创建文档元数据，并做知识库归属和重复性校验。"""
    knowledge_base = document_crud.get_knowledge_base_by_id(db, payload.knowledge_base_id)
    if knowledge_base is None:
        raise AppException("所属知识库不存在", status_code=404)

    duplicated_document = document_crud.get_document_by_md5(
        db,
        knowledge_base_id=payload.knowledge_base_id,
        file_md5=payload.file_md5,
    )
    if duplicated_document is not None:
        raise AppException("当前知识库中已存在相同文件", status_code=409)

    try:
        document = document_crud.create_document(
            db,
            knowledge_base_id=payload.knowledge_base_id,
            filename=payload.filename,
            file_type=payload.file_type,
            file_size=payload.file_size,
            file_md5=payload.file_md5,
            chunk_count=payload.chunk_count,
            parse_status=payload.parse_status,
        )
        db.commit()
        return document
    except SQLAlchemyError as exc:
        db.rollback()
        raise AppException("创建文档失败，请稍后重试", status_code=500) from exc


def list_documents_by_knowledge_base(db: Session, knowledge_base_id: int):
    """查询知识库下的文档列表。"""
    knowledge_base = document_crud.get_knowledge_base_by_id(db, knowledge_base_id)
    if knowledge_base is None:
        raise AppException("知识库不存在", status_code=404)
    return document_crud.list_documents_by_knowledge_base(db, knowledge_base_id)


def update_document_status(
    db: Session,
    document_id: int,
    payload: DocumentStatusUpdateRequest,
):
    """更新文档解析状态。"""
    try:
        document = document_crud.update_document_status(
            db,
            document_id=document_id,
            parse_status=payload.parse_status,
            chunk_count=payload.chunk_count,
        )
        if document is None:
            db.rollback()
            raise AppException("文档不存在", status_code=404)

        db.commit()
        return document
    except AppException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise AppException("更新文档状态失败，请稍后重试", status_code=500) from exc
