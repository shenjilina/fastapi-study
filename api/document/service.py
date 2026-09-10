from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.audit.service import record as audit
from api.document import crud
from api.document.enums import DocumentParseStatus
from api.document.model import Document
from api.document.schema import BatchRetryRead, ChunkPageRead, ChunkRead, DocumentCreateRequest, DocumentDeleteRead, DocumentPageRead, DocumentRead, ParseQueueRead
from api.document.tasks import cleanup_vectors, process_file
from api.files.enums import FileStatus, FileStorageStatus
from api.files.model import FileRecord
from api.knowledge import service as knowledge_service
from common.dependencies import ensure_owner
from core.exceptions import AppException


def get_readable(db: Session, document_id: int, current_user):
    """获取文档并校验当前用户对其所属知识库的读取权限。

    Args:
        db: 数据库会话。
        document_id: 文档 ID。
        current_user: 当前登录用户。

    Returns:
        Document: 校验通过后的文档 ORM 对象。

    Raises:
        AppException: 文档不存在（404）或无权限访问所属知识库。
    """
    document = crud.get(db, document_id)
    if document is None:
        raise AppException("文档不存在", status_code=404)
    knowledge_service.get_readable(db, document.knowledge_base_id, current_user)
    return document


def detail(db: Session, document_id: int, current_user) -> DocumentRead:
    """查询文档详情，返回文档读取模型（含权限校验）。"""
    return DocumentRead.model_validate(get_readable(db, document_id, current_user))


def create(db: Session, payload: DocumentCreateRequest, current_user) -> DocumentRead:
    """基于已上传文件创建文档。

    校验文件归属、知识库所有权与活跃状态、源文件存储状态、文件状态（必须为已上传），
    并确保该文件不存在有效文档。创建成功后记录审计日志并提交事务。

    Raises:
        AppException: 文件不存在（404）、非文件所有者、源文件已删除（409）、
            文件状态不允许创建（409）或该文件已存在有效文档（409）。
    """
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
    document = Document(file_id=record.id, knowledge_base_id=payload.knowledge_base_id, title=payload.title, description=payload.description, file_size=record.file_size, parse_status=DocumentParseStatus.PENDING)
    db.add(document)
    db.flush()
    audit(db, action="document.created", target_type="document", target_id=document.id, operator_id=current_user.id, detail={"file_id": record.id, "knowledge_base_id": document.knowledge_base_id})
    db.commit()
    db.refresh(document)
    return DocumentRead.model_validate(document)


def list_items(db: Session, knowledge_base_id: int, current_user, *, parse_status: DocumentParseStatus | None, page: int, page_size: int) -> DocumentPageRead:
    """分页查询指定知识库下的文档列表。

    Args:
        parse_status: 可选的解析状态过滤条件。
        page: 页码（从 1 开始）。
        page_size: 每页数量。

    Returns:
        DocumentPageRead: 文档分页结果，包含条目、总数与分页信息。
    """
    knowledge_service.get_readable(db, knowledge_base_id, current_user)
    rows, total = crud.page_by_knowledge_base(db, knowledge_base_id, parse_status=parse_status, page=page, page_size=page_size)
    return DocumentPageRead(items=[DocumentRead.model_validate(item) for item in rows], total=total, page=page, page_size=page_size)


def chunks(db: Session, document_id: int, current_user, page: int, page_size: int) -> ChunkPageRead:
    """分页查询文档解析后的分块（chunk）列表。

    仅当文档解析状态为成功时才允许查询，否则返回 409 冲突。

    Returns:
        ChunkPageRead: 分块分页结果，包含条目、总数与分页信息。
    """
    document = get_readable(db, document_id, current_user)
    if document.parse_status != DocumentParseStatus.SUCCESS:
        raise AppException("文档尚未解析成功", status_code=409)
    rows, total = crud.page_chunks(db, document.id, page, page_size)
    return ChunkPageRead(items=[ChunkRead.model_validate(item) for item in rows], total=total, page=page, page_size=page_size)


def delete(db: Session, document_id: int, current_user, tasks: BackgroundTasks) -> DocumentDeleteRead:
    """软删除文档，并安排后台任务清理其向量数据。

    解析中的文档不允许删除。软删除后，若源文件仍存在则将文件状态恢复为已上传，
    以便该文件可再次创建新文档。提交事务后注册向量清理后台任务。

    Returns:
        DocumentDeleteRead: 被删除的文档 ID 及向量清理任务是否已入队。
    """
    document = get_readable(db, document_id, current_user)
    record = document.file
    knowledge_service.get_owned_active(db, document.knowledge_base_id, current_user)
    if record.status == FileStatus.PARSING:
        raise AppException("文档正在解析，不可删除", status_code=409)
    crud.soft_delete(db, document)
    if record.storage_status == FileStorageStatus.PRESENT:
        record.status = FileStatus.UPLOADED
    audit(db, action="document.deleted", target_type="document", target_id=document.id, operator_id=current_user.id)
    db.commit()
    tasks.add_task(cleanup_vectors, document.id)
    return DocumentDeleteRead(document_id=document.id, vector_cleanup_queued=True)


def queue_parse(db: Session, file_id: int, current_user, tasks: BackgroundTasks, *, retry: bool = False) -> ParseQueueRead:
    """将文件的关联文档加入解析队列。

    retry=False 时要求文件状态为已上传且文档解析状态为待解析（首次解析）；
    retry=True 时要求文件状态为解析失败，并重置文档解析状态与错误信息。
    校验通过后更新文件状态为待解析，记录审计日志并注册解析后台任务。

    Args:
        retry: 是否为失败重试。

    Returns:
        ParseQueueRead: 文件 ID、文档 ID 与当前文件状态。
    """
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
        if record.status != FileStatus.PARSE_FAILED:
            raise AppException("当前文件状态不允许重试", status_code=409)
        document.parse_status = DocumentParseStatus.PENDING
        document.error_msg = None
    else:
        if record.status != FileStatus.UPLOADED or document.parse_status != DocumentParseStatus.PENDING:
            raise AppException("当前文件状态不允许解析", status_code=409)
    record.status = FileStatus.PARSE_PENDING
    audit(db, action="file.parse_queued", target_type="file", target_id=record.id, operator_id=current_user.id, detail={"retry": retry, "document_id": document.id})
    db.commit()
    tasks.add_task(process_file, record.id)
    return ParseQueueRead(file_id=record.id, document_id=document.id, status=record.status)


def retry_failed(db: Session, knowledge_base_id: int, current_user, tasks: BackgroundTasks) -> BatchRetryRead:
    """批量重试知识库下所有解析失败的文档。

    查询该知识库内源文件仍存在且解析失败的未删除文档，逐一将其文件状态置为
    待解析、重置文档解析状态与错误信息，并记录审计日志。提交事务后为每个文件
    注册解析后台任务。

    Returns:
        BatchRetryRead: 已入队重试的文件 ID 列表。
    """
    knowledge_service.get_owned_active(db, knowledge_base_id, current_user)
    records = db.execute(select(FileRecord, Document).join(Document, Document.file_id == FileRecord.id).where(Document.knowledge_base_id == knowledge_base_id, FileRecord.status == FileStatus.PARSE_FAILED, FileRecord.storage_status == FileStorageStatus.PRESENT, Document.deleted_at.is_(None))).all()
    queued = []
    for record, document in records:
        record.status = FileStatus.PARSE_PENDING
        document.parse_status = DocumentParseStatus.PENDING
        document.error_msg = None
        audit(db, action="file.parse_queued", target_type="file", target_id=record.id, operator_id=current_user.id, detail={"retry": True})
        queued.append(record.id)
    db.commit()
    for file_id in queued:
        tasks.add_task(process_file, file_id)
    return BatchRetryRead(queued_file_ids=queued)
