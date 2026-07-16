"""知识库和文档模块基础 CRUD 示例。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.document.enums import DocumentParseStatus
from api.document.model import Document, KnowledgeBase
from api.rag.enums import KnowledgeBaseStatus


def create_knowledge_base(
    db: Session,
    *,
    owner_id: int,
    name: str,
    description: str | None = None,
    status: KnowledgeBaseStatus = KnowledgeBaseStatus.ACTIVE,
) -> KnowledgeBase:
    """创建知识库。"""
    knowledge_base = KnowledgeBase(
        owner_id=owner_id,
        name=name,
        description=description,
        status=status,
    )
    db.add(knowledge_base)
    db.flush()
    db.refresh(knowledge_base)
    return knowledge_base


def get_knowledge_base_by_id(db: Session, knowledge_base_id: int) -> KnowledgeBase | None:
    """按主键查询知识库。"""
    return db.get(KnowledgeBase, knowledge_base_id)


def list_knowledge_bases_by_owner(db: Session, owner_id: int) -> list[KnowledgeBase]:
    """查询某个用户名下的全部知识库。"""
    statement = (
        select(KnowledgeBase)
        .where(KnowledgeBase.owner_id == owner_id)
        .order_by(KnowledgeBase.id.asc())
    )
    return list(db.scalars(statement))


def create_document(
    db: Session,
    *,
    knowledge_base_id: int,
    filename: str,
    file_type: str,
    file_size: int,
    file_md5: str,
    chunk_count: int = 0,
    parse_status: DocumentParseStatus = DocumentParseStatus.PENDING,
) -> Document:
    """创建文档元数据。"""
    document = Document(
        knowledge_base_id=knowledge_base_id,
        filename=filename,
        file_type=file_type,
        file_size=file_size,
        file_md5=file_md5,
        chunk_count=chunk_count,
        parse_status=parse_status,
    )
    db.add(document)
    db.flush()
    db.refresh(document)
    return document


def get_document_by_id(db: Session, document_id: int) -> Document | None:
    """按主键查询文档。"""
    return db.get(Document, document_id)


def get_document_by_md5(
    db: Session,
    *,
    knowledge_base_id: int,
    file_md5: str,
) -> Document | None:
    """按知识库和文件摘要查询文档，用于去重。"""
    statement = select(Document).where(
        Document.knowledge_base_id == knowledge_base_id,
        Document.file_md5 == file_md5,
    )
    return db.scalar(statement)


def list_documents_by_knowledge_base(db: Session, knowledge_base_id: int) -> list[Document]:
    """查询知识库下的全部文档。"""
    statement = (
        select(Document)
        .where(Document.knowledge_base_id == knowledge_base_id)
        .order_by(Document.id.asc())
    )
    return list(db.scalars(statement))


def update_document_status(
    db: Session,
    *,
    document_id: int,
    parse_status: DocumentParseStatus,
    chunk_count: int | None = None,
) -> Document | None:
    """更新文档解析状态。"""
    document = get_document_by_id(db, document_id)
    if document is None:
        return None

    document.parse_status = parse_status
    if chunk_count is not None:
        document.chunk_count = chunk_count

    db.flush()
    db.refresh(document)
    return document


def delete_document(db: Session, document_id: int) -> bool:
    """按主键删除文档元数据，返回是否删除成功。"""
    document = get_document_by_id(db, document_id)
    if document is None:
        return False
    db.delete(document)
    db.flush()
    return True
