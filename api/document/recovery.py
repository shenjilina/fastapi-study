from sqlalchemy import update

from api.document.enums import DocumentParseStatus
from api.document.model import Document
from api.files.enums import FileStatus
from api.files.model import FileRecord
from core.db import SessionLocal


def reset_interrupted_parses() -> None:
    """Make in-process jobs retriable after an application restart."""
    db = SessionLocal()
    try:
        db.execute(
            update(FileRecord)
            .where(FileRecord.status.in_([FileStatus.PARSE_PENDING, FileStatus.PARSING]))
            .values(status=FileStatus.UPLOADED)
        )
        db.execute(
            update(Document)
            .where(
                Document.deleted_at.is_(None),
                Document.parse_status.in_(
                    [DocumentParseStatus.PENDING, DocumentParseStatus.PARSING]
                ),
            )
            .values(parse_status=DocumentParseStatus.PENDING)
        )
        db.commit()
    finally:
        db.close()
