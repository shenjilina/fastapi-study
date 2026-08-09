"""文档管理模块业务服务。

职责：
- 组装文档业务流程：文件校验 -> MD5 去重 -> 文本解析 -> 智能切片 -> 向量入库 -> 数据库存元数据。
- 文档删除：向量 + DB 联动清理。
- 知库存在性校验通过 knowledge 模块 CRUD 完成，不直接操作知识库表。
"""

import shutil
import tempfile
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.document import crud as document_crud
from api.document.enums import DocumentParseStatus
from api.document.schema import (
    DocumentCreateRequest,
    DocumentStatusUpdateRequest,
)
from api.knowledge import crud as knowledge_crud
from config.log_config import get_logger
from config.settings import get_settings
from core.exceptions import AppException
from core.langchain.chroma_store import get_chroma_store
from utils import file_parser, hash_utils, text_utils

logger = get_logger(__name__)


def _rollback_vectors(vector_ids: list[str]) -> None:
    """回滚已写入的向量数据，失败仅告警不阻断主流程。"""
    if not vector_ids:
        return
    try:
        get_chroma_store().delete_by_ids(vector_ids)
        logger.warning("Rolled back %d vectors after processing failure.", len(vector_ids))
    except Exception as rollback_exc:  # 回滚失败不应掩盖原始错误。
        logger.warning("Failed to rollback vectors: %s", rollback_exc)


def _commit_document_status(
    db: Session,
    *,
    document_id: int,
    parse_status: DocumentParseStatus,
    chunk_count: int | None = None,
) -> None:
    """提交文档解析状态，失败时回滚事务并抛出统一业务异常。"""
    try:
        document_crud.update_document_status(
            db,
            document_id=document_id,
            parse_status=parse_status,
            chunk_count=chunk_count,
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("Failed to persist document status: id=%d err=%s", document_id, exc)
        raise AppException("文档状态更新失败，请稍后重试", status_code=500) from exc


def create_document(db: Session, payload: DocumentCreateRequest):
    """创建文档元数据，并做知识库归属和重复性校验。"""
    knowledge_base = knowledge_crud.get_knowledge_base_by_id(db, payload.knowledge_base_id)
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
    knowledge_base = knowledge_crud.get_knowledge_base_by_id(db, knowledge_base_id)
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


def upload_document(db: Session, knowledge_base_id: int, file: UploadFile) -> dict:
    """文件上传全流程：校验 -> MD5 去重 -> 文本解析 -> 智能切片 -> 向量入库 -> 数据库存元数据。

    任何步骤失败都会将文档状态置为 FAILED 并回滚向量数据。
    """
    settings = get_settings()

    # 1. 验证知识库存在
    knowledge_base = knowledge_crud.get_knowledge_base_by_id(db, knowledge_base_id)
    if knowledge_base is None:
        raise AppException("所属知识库不存在", status_code=404)

    # 2. 文件格式白名单校验
    filename = file.filename or "unknown"
    file_ext = Path(filename).suffix.lower().lstrip(".")
    if file_ext not in settings.allowed_file_extensions:
        raise AppException(
            f"不支持的文件类型: .{file_ext}，仅支持 {settings.allowed_file_extensions}",
            status_code=400,
        )

    # 3. 文件大小限制
    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
    if file.size and file.size > max_size_bytes:
        raise AppException(
            f"文件大小超过限制: 最大 {settings.max_upload_size_mb}MB",
            status_code=413,
        )

    # 4. 保存到临时文件
    tmp_path = Path(tempfile.mktemp(suffix=f".{file_ext}"))
    try:
        with tmp_path.open("wb") as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)

        actual_size = tmp_path.stat().st_size
        if actual_size == 0:
            raise AppException("文件内容为空", status_code=422)
        if actual_size > max_size_bytes:
            raise AppException(
                f"文件大小超过限制: 最大 {settings.max_upload_size_mb}MB",
                status_code=413,
            )

        # 5. 计算 MD5
        file_md5 = hash_utils.compute_file_md5(tmp_path)

        # 6. MD5 去重
        existing = document_crud.get_document_by_md5(
            db,
            knowledge_base_id=knowledge_base_id,
            file_md5=file_md5,
        )
        if existing is not None:
            raise AppException("当前知识库中已存在相同文件", status_code=409)

        # 7. 创建文档记录（PENDING 状态），失败时回滚事务。
        try:
            document = document_crud.create_document(
                db,
                knowledge_base_id=knowledge_base_id,
                filename=filename,
                file_type=file_ext,
                file_size=actual_size,
                file_md5=file_md5,
                chunk_count=0,
                parse_status=DocumentParseStatus.PENDING,
            )
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            raise AppException("创建文档记录失败，请稍后重试", status_code=500) from exc

        # 8. 文本解析 -> 切片 -> 向量入库
        # vector_ids 提前声明，便于后续失败时回滚已写入的向量。
        vector_ids: list[str] = []
        try:
            raw_text = file_parser.parse_file(tmp_path)
            cleaned_text = text_utils.clean_text(raw_text)
            if not cleaned_text:
                raise AppException("文件解析后文本内容为空", status_code=422)

            # 9. LangChain 智能切片
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )
            chunks = splitter.split_text(cleaned_text)
            chunks, _removed = text_utils.deduplicate_texts(chunks)

            if not chunks:
                raise AppException("切片后无有效内容", status_code=422)

            # 10. 向量入库
            chroma_store = get_chroma_store()
            metadatas = [
                {
                    "knowledge_base_id": knowledge_base_id,
                    "document_id": document.id,
                    "filename": filename,
                    "chunk_index": i,
                }
                for i in range(len(chunks))
            ]
            vector_ids = chroma_store.add_texts(chunks, metadatas=metadatas)

            # 11. 更新文档状态为成功，落库失败时回滚已写入的向量，避免无主垃圾向量。
            # 失败后直接标记 FAILED 并抛出，避免进入外层分支重复回滚。
            try:
                _commit_document_status(
                    db,
                    document_id=document.id,
                    parse_status=DocumentParseStatus.SUCCESS,
                    chunk_count=len(chunks),
                )
            except AppException:
                # 此处仅回滚向量并清空引用，FAILED 标记由外层分支统一执行一次。
                _rollback_vectors(vector_ids)
                vector_ids = []
                raise

            logger.info(
                "Document uploaded: id=%d chunks=%d vectors=%d",
                document.id,
                len(chunks),
                len(vector_ids),
            )
            return {
                "document": document,
                "vector_ids": vector_ids,
                "chunk_count": len(chunks),
            }

        except AppException:
            # 业务异常：标记失败后向上抛，已写入的向量同步回滚。
            _rollback_vectors(vector_ids)
            _commit_document_status(
                db,
                document_id=document.id,
                parse_status=DocumentParseStatus.FAILED,
            )
            raise
        except Exception as exc:
            # 未知异常：回滚向量、标记失败并记录。
            logger.exception("Document processing failed: id=%d err=%s", document.id, exc)
            _rollback_vectors(vector_ids)
            _commit_document_status(
                db,
                document_id=document.id,
                parse_status=DocumentParseStatus.FAILED,
            )
            raise AppException(f"文档处理失败: {exc}", status_code=500) from exc

    finally:
        tmp_path.unlink(missing_ok=True)


def delete_document(db: Session, document_id: int) -> dict:
    """删除文档：同时删除向量数据和数据库记录。"""
    document = document_crud.get_document_by_id(db, document_id)
    if document is None:
        raise AppException("文档不存在", status_code=404)

    filename = document.filename

    # 1. 删除向量数据
    try:
        chroma_store = get_chroma_store()
        deleted_count = chroma_store.delete_by_metadata({"document_id": document_id})
        logger.info(
            "Vectors deleted: document_id=%d count=%d",
            document_id,
            deleted_count,
        )
    except Exception as exc:
        # 向量删除失败不阻塞 DB 删除，只记录警告
        logger.warning("Failed to delete vectors for document %d: %s", document_id, exc)

    # 2. 删除数据库记录
    try:
        document_crud.delete_document(db, document_id)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise AppException("删除文档失败，请稍后重试", status_code=500) from exc

    return {"document_id": document_id, "filename": filename, "deleted": True}
