from typing import Any

from sqlalchemy.orm import Session

from api.audit.model import AuditLog


def record(
    db: Session,
    *,
    action: str,
    target_type: str,
    target_id: int,
    operator_id: int | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        action=action,
        target_type=target_type,
        target_id=target_id,
        operator_id=operator_id,
        detail=detail or {},
    )
    db.add(entry)
    db.flush()
    return entry
