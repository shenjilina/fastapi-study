from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from api.files import service
from api.files.schema import FileDeleteRequest, FileUploadRead
from common.dependencies import get_current_user
from common.response import ApiResponse, success_response
from core.db import get_db

router = APIRouter(prefix="/files", tags=["files"])


@router.post(
    "/upload", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[FileUploadRead]
)
async def upload_file(
    knowledge_base_id: int = Form(..., description="知识库 ID"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = service.upload_file(db, knowledge_base_id, file, current_user)
    return success_response(result.model_dump(mode="json"), message="文件上传成功")


@router.post("/delete", response_model=ApiResponse[dict])
def delete_file(
    payload: FileDeleteRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return success_response(
        service.delete_file(db, payload.file_id, current_user), message="文件删除成功"
    )
