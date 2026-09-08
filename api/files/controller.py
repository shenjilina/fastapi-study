from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from api.files import service
from api.files.schema import (
    FileIdRequest,
    FileListRequest,
    FilePageRead,
    FileRead,
    FileUploadResult,
    SourceDeleteRead,
)
from common.dependencies import get_current_user
from common.response import ApiResponse, success_response
from core.db import get_db

router = APIRouter(prefix="/files", tags=["files"])


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[list[FileUploadResult]],
)
def upload(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """上传一个或多个文件，仅保存文件元数据和服务器源文件。"""
    return success_response(service.upload_many(db, files, current_user), "文件上传成功")


@router.post("/list", response_model=ApiResponse[FilePageRead])
def list_items(
    payload: FileListRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    """按知识库和文件状态分页查询文件列表。"""
    return success_response(
        service.list_items(
            db,
            current_user,
            file_status=payload.file_status,
            page=payload.page,
            page_size=payload.page_size,
        )
    )


@router.post("/detail", response_model=ApiResponse[FileRead])
def detail(
    payload: FileIdRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    """查询单个文件的元数据和存储状态。"""
    return success_response(service.detail(db, payload.file_id, current_user))


@router.post("/delete-source", response_model=ApiResponse[SourceDeleteRead])
def delete_source(
    payload: FileIdRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    """删除服务器源文件并保留文件元数据和解析记录。"""
    return success_response(service.delete_source(db, payload.file_id, current_user))
