from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.audit.service import record as audit
from api.document import crud
from api.document.enums import DocumentParseStatus
from api.document.model import Document
from api.document.schema import (
    BatchRetryRead,
    ChunkPageRead,
    ChunkRead,
    DocumentCreateRequest,
    DocumentDeleteRead,
    DocumentPageRead,
    DocumentRead,
    ParseQueueRead,
)
from api.document.tasks import cleanup_vectors, process_file
from api.files.enums import FileStatus, FileStorageStatus
from api.files.model import FileRecord
from api.knowledge import service as knowledge_service
from common.dependencies import ensure_owner
from core.exceptions import AppException


def get_readable(db: Session, document_id: int, current_user):
    # 获取文档，并确认当前用户有权访问它所属的知识库。
    document = crud.get(db, document_id)
    if document is None:
        raise AppException("文档不存在", status_code=404)
    knowledge_service.get_readable(db, document.knowledge_base_id, current_user)
    return document


def detail(db: Session, document_id: int, current_user) -> DocumentRead:
    # 将数据库模型转换为对外返回的文档详情结构。
    return DocumentRead.model_validate(get_readable(db, document_id, current_user))


def create(db: Session, payload: DocumentCreateRequest, current_user) -> DocumentRead:
    # 校验文件、知识库及所有权后，创建一个处于待解析状态的文档。
    record = db.get(FileRecord, payload.file_id)
    if record is None:
        raise AppException("文件不存在", status_code=404)
    ensure_owner(record.owner_id, current_user, resource="文件")
    knowledge_service.get_owned_active(db, payload.knowledge_base_id, current_user)
    if record.storage_status != FileStorageStatus.PRESENT:
        raise AppException("源文件已删除，不能创建文档", status_code=409)
    if record.status != FileStatus.UPLOADED:
        raise AppException("当前文件状态不允许创建文档", status_code=409)
    if crud.active_for_file(db, record.id) is not None:
        raise AppException("当前文件已存在有效文档", status_code=409)

    document = Document(
        file_id=record.id,
        knowledge_base_id=payload.knowledge_base_id,
        title=payload.title,
        description=payload.description,
        file_size=record.file_size,
        parse_status=DocumentParseStatus.PENDING,
    )
    db.add(document)
    # flush 使数据库生成 document.id，便于记录审计信息。
    db.flush()
    audit(
        db,
        action="document.created",
        target_type="document",
        target_id=document.id,
        operator_id=current_user.id,
        detail={"file_id": record.id, "knowledge_base_id": document.knowledge_base_id},
    )
    db.commit()
    db.refresh(document)
    return DocumentRead.model_validate(document)


def list_items(
    db: Session,
    knowledge_base_id: int,
    current_user,
    *,
    parse_status: DocumentParseStatus | None,
    page: int,
    page_size: int,
) -> DocumentPageRead:
    # 分页查询知识库中的文档，可按解析状态过滤。
    knowledge_service.get_readable(db, knowledge_base_id, current_user)
    rows, total = crud.page_by_knowledge_base(
        db,
        knowledge_base_id,
        parse_status=parse_status,
        page=page,
        page_size=page_size,
    )
    return DocumentPageRead(
        items=[DocumentRead.model_validate(item) for item in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def chunks(db: Session, document_id: int, current_user, page: int, page_size: int) -> ChunkPageRead:
    # 仅允许预览解析成功的文档文本块，并按页返回。
    document = get_readable(db, document_id, current_user)
    if document.parse_status != DocumentParseStatus.SUCCESS:
        raise AppException("文档尚未解析成功", status_code=409)
    rows, total = crud.page_chunks(db, document.id, page, page_size)
    return ChunkPageRead(
        items=[ChunkRead.model_validate(item) for item in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def delete(
    db: Session, document_id: int, current_user, tasks: BackgroundTasks
) -> DocumentDeleteRead:
    # 软删除文档；向量数据放入后台任务清理，避免阻塞接口响应。
    document = get_readable(db, document_id, current_user)
    record = document.file
    knowledge_service.get_owned_active(db, document.knowledge_base_id, current_user)
    if record.status == FileStatus.PARSING:
        raise AppException("文档正在解析，不可删除", status_code=409)
    crud.soft_delete(db, document)
    if record.storage_status == FileStorageStatus.PRESENT:
        record.status = FileStatus.UPLOADED
    audit(
        db,
        action="document.deleted",
        target_type="document",
        target_id=document.id,
        operator_id=current_user.id,
    )
    db.commit()
    tasks.add_task(cleanup_vectors, document.id)
    return DocumentDeleteRead(document_id=document.id, vector_cleanup_queued=True)


def queue_parse(
    db: Session,
    file_id: int,
    current_user,
    tasks: BackgroundTasks,
    *,
    retry: bool = False,
) -> ParseQueueRead:
    # 校验文件是否可以解析，并将实际解析工作交给后台任务。
    record = db.get(FileRecord, file_id)
    if record is None:
        raise AppException("文件不存在", status_code=404)
    if record.storage_status != FileStorageStatus.PRESENT:
        raise AppException("源文件已删除，不能解析", status_code=409)

    document = crud.active_for_file(db, record.id)
    if document is None:
        raise AppException("请先创建待解析文档", status_code=409)
    knowledge_service.get_owned_active(db, document.knowledge_base_id, current_user)
    if retry:
        # 重试只允许用于上次解析失败的文件，并重置文档错误状态。
        if record.status != FileStatus.PARSE_FAILED:
            raise AppException("当前文件状态不允许重试", status_code=409)
        document.parse_status = DocumentParseStatus.PENDING
        document.error_msg = None
    else:
        # 首次解析要求文件已上传且文档仍处于待解析状态。
        if record.status != FileStatus.UPLOADED:
            raise AppException("当前文件状态不允许解析", status_code=409)
        if document.parse_status != DocumentParseStatus.PENDING:
            raise AppException("请先创建待解析文档", status_code=409)

    record.status = FileStatus.PARSE_PENDING
    # 先提交状态和审计记录，再加入任务，避免任务读取到未提交的数据。
    audit(
        db,
        action="file.parse_queued",
        target_type="file",
        target_id=record.id,
        operator_id=current_user.id,
        detail={"retry": retry, "document_id": document.id},
    )
    db.commit()
    tasks.add_task(process_file, record.id)
    return ParseQueueRead(file_id=record.id, document_id=document.id, status=record.status)


def retry_failed(
    db: Session, knowledge_base_id: int, current_user, tasks: BackgroundTasks
) -> BatchRetryRead:
    # 批量找出知识库中可重试的失败文件，并逐个加入解析队列。
    knowledge_service.get_owned_active(db, knowledge_base_id, current_user)
    records = db.execute(
        select(FileRecord, Document)
        .join(Document, Document.file_id == FileRecord.id)
        .where(
            Document.knowledge_base_id == knowledge_base_id,
            FileRecord.status == FileStatus.PARSE_FAILED,
            FileRecord.storage_status == FileStorageStatus.PRESENT,
            Document.deleted_at.is_(None),
        )
    ).all()
    queued = []
    for record, document in records:
        record.status = FileStatus.PARSE_PENDING
        document.parse_status = DocumentParseStatus.PENDING
        document.error_msg = None
        audit(
            db,
            action="file.parse_queued",
            target_type="file",
            target_id=record.id,
            operator_id=current_user.id,
            detail={"retry": True},
        )
        queued.append(record.id)
    db.commit()
    for file_id in queued:
        tasks.add_task(process_file, file_id)
    return BatchRetryRead(queued_file_ids=queued)
