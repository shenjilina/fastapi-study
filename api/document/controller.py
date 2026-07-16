"""知识库和文档模块控制器。"""

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from api.document import service
from api.document.schema import (
    DocumentCreateRequest,
    DocumentDeleteResponse,
    DocumentRead,
    DocumentStatusUpdateRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseRead,
)
from common.response import success_response
from core.db import get_db

router = APIRouter(tags=["documents"])


@router.post("/knowledge-bases", status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """创建知识库接口。"""
    knowledge_base = service.create_knowledge_base(db, payload)
    return success_response(
        KnowledgeBaseRead.model_validate(knowledge_base).model_dump(mode="json"),
        message="知识库创建成功",
    )


@router.get("/knowledge-bases", status_code=status.HTTP_200_OK)
def list_knowledge_bases(
    owner_id: int = Query(gt=0, description="用户 ID"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """按用户查询知识库列表接口。"""
    knowledge_bases = [
        KnowledgeBaseRead.model_validate(item).model_dump(mode="json")
        for item in service.list_knowledge_bases(db, owner_id)
    ]
    return success_response(knowledge_bases, message="知识库列表获取成功")


@router.get("/knowledge-bases/{knowledge_base_id}", status_code=status.HTTP_200_OK)
def get_knowledge_base_detail(
    knowledge_base_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """查询知识库详情接口。"""
    knowledge_base = service.get_knowledge_base_detail(db, knowledge_base_id)
    return success_response(
        KnowledgeBaseRead.model_validate(knowledge_base).model_dump(mode="json"),
        message="知识库详情获取成功",
    )


@router.post("/documents", status_code=status.HTTP_201_CREATED)
def create_document(
    payload: DocumentCreateRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """创建文档接口。"""
    document = service.create_document(db, payload)
    return success_response(
        DocumentRead.model_validate(document).model_dump(mode="json"),
        message="文档创建成功",
    )


@router.patch("/documents/{document_id}/status", status_code=status.HTTP_200_OK)
def update_document_status(
    document_id: int,
    payload: DocumentStatusUpdateRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """更新文档解析状态接口。"""
    document = service.update_document_status(db, document_id, payload)
    return success_response(
        DocumentRead.model_validate(document).model_dump(mode="json"),
        message="文档状态更新成功",
    )


@router.get("/knowledge-bases/{knowledge_base_id}/documents", status_code=status.HTTP_200_OK)
def list_documents_by_knowledge_base(
    knowledge_base_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """查询知识库文档列表接口。"""
    documents = [
        DocumentRead.model_validate(item).model_dump(mode="json")
        for item in service.list_documents_by_knowledge_base(db, knowledge_base_id)
    ]
    return success_response(documents, message="文档列表获取成功")


@router.post(
    "/knowledge-bases/documents/upload/{knowledge_base_id}",
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    knowledge_base_id: int,
    file: UploadFile = File(..., description="上传的文件，支持 txt / pdf"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """文件上传接口：校验 -> 去重 -> 解析 -> 切片 -> 向量入库 -> 存元数据。"""
    result = service.upload_document(db, knowledge_base_id, file)
    document_data = DocumentRead.model_validate(result["document"]).model_dump(mode="json")
    return success_response(
        {
            "document": document_data,
            "vector_ids": result["vector_ids"],
            "chunk_count": result["chunk_count"],
        },
        message="文档上传成功",
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """删除文档接口：同时删除向量数据和数据库记录。"""
    result = service.delete_document(db, document_id)
    return success_response(
        DocumentDeleteResponse(
            document_id=result["document_id"],
            filename=result["filename"],
            deleted=result["deleted"],
        ).model_dump(mode="json"),
        message="文档删除成功",
    )
