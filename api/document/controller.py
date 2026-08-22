from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from api.document import service
from api.document.schema import (
    DocumentCreateRequest,
    DocumentListRequest,
    DocumentRead,
    DocumentStatusUpdateRequest,
)
from common.dependencies import get_current_user
from common.response import ApiResponse, success_response
from core.db import get_db

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/create", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[DocumentRead]
)
def create_document(
    payload: DocumentCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    document = service.create_document(db, payload, current_user)
    return success_response(
        DocumentRead.model_validate(document).model_dump(mode="json"), message="文档创建成功"
    )


@router.post("/status", response_model=ApiResponse[DocumentRead])
def update_document_status(
    payload: DocumentStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    document = service.update_document_status(db, payload.document_id, payload, current_user)
    return success_response(
        DocumentRead.model_validate(document).model_dump(mode="json"), message="文档状态更新成功"
    )


@router.post("/list", response_model=ApiResponse[list[DocumentRead]])
def list_documents(
    payload: DocumentListRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    documents = [
        DocumentRead.model_validate(item).model_dump(mode="json")
        for item in service.list_documents_by_knowledge_base(
            db, payload.knowledge_base_id, current_user
        )
    ]
    return success_response(documents, message="文档列表获取成功")
