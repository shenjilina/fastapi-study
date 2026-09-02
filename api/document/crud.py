from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.chunk.model import Chunk
from api.document.model import Document
from api.document.enums import DocumentParseStatus
from api.files.enums import FileStatus, FileStorageStatus
from api.files.model import FileRecord
from api.knowledge.model import KnowledgeBase
from uuid import uuid4


def create_document(
    db: Session,
    *,
    file_id: int | None = None,
    knowledge_base_id: int | None = None,
    title: str | None = None,
    filename: str | None = None,
    description: str | None = None,
    file_size: int = 0,
    file_type: str | None = None,
    file_md5: str | None = None,
    parse_status: DocumentParseStatus = DocumentParseStatus.PENDING,
    **_: object,
) -> Document:
    document_knowledge_base_id = knowledge_base_id
    if file_id is None:
        knowledge_base = db.get(KnowledgeBase, knowledge_base_id)
        if knowledge_base is None:
            raise ValueError("knowledge base is required")
        display_name = filename or title or "legacy-document.txt"
        record = FileRecord(
            owner_id=knowledge_base.owner_id,
            filename=display_name,
            stored_filename=None,
            storage_path=None,
            file_type=file_type,
            file_size=file_size,
            file_md5=file_md5 or uuid4().hex,
            status=FileStatus.UPLOADED,
            storage_status=FileStorageStatus.PRESENT,
        )
        db.add(record)
        db.flush()
        file_id = record.id
        document_knowledge_base_id = knowledge_base.id
    elif document_knowledge_base_id is None:
        raise ValueError("knowledge base is required")
    document = Document(
        file_id=file_id,
        knowledge_base_id=document_knowledge_base_id,
        title=title or filename or "未命名文档",
        description=description,
        file_size=file_size,
        parse_status=parse_status,
    )
    db.add(document)
    db.flush()
    return document


def active_for_file(db: Session, file_id: int) -> Document | None:
    return db.scalar(
        select(Document).where(Document.file_id == file_id, Document.deleted_at.is_(None))
    )


def get(db: Session, document_id: int, *, include_deleted: bool = False) -> Document | None:
    stmt = select(Document).where(Document.id == document_id)
    if not include_deleted:
        stmt = stmt.where(Document.deleted_at.is_(None))
    return db.scalar(stmt)


def page_chunks(
    db: Session, document_id: int, page: int, page_size: int
) -> tuple[list[Chunk], int]:
    filters = (Chunk.document_id == document_id, Chunk.deleted_at.is_(None))
    total = db.scalar(select(func.count()).select_from(Chunk).where(*filters)) or 0
    rows = db.scalars(
        select(Chunk)
        .where(*filters)
        .order_by(Chunk.chunk_index)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), total


def soft_delete(db: Session, document: Document) -> list[str]:
    now = datetime.now(timezone.utc)
    vector_ids = []
    for chunk in document.chunks:
        if chunk.deleted_at is None:
            chunk.deleted_at = now
            if chunk.vector_id:
                vector_ids.append(chunk.vector_id)
    document.deleted_at = now
    document.chunk_count = 0
    return vector_ids


def update_document_status(
    db: Session,
    *,
    document_id: int,
    parse_status: DocumentParseStatus,
    chunk_count: int | None = None,
    error_msg: str | None = None,
) -> Document | None:
    document = get(db, document_id)
    if document is None:
        return None
    document.parse_status = parse_status
    document.error_msg = error_msg
    if chunk_count is not None:
        document.chunk_count = chunk_count
    db.flush()
    return document


def list_documents_by_knowledge_base(db: Session, knowledge_base_id: int) -> list[Document]:
    return list(
        db.scalars(
            select(Document).where(
                Document.knowledge_base_id == knowledge_base_id, Document.deleted_at.is_(None)
            )
        )
    )


def page_by_knowledge_base(
    db: Session,
    knowledge_base_id: int,
    *,
    parse_status: DocumentParseStatus | None,
    page: int,
    page_size: int,
) -> tuple[list[Document], int]:
    filters = [Document.knowledge_base_id == knowledge_base_id, Document.deleted_at.is_(None)]
    if parse_status is not None:
        filters.append(Document.parse_status == parse_status)
    statement = select(Document).where(*filters)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.scalars(
        statement.order_by(Document.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return rows, total
