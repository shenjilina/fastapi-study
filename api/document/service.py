from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.chunk import crud as chunk_crud
from api.document import crud as document_crud
from api.document.enums import DocumentParseStatus
from api.document.schema import DocumentCreateRequest, DocumentStatusUpdateRequest
from api.files import crud as file_crud
from api.files.enums import FileStatus
from api.knowledge import crud as knowledge_crud
from common.dependencies import ensure_owner
from config.settings import get_settings
from core.exceptions import AppException
from core.langchain.chroma_store import get_chroma_store
from utils import file_parser, text_utils


def _owned_file(db: Session, file_id: int, current_user):
    record = file_crud.get_file(db, file_id)
    if record is None or record.status == FileStatus.PHYSICAL_DELETED:
        raise AppException("文件不存在", status_code=404)
    ensure_owner(record.owner_id, current_user, resource="文件")
    knowledge_base = knowledge_crud.get_knowledge_base_by_id(db, record.knowledge_base_id)
    if knowledge_base is None:
        raise AppException("知识库不存在", status_code=404)
    return record


def _mark_failed(db: Session, record, document, message: str, vector_ids: list[str]) -> None:
    vectors_cleaned = True
    if vector_ids:
        try:
            get_chroma_store().delete_by_ids(vector_ids)
        except Exception:
            vectors_cleaned = False
    chunk_crud.soft_delete_chunks(db, document.id)
    document.parse_status = DocumentParseStatus.FAILED
    document.error_msg = message[:4000]
    document.chunk_count = 0
    document.vector_cleaned = vectors_cleaned
    record.status = FileStatus.PARSE_FAILED
    db.commit()


def _process_document(db: Session, record, document):
    settings = get_settings()
    vector_ids: list[str] = []
    document.parse_status = DocumentParseStatus.PARSING
    document.error_msg = None
    record.status = FileStatus.PARSE_PENDING
    db.commit()
    try:
        if not record.storage_path:
            raise AppException("文件物理路径不存在", status_code=422)
        raw_text = file_parser.parse_file(Path(record.storage_path))
        cleaned_text = text_utils.clean_text(raw_text)
        if not cleaned_text:
            raise AppException("文件解析后文本内容为空", status_code=422)

        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
        )
        chunks, _ = text_utils.deduplicate_texts(splitter.split_text(cleaned_text))
        if not chunks:
            raise AppException("切片后无有效内容", status_code=422)

        vector_ids = get_chroma_store().add_texts(
            chunks,
            metadatas=[
                {
                    "knowledge_base_id": record.knowledge_base_id,
                    "document_id": document.id,
                    "filename": record.filename,
                    "chunk_index": index,
                }
                for index in range(len(chunks))
            ],
        )
        chunk_crud.create_chunks(db, document.id, chunks, vector_ids)
        document.chunk_count = len(chunks)
        document.parse_status = DocumentParseStatus.SUCCESS
        document.error_msg = None
        document.vector_cleaned = False
        record.status = FileStatus.UPLOADED
        db.commit()
        return document
    except Exception as exc:
        db.rollback()
        _mark_failed(db, record, document, str(exc), vector_ids)
        raise


def create_document(db: Session, payload: DocumentCreateRequest, current_user):
    record = _owned_file(db, payload.file_id, current_user)
    existing = document_crud.get_document_by_file_id(db, record.id)
    if existing is not None:
        return existing
    try:
        document = document_crud.create_document(
            db,
            file_id=record.id,
            title=payload.title,
            description=payload.description,
            file_size=record.file_size,
            parse_status=DocumentParseStatus.PENDING,
        )
        db.commit()
        return _process_document(db, record, document)
    except AppException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise AppException("创建文档失败，请稍后重试", status_code=500) from exc


def list_documents_by_knowledge_base(db: Session, knowledge_base_id: int, current_user):
    knowledge_base = knowledge_crud.get_knowledge_base_by_id(db, knowledge_base_id)
    if knowledge_base is None:
        raise AppException("知识库不存在", status_code=404)
    ensure_owner(knowledge_base.owner_id, current_user, resource="文档")
    return document_crud.list_documents_by_knowledge_base(db, knowledge_base_id)


def update_document_status(
    db: Session, document_id: int, payload: DocumentStatusUpdateRequest, current_user
):
    document = document_crud.get_document_by_id(db, document_id)
    if document is None:
        raise AppException("文档不存在", status_code=404)
    ensure_owner(document.file.owner_id, current_user, resource="文档")
    document.parse_status = payload.parse_status
    if payload.chunk_count is not None:
        document.chunk_count = payload.chunk_count
    db.commit()
    return document


def delete_document(db: Session, document_id: int, current_user) -> dict:
    document = document_crud.get_document_by_id(db, document_id)
    if document is None:
        raise AppException("文档不存在", status_code=404)
    ensure_owner(document.file.owner_id, current_user, resource="文档")
    vector_ids = [
        chunk.vector_id for chunk in document.chunks if chunk.deleted_at is None and chunk.vector_id
    ]
    vectors_cleaned = True
    try:
        if vector_ids:
            get_chroma_store().delete_by_ids(vector_ids)
        chunk_crud.soft_delete_chunks(db, document.id)
    except Exception:
        vectors_cleaned = False
    document.deleted_at = datetime.now(timezone.utc)
    document.vector_cleaned = vectors_cleaned
    document.chunk_count = 0
    db.commit()
    return {
        "document_id": document_id,
        "filename": document.file.filename,
        "deleted": True,
        "vector_cleaned": vectors_cleaned,
    }
