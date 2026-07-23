from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from api.document.crud import (
    create_document,
    list_documents_by_knowledge_base,
    update_document_status,
)
from api.document.enums import DocumentParseStatus
from api.document.model import Document
from api.knowledge.crud import (
    create_knowledge_base,
    list_knowledge_bases_by_owner,
)
from api.knowledge.enums import KnowledgeBaseStatus
from api.knowledge.model import KnowledgeBase
from api.rag.crud import create_conversation_record, list_conversations_by_knowledge_base
from api.rag.enums import ConversationRecordStatus
from api.rag.model import ConversationRecord
from api.user.crud import create_user, get_user_by_username, list_users
from api.user.model import User
from core.db import Base, load_all_models


def build_test_session() -> Session:
    """为 Day2 学习验证创建独立的内存数据库会话。"""
    load_all_models()
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    return testing_session()


def test_day2_models_relationships_and_crud_flow() -> None:
    """验证 Day2 的核心表结构、关系映射和 CRUD 流程。"""
    db = build_test_session()
    try:
        user = create_user(
            db,
            username="alice",
            email="alice@example.com",
            hashed_password="hashed_password",
        )
        assert user.id == 1
        assert get_user_by_username(db, "alice") is not None
        assert len(list_users(db)) == 1

        knowledge_base = create_knowledge_base(
            db,
            owner_id=user.id,
            name="FastAPI Notes",
            description="Day2 练习知识库",
            status=KnowledgeBaseStatus.ACTIVE,
        )
        assert knowledge_base.owner_id == user.id
        assert len(list_knowledge_bases_by_owner(db, user.id)) == 1

        document = create_document(
            db,
            knowledge_base_id=knowledge_base.id,
            filename="notes.txt",
            file_type="txt",
            file_size=1024,
            file_md5="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        assert document.parse_status == DocumentParseStatus.PENDING

        updated_document = update_document_status(
            db,
            document_id=document.id,
            parse_status=DocumentParseStatus.SUCCESS,
            chunk_count=4,
        )
        assert updated_document is not None
        assert updated_document.parse_status == DocumentParseStatus.SUCCESS
        assert updated_document.chunk_count == 4
        assert len(list_documents_by_knowledge_base(db, knowledge_base.id)) == 1

        conversation = create_conversation_record(
            db,
            user_id=user.id,
            knowledge_base_id=knowledge_base.id,
            question="今天学到了什么？",
            answer="学会了用户、知识库、文档和问答记录表之间的关系。",
            source_document_ids=str(document.id),
            status=ConversationRecordStatus.GENERATED,
        )
        assert conversation.id == 1
        assert len(list_conversations_by_knowledge_base(db, knowledge_base.id)) == 1

        # 直接查表，确认三层关系都已经正确落库。
        assert db.scalar(select(User).where(User.id == user.id)) is not None
        assert db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base.id)) is not None
        assert db.scalar(select(Document).where(Document.id == document.id)) is not None
        assert db.scalar(select(ConversationRecord).where(ConversationRecord.id == conversation.id)) is not None
    finally:
        db.close()


def test_day2_enum_defaults_are_applied() -> None:
    """验证 Day2 模型中的默认状态值能正常生效。"""
    db = build_test_session()
    try:
        user = create_user(
            db,
            username="bob",
            email="bob@example.com",
            hashed_password="hashed_password",
        )
        knowledge_base = create_knowledge_base(
            db,
            owner_id=user.id,
            name="Default Status KB",
        )
        document = create_document(
            db,
            knowledge_base_id=knowledge_base.id,
            filename="defaults.pdf",
            file_type="pdf",
            file_size=2048,
            file_md5="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )
        conversation = create_conversation_record(
            db,
            user_id=user.id,
            knowledge_base_id=knowledge_base.id,
            question="默认状态是什么？",
            answer="知识库默认启用，文档默认待解析，问答默认已生成。",
        )

        assert knowledge_base.status == KnowledgeBaseStatus.ACTIVE
        assert document.parse_status == DocumentParseStatus.PENDING
        assert conversation.status == ConversationRecordStatus.GENERATED
    finally:
        db.close()
