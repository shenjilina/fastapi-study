"""文档模块控制器。

职责：仅处理路由接收、参数校验、统一响应、依赖注入，无任何业务、DB、RAG 逻辑。
路由说明：知识库 CRUD 路由已迁移至 api/knowledge/controller.py，
此处仅保留文档操作路由（含以 /knowledge-bases/ 为前缀的文档嵌套路由）。
"""

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from api.document import service
from api.document.schema import (
    DocumentCreateRequest,
    DocumentDeleteResponse,
    DocumentListRequest,
    DocumentRead,
    DocumentStatusUpdateRequest,
    DocumentUploadResponse,
)
from common.dependencies import get_current_user
from common.response import ApiResponse, success_response
from core.db import get_db

router = APIRouter(tags=["documents"])


@router.post(
    "/documents", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[DocumentRead]
)
def create_document(
    payload: DocumentCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """创建文档接口。"""
    document = service.create_document(db, payload, current_user)
    return success_response(
        DocumentRead.model_validate(document).model_dump(mode="json"),
        message="文档创建成功",
    )


@router.patch(
    "/documents/{document_id}/status",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[DocumentRead],
)
def update_document_status(
    document_id: int,
    payload: DocumentStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """更新文档解析状态接口。"""
    document = service.update_document_status(db, document_id, payload, current_user)
    return success_response(
        DocumentRead.model_validate(document).model_dump(mode="json"),
        message="文档状态更新成功",
    )


@router.post(
    "/knowledge-bases/documents/list",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[list[DocumentRead]],
)
def list_documents_by_knowledge_base(
    payload: DocumentListRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """查询知识库文档列表接口。"""
    documents = [
        DocumentRead.model_validate(item).model_dump(mode="json")
        for item in service.list_documents_by_knowledge_base(
            db, payload.knowledge_base_id, current_user
        )
    ]
    return success_response(documents, message="文档列表获取成功")


@router.post(
    "/knowledge-bases/documents/upload/{knowledge_base_id}",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[DocumentUploadResponse],
)
async def upload_document(
    knowledge_base_id: int,
    file: UploadFile = File(..., description="上传的文件，支持 txt / pdf"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """文件上传接口：校验 -> 去重 -> 解析 -> 切片 -> 向量入库 -> 存元数据。"""
    result = service.upload_document(db, knowledge_base_id, file, current_user)
    document_data = DocumentRead.model_validate(result["document"]).model_dump(mode="json")
    return success_response(
        {
            "document": document_data,
            "vector_ids": result["vector_ids"],
            "chunk_count": result["chunk_count"],
        },
        message="文档上传成功",
    )


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[DocumentDeleteResponse],
)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """删除文档接口：同时删除向量数据和数据库记录。"""
    result = service.delete_document(db, document_id, current_user)
    return success_response(
        DocumentDeleteResponse(
            document_id=result["document_id"],
            filename=result["filename"],
            deleted=result["deleted"],
        ).model_dump(mode="json"),
        message="文档删除成功",
    )
