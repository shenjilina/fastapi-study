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
    # 后台解析主流程：提取文本、切分、向量化，并保存文本块及状态。
    db = SessionLocal()
    vector_ids: list[str] = []
    try:
        claimed = db.execute(
            # 条件更新用于“抢占”任务，避免同一文件被并发解析。
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
            # 任务执行前再次校验关联对象和资源状态，防止处理已失效的任务。
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
        # 将原始文件转换为可检索的纯文本，并清理无效内容。
        if not text:
            raise ValueError("文件解析后文本内容为空")
        settings = get_settings()
        splitter = __import__(
            "langchain_text_splitters", fromlist=["RecursiveCharacterTextSplitter"]
        ).RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
        )
        # 按配置切分文本并去重，便于后续检索和控制向量粒度。
        contents, _ = text_utils.deduplicate_texts(splitter.split_text(text))
        if not contents:
            raise ValueError("切片后无有效内容")
        vector_ids = get_chroma_store().add_texts(
            # 写入向量库，同时保存知识库、文档和块序号等检索元数据。
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
        # 向量写入后重新建立数据库会话，避免长任务持有旧连接。
        db = SessionLocal()
        record = db.get(FileRecord, file_id)
        document = crud.active_for_file(db, file_id)
        if not record or not document or record.status != FileStatus.PARSING:
            # 状态已被其他操作改变时，删除刚写入的向量，避免产生孤儿数据。
            get_chroma_store().delete_by_ids(vector_ids)
            return
        create_chunks(db, document.id, contents, vector_ids)
        # 数据库记录与向量 ID 关联，解析成功后更新文件和文档状态。
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
        # 任一步骤失败都回滚数据库，并尽力清理已写入的向量和文本块。
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
    # 删除文档关联的向量数据；用于文档软删除后的异步清理。
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
