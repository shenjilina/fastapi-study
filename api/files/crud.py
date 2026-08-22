from sqlalchemy import select
from sqlalchemy.orm import Session

from api.files.model import FileRecord


def get_file(db: Session, file_id: int) -> FileRecord | None:
    return db.scalar(select(FileRecord).where(FileRecord.id == file_id))


def find_duplicate(db: Session, file_md5: str) -> FileRecord | None:
    return db.scalar(select(FileRecord).where(FileRecord.file_md5 == file_md5))


def create_file(db: Session, **values) -> FileRecord:
    record = FileRecord(**values)
    db.add(record)
    db.flush()
    db.refresh(record)
    return record
