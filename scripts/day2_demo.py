"""Day2 端到端练习脚本：演示模型关系和基础 CRUD。"""

from uuid import uuid4

from api.document.crud import create_document, create_knowledge_base, update_document_status
from api.document.enums import DocumentParseStatus
from api.rag.crud import create_conversation_record
from api.user.crud import create_user
from core.db import SessionLocal, create_all_tables, load_all_models


def main() -> None:
    """依次创建用户、知识库、文档和问答记录，帮助理解 Day2 数据流。"""
    load_all_models()
    create_all_tables()
    suffix = uuid4().hex[:8]

    with SessionLocal() as db:
        user = create_user(
            db,
            username=f"day2_student_{suffix}",
            email=f"day2_student_{suffix}@example.com",
            hashed_password="demo_hashed_password",
        )

        knowledge_base = create_knowledge_base(
            db,
            owner_id=user.id,
            name="FastAPI Day2 Knowledge Base",
            description="用于练习数据库模型关系。",
        )

        document = create_document(
            db,
            knowledge_base_id=knowledge_base.id,
            filename="fastapi_day2_notes.txt",
            file_type="txt",
            file_size=2048,
            file_md5="1234567890abcdef1234567890abcdef",
        )

        update_document_status(
            db,
            document_id=document.id,
            parse_status=DocumentParseStatus.SUCCESS,
            chunk_count=6,
        )

        conversation = create_conversation_record(
            db,
            user_id=user.id,
            knowledge_base_id=knowledge_base.id,
            question="Day2 学了什么？",
            answer="完成了用户、知识库、文档、问答记录四张核心表的建模。",
            source_document_ids=str(document.id),
        )

        print(f"User created: {user.id} / {user.username}")
        print(f"Knowledge base created: {knowledge_base.id} / {knowledge_base.name}")
        print(f"Document created: {document.id} / {document.filename}")
        print(f"Conversation created: {conversation.id} / {conversation.status}")


if __name__ == "__main__":
    main()
