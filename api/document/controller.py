from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from api.document import service
from api.document.schema import (
    BatchRetryRead,
    ChunkListRequest,
    ChunkPageRead,
    DocumentCreateRequest,
    DocumentDeleteRead,
    DocumentIdRequest,
    DocumentListRequest,
    DocumentPageRead,
    DocumentRead,
    FileParseRequest,
    KnowledgeBaseIdRequest,
    ParseQueueRead,
)
from common.dependencies import get_current_user
from common.response import ApiResponse, success_response
from core.db import get_db

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/create", status_code=201, response_model=ApiResponse[DocumentRead])
def create(
    payload: DocumentCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """根据已上传文件创建待解析文档，不触发解析任务。"""
    return success_response(service.create(db, payload, current_user), "文档创建成功")


@router.post("/list", response_model=ApiResponse[DocumentPageRead])
def list_items(
    payload: DocumentListRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """按知识库和解析状态分页查询未软删除文档。"""
    return success_response(
        service.list_items(
            db,
            payload.knowledge_base_id,
            current_user,
            parse_status=payload.parse_status,
            page=payload.page,
            page_size=payload.page_size,
        )
    )


@router.post("/detail", response_model=ApiResponse[DocumentRead])
def detail(
    payload: DocumentIdRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """查询文档解析状态、切片数量和错误信息。"""
    return success_response(service.detail(db, payload.document_id, current_user))


@router.post("/delete", response_model=ApiResponse[DocumentDeleteRead])
def delete(
    payload: DocumentIdRequest,
    tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """软删除文档及其切片，并异步回收关联向量。"""
    return success_response(service.delete(db, payload.document_id, current_user, tasks))


@router.post("/chunks", response_model=ApiResponse[ChunkPageRead])
def chunks(
    payload: ChunkListRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    """分页预览解析成功文档的有效文本切片。"""
    return success_response(
        service.chunks(db, payload.document_id, current_user, payload.page, payload.page_size)
    )


@router.post("/retry", response_model=ApiResponse[BatchRetryRead])
def retry(
    payload: KnowledgeBaseIdRequest,
    tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """批量重新提交当前知识库中所有解析失败的文件。"""
    return success_response(
        service.retry_failed(db, payload.knowledge_base_id, current_user, tasks)
    )


@router.post("/parse", response_model=ApiResponse[ParseQueueRead])
def parse(
    payload: FileParseRequest,
    tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """提交已创建的待解析文档对应的文件解析任务。"""
    return success_response(
        service.queue_parse(db, payload.file_id, current_user, tasks, retry=payload.retry)
    )
