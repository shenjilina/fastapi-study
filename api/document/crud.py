from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import uuid4

from api.document.enums import DocumentParseStatus
from api.document.model import Document
from api.files.enums import FileStatus
from api.knowledge.model import KnowledgeBase
from api.files.model import FileRecord


def create_document(
    db: Session,
    *,
    file_id: int | None = None,
    knowledge_base_id: int | None = None,
    title: str | None = None,
    description: str | None = None,
    file_size: int = 0,
    filename: str | None = None,
    file_type: str | None = None,
    file_md5: str | None = None,
    chunk_count: int = 0,
    parse_status: DocumentParseStatus = DocumentParseStatus.PENDING,
) -> Document:
    if file_id is None:
        if knowledge_base_id is None:
            raise ValueError("file_id is required")
        knowledge_base = db.get(KnowledgeBase, knowledge_base_id)
        if knowledge_base is None:
            raise ValueError("knowledge base is required")
        legacy_filename = filename or title or "legacy-document.txt"
        suffix = legacy_filename.rsplit(".", 1)[-1] if "." in legacy_filename else None
        legacy_file = FileRecord(
            owner_id=knowledge_base.owner_id,
            knowledge_base_id=knowledge_base_id,
            filename=legacy_filename,
            stored_filename=f"legacy-{uuid4().hex}",
            storage_path=None,
            file_type=file_type or suffix,
            file_size=file_size,
            file_md5=file_md5 or uuid4().hex,
            status=FileStatus.UPLOADED,
        )
        db.add(legacy_file)
        db.flush()
        file_id = legacy_file.id
    document = Document(
        file_id=file_id,
        title=title or filename or "未命名文档",
        description=description,
        file_size=file_size,
        chunk_count=chunk_count,
        parse_status=parse_status,
    )
    db.add(document)
    db.flush()
    db.refresh(document)
    return document


def get_document_by_file_id(db: Session, file_id: int) -> Document | None:
    statement = select(Document).where(
        Document.file_id == file_id,
        Document.deleted_at.is_(None),
    )
    return db.scalar(statement)


def get_document_by_id(
    db: Session, document_id: int, *, include_deleted: bool = False
) -> Document | None:
    statement = select(Document).where(Document.id == document_id)
    if not include_deleted:
        statement = statement.where(Document.deleted_at.is_(None))
    return db.scalar(statement)


def list_documents_by_knowledge_base(db: Session, knowledge_base_id: int) -> list[Document]:
    statement = (
        select(Document)
        .join(FileRecord, Document.file_id == FileRecord.id)
        .where(Document.deleted_at.is_(None), FileRecord.knowledge_base_id == knowledge_base_id)
        .order_by(Document.id.asc())
    )
    return list(db.scalars(statement))


def update_document_status(
    db: Session,
    *,
    document_id: int,
    parse_status: DocumentParseStatus,
    chunk_count: int | None = None,
    error_msg: str | None = None,
) -> Document | None:
    document = get_document_by_id(db, document_id)
    if document is None:
        return None
    document.parse_status = parse_status
    document.error_msg = error_msg
    if chunk_count is not None:
        document.chunk_count = chunk_count
    db.flush()
    db.refresh(document)
    return document


def soft_delete_document(db: Session, document: Document) -> None:
    document.deleted_at = datetime.now(timezone.utc)
    document.parse_status = DocumentParseStatus.FAILED
    document.chunk_count = 0
    db.flush()
