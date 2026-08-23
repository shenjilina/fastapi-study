from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from api.knowledge import service
from api.knowledge.schema import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseDeleteRequest,
    KnowledgeBaseIdRequest,
    KnowledgeBaseListRequest,
    KnowledgeBasePageRead,
    KnowledgeBaseRead,
    KnowledgeBaseStatusUpdateRequest,
    KnowledgeBaseSummaryRead,
    KnowledgeBaseUpdateBody,
)
from common.dependencies import get_current_user
from common.response import ApiResponse, success_response
from core.db import get_db

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge"])


@router.post(
    "/create", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[KnowledgeBaseRead]
)
def create(
    payload: KnowledgeBaseCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """创建当前用户的知识库，默认状态为正常可用。"""
    return success_response(service.create(db, payload, current_user), "知识库创建成功")


@router.post("/list", response_model=ApiResponse[KnowledgeBasePageRead])
def list_items(
    payload: KnowledgeBaseListRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """按名称和状态分页查询当前用户可见的知识库。"""
    items, total = service.list_items(
        db,
        current_user,
        query=payload.query,
        status=payload.status,
        page=payload.page,
        page_size=payload.page_size,
    )
    return success_response(
        KnowledgeBasePageRead(
            items=items, total=total, page=payload.page, page_size=payload.page_size
        )
    )


@router.post("/detail", response_model=ApiResponse[KnowledgeBaseRead])
def detail(
    payload: KnowledgeBaseIdRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """查询指定知识库详情，公开知识库允许其他登录用户读取。"""
    return success_response(
        KnowledgeBaseRead.model_validate(
            service.get_readable(db, payload.knowledge_base_id, current_user)
        )
    )


@router.patch("/update", response_model=ApiResponse[KnowledgeBaseRead])
def update(
    payload: KnowledgeBaseUpdateBody,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """修改当前用户知识库的名称、描述或可见性。"""
    return success_response(service.update(db, payload.knowledge_base_id, payload, current_user))


@router.patch("/status", response_model=ApiResponse[KnowledgeBaseRead])
def update_status(
    payload: KnowledgeBaseStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """启用、禁用或归档当前用户的知识库。"""
    return success_response(
        service.change_status(db, payload.knowledge_base_id, payload, current_user)
    )


@router.delete("/delete", response_model=ApiResponse[dict])
def delete(
    payload: KnowledgeBaseDeleteRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """按确认名称软删除知识库，并保留关联审计数据。"""
    service.delete(db, payload.knowledge_base_id, payload, current_user)
    return success_response({"id": payload.knowledge_base_id, "deleted": True})


@router.post("/summary", response_model=ApiResponse[KnowledgeBaseSummaryRead])
def summary(
    payload: KnowledgeBaseIdRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """查询知识库的文件、有效文档和解析失败统计。"""
    return success_response(service.summary(db, payload.knowledge_base_id, current_user))
