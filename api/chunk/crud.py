from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.chunk.model import Chunk


def create_chunks(
    db: Session, document_id: int, contents: list[str], vector_ids: list[str]
) -> list[Chunk]:
    rows = [
        Chunk(document_id=document_id, chunk_index=index, content=content, vector_id=vector_id)
        for index, (content, vector_id) in enumerate(zip(contents, vector_ids, strict=True))
    ]
    db.add_all(rows)
    db.flush()
    return rows


def soft_delete_chunks(db: Session, document_id: int) -> int:
    rows = list(
        db.scalars(
            select(Chunk).where(Chunk.document_id == document_id, Chunk.deleted_at.is_(None))
        )
    )
    now = datetime.now(timezone.utc)
    for row in rows:
        row.deleted_at = now
    db.flush()
    return len(rows)
