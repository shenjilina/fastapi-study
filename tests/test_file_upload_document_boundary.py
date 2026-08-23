from io import BytesIO

from fastapi import BackgroundTasks, UploadFile
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api.document import service as document_service
from api.document.model import Document
from api.document.schema import DocumentCreateRequest
from api.files import service as file_service
from api.files.enums import FileStatus
from api.files.model import FileRecord
from api.knowledge.crud import create_knowledge_base
from api.user.crud import create_user
from config.settings import Settings
from core.db import Base, load_all_models


def build_session() -> Session:
    load_all_models()
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_upload_only_creates_file_record(tmp_path, monkeypatch) -> None:
    db = build_session()
    user = create_user(
        db, username="upload-owner", email="upload@example.com", hashed_password="hash"
    )
    db.commit()
    monkeypatch.setattr(
        file_service, "get_settings", lambda: Settings(file_storage_dir=str(tmp_path))
    )
    upload = UploadFile(filename="notes.txt", file=BytesIO(b"file content"))

    result = file_service.upload_many(db, [upload], user)

    assert result[0].accepted is True
    record = db.scalar(select(FileRecord))
    assert record is not None
    assert result[0].file_id == record.id
    assert record.status == FileStatus.UPLOADED
    assert db.scalar(select(Document).where(Document.file_id == record.id)) is None

    duplicate = UploadFile(filename="notes-copy.txt", file=BytesIO(b"file content"))
    duplicate_result = file_service.upload_many(db, [duplicate], user)

    assert duplicate_result[0].accepted is False
    assert duplicate_result[0].file_id == record.id


def test_document_create_is_required_before_parsing(tmp_path) -> None:
    db = build_session()
    user = create_user(
        db, username="parse-owner", email="parse@example.com", hashed_password="hash"
    )
    knowledge_base = create_knowledge_base(db, owner_id=user.id, name="Parse KB")
    db.add(
        FileRecord(
            owner_id=user.id,
            filename="notes.txt",
            storage_path=str(tmp_path / "notes.txt"),
            file_md5="a" * 32,
            status=FileStatus.UPLOADED,
        )
    )
    db.commit()
    record = db.scalar(select(FileRecord))
    assert record is not None
    created = document_service.create(
        db,
        DocumentCreateRequest(
            file_id=record.id,
            knowledge_base_id=knowledge_base.id,
            title="Notes",
            description="Test document",
        ),
        user,
    )
    document = db.scalar(select(Document).where(Document.file_id == record.id))
    assert document is not None
    assert created.id == document.id
    assert document.knowledge_base_id == knowledge_base.id
    assert record.status == FileStatus.UPLOADED

    tasks = BackgroundTasks()
    result = document_service.queue_parse(db, record.id, user, tasks)

    assert result.document_id == document.id
    assert record.status == FileStatus.PARSE_PENDING
    assert len(tasks.tasks) == 1
