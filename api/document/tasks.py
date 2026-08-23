from pathlib import Path

from sqlalchemy import update

from api.audit.service import record as audit
from api.chunk.crud import create_chunks, soft_delete_chunks
from api.document import crud
from api.document.enums import DocumentParseStatus
from api.files.enums import FileStatus, FileStorageStatus
from api.files.model import FileRecord
from api.knowledge.enums import KnowledgeBaseStatus
from api.knowledge.model import KnowledgeBase
from config.settings import get_settings
from core.db import SessionLocal
from core.langchain.chroma_store import get_chroma_store
from utils import file_parser, text_utils


def process_file(file_id: int) -> None:
    db = SessionLocal()
    vector_ids: list[str] = []
    try:
        claimed = db.execute(
            update(FileRecord)
            .where(FileRecord.id == file_id, FileRecord.status == FileStatus.PARSE_PENDING)
            .values(status=FileStatus.PARSING)
        )
        if claimed.rowcount != 1:
            db.rollback()
            return
        record = db.get(FileRecord, file_id)
        document = crud.active_for_file(db, file_id)
        knowledge_base = db.get(KnowledgeBase, document.knowledge_base_id) if document else None
        if (
            not record
            or not document
            or not knowledge_base
            or knowledge_base.status != KnowledgeBaseStatus.ACTIVE
            or record.storage_status != FileStorageStatus.PRESENT
        ):
            if record:
                record.status = FileStatus.UPLOADED
            if document:
                document.parse_status = DocumentParseStatus.PENDING
            db.commit()
            return
        document.parse_status = DocumentParseStatus.PARSING
        document.error_msg = None
        audit(
            db,
            action="file.parse_started",
            target_type="file",
            target_id=file_id,
            detail={"document_id": document.id},
        )
        db.commit()

        text = text_utils.clean_text(file_parser.parse_file(Path(record.storage_path or "")))
        if not text:
            raise ValueError("文件解析后文本内容为空")
        settings = get_settings()
        splitter = __import__(
            "langchain_text_splitters", fromlist=["RecursiveCharacterTextSplitter"]
        ).RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
        )
        contents, _ = text_utils.deduplicate_texts(splitter.split_text(text))
        if not contents:
            raise ValueError("切片后无有效内容")
        vector_ids = get_chroma_store().add_texts(
            contents,
            metadatas=[
                {
                    "knowledge_base_id": document.knowledge_base_id,
                    "document_id": document.id,
                    "filename": record.filename,
                    "chunk_index": i,
                }
                for i in range(len(contents))
            ],
        )
        db.close()
        db = SessionLocal()
        record = db.get(FileRecord, file_id)
        document = crud.active_for_file(db, file_id)
        if not record or not document or record.status != FileStatus.PARSING:
            get_chroma_store().delete_by_ids(vector_ids)
            return
        create_chunks(db, document.id, contents, vector_ids)
        document.chunk_count = len(contents)
        document.parse_status = DocumentParseStatus.SUCCESS
        document.vector_cleaned = False
        record.status = FileStatus.SUCCESS
        audit(
            db,
            action="file.parse_succeeded",
            target_type="file",
            target_id=file_id,
            detail={"chunks": len(contents)},
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        failure_db = SessionLocal()
        try:
            record = failure_db.get(FileRecord, file_id)
            document = crud.active_for_file(failure_db, file_id)
            cleaned = True
            if vector_ids:
                try:
                    get_chroma_store().delete_by_ids(vector_ids)
                except Exception:
                    cleaned = False
            if document:
                soft_delete_chunks(failure_db, document.id)
                document.parse_status = DocumentParseStatus.FAILED
                document.error_msg = str(exc)[:4000]
                document.chunk_count = 0
                document.vector_cleaned = cleaned
            if record:
                record.status = FileStatus.PARSE_FAILED
            audit(
                failure_db,
                action="file.parse_failed",
                target_type="file",
                target_id=file_id,
                detail={"error": str(exc)[:500]},
            )
            failure_db.commit()
        finally:
            failure_db.close()
    finally:
        db.close()


def cleanup_vectors(document_id: int) -> None:
    db = SessionLocal()
    try:
        document = crud.get(db, document_id, include_deleted=True)
        if not document:
            return
        ids = [chunk.vector_id for chunk in document.chunks if chunk.vector_id]
        if ids:
            get_chroma_store().delete_by_ids(ids)
        document.vector_cleaned = True
        audit(db, action="document.vectors_cleaned", target_type="document", target_id=document_id)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
