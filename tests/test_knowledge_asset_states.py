from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.document.enums import DocumentParseStatus
from api.document.model import Document
from api.files.enums import FileStatus, FileStorageStatus
from api.files.model import FileRecord
from api.knowledge.enums import KnowledgeBaseStatus, KnowledgeBaseVisibility
from api.knowledge.model import KnowledgeBase
from core.db import Base, load_all_models


def build_session() -> Session:
    load_all_models()
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_file_parse_and_storage_states_are_independent() -> None:
    assert FileStatus.SUCCESS.value == "SUCCESS"
    assert FileStorageStatus.PHYSICAL_DELETED.value == "PHYSICAL_DELETED"


def test_only_one_active_document_is_allowed_per_file() -> None:
    db = build_session()
    knowledge_base = KnowledgeBase(
        owner_id=1,
        name="KB",
        status=KnowledgeBaseStatus.ACTIVE,
        visibility=KnowledgeBaseVisibility.PRIVATE,
    )
    db.add(knowledge_base)
    db.flush()
    record = FileRecord(
        owner_id=1,
        filename="a.txt",
        file_md5="a" * 32,
        status=FileStatus.UPLOADED,
        storage_status=FileStorageStatus.PRESENT,
    )
    db.add(record)
    db.flush()
    db.add(
        Document(
            file_id=record.id,
            knowledge_base_id=knowledge_base.id,
            title="first",
            parse_status=DocumentParseStatus.PENDING,
        )
    )
    db.commit()
    db.add(
        Document(
            file_id=record.id,
            knowledge_base_id=knowledge_base.id,
            title="second",
            parse_status=DocumentParseStatus.PENDING,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    first = db.query(Document).filter_by(file_id=record.id).one()
    first.deleted_at = datetime.now(timezone.utc)
    db.commit()
    db.add(
        Document(
            file_id=record.id,
            knowledge_base_id=knowledge_base.id,
            title="replacement",
            parse_status=DocumentParseStatus.PENDING,
        )
    )
    db.commit()
    assert (
        db.query(Document)
        .filter(Document.file_id == record.id, Document.deleted_at.is_(None))
        .count()
        == 1
    )
