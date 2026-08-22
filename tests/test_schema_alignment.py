from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from api.chunk.model import Chunk
from api.document.enums import DocumentParseStatus
from api.document.model import Document
from api.files.enums import FileStatus
from api.files.model import FileRecord
from api.knowledge.crud import (
    create_knowledge_base,
    get_knowledge_base_by_id,
    list_knowledge_bases_by_owner,
)
from api.knowledge.enums import KnowledgeBaseVisibility
from api.user.crud import create_user
from core.db import Base, load_all_models


def build_session() -> Session:
    load_all_models()
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_target_models_have_expected_columns_and_states() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    load_all_models()
    Base.metadata.create_all(engine)
    inspector = inspect(engine)

    document_columns = {column["name"] for column in inspector.get_columns("documents")}
    assert "knowledge_base_id" not in document_columns
    assert {"file_id", "error_msg", "vector_cleaned", "file_size", "deleted_at"} <= document_columns
    assert {"document_id", "chunk_index", "content", "vector_id"} <= {
        column["name"] for column in inspector.get_columns("chunks")
    }
    assert FileStatus.PHYSICAL_DELETED.value == "physical_deleted"
    assert DocumentParseStatus.PARSING.value == "parsing"


def test_knowledge_base_visibility_and_soft_delete_filter() -> None:
    db = build_session()
    user = create_user(
        db,
        username="schema-user",
        email="schema@example.com",
        hashed_password="hashed",
    )
    active = create_knowledge_base(
        db,
        owner_id=user.id,
        name="Visible KB",
        visibility=KnowledgeBaseVisibility.PUBLIC,
    )
    deleted = create_knowledge_base(db, owner_id=user.id, name="Deleted KB")
    deleted.deleted_at = datetime.now(timezone.utc)
    db.commit()

    assert active.visibility == KnowledgeBaseVisibility.PUBLIC
    assert get_knowledge_base_by_id(db, deleted.id) is None
    assert [item.id for item in list_knowledge_bases_by_owner(db, user.id)] == [active.id]


def test_document_is_reached_through_file() -> None:
    db = build_session()
    user = create_user(
        db,
        username="file-user",
        email="file@example.com",
        hashed_password="hashed",
    )
    knowledge_base = create_knowledge_base(db, owner_id=user.id, name="File KB")
    record = FileRecord(
        owner_id=user.id,
        knowledge_base_id=knowledge_base.id,
        filename="notes.txt",
        stored_filename="stored-notes.txt",
        storage_path="uploads/stored-notes.txt",
        file_type="txt",
        file_size=10,
        file_md5="a" * 32,
        status=FileStatus.UPLOADED,
    )
    document = Document(file=record, title="Notes", file_size=10)
    db.add(document)
    db.commit()
    chunk = Chunk(document_id=document.id, chunk_index=0, content="hello")
    db.add(chunk)
    db.commit()

    assert document.file.knowledge_base_id == knowledge_base.id
    assert not hasattr(document, "knowledge_base_id")
    assert document.chunks[0].content == "hello"
