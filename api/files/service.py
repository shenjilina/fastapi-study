import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.audit.service import record as audit
from api.files.enums import FileStatus, FileStorageStatus
from api.files.model import FileRecord
from api.files.schema import FilePageRead, FileRead, FileUploadResult, SourceDeleteRead
from config.settings import get_settings
from common.dependencies import ensure_owner
from core.exceptions import AppException


def _read(record: FileRecord) -> FileRead:
    return FileRead(
        id=record.id,
        owner_id=record.owner_id,
        filename=record.filename,
        file_type=record.file_type,
        mime_type=record.mime_type,
        file_size=record.file_size,
        file_md5=record.file_md5,
        status=record.status,
        storage_status=record.storage_status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _owned_file(db: Session, file_id: int, current_user) -> FileRecord:
    record = db.scalar(select(FileRecord).where(FileRecord.id == file_id))
    if record is None:
        raise AppException("文件不存在", status_code=404)
    ensure_owner(record.owner_id, current_user, resource="文件")
    return record


def upload_many(
    db: Session,
    uploads: list[UploadFile],
    current_user,
) -> list[FileUploadResult]:
    settings = get_settings()
    root = Path(settings.file_storage_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    results = []
    for upload in uploads:
        name = upload.filename or "unknown"
        suffix = Path(name).suffix.lower().lstrip(".")
        if suffix == "doc" or suffix not in settings.allowed_file_extensions:
            results.append(
                FileUploadResult(filename=name, accepted=False, error="不支持的文件格式")
            )
            continue
        destination = root / f"{uuid4().hex}.{suffix}"
        digest, size = hashlib.md5(), 0
        try:
            with destination.open("wb") as output:
                while data := upload.file.read(1024 * 1024):
                    size += len(data)
                    if size > settings.max_upload_size_mb * 1024 * 1024:
                        raise AppException("文件大小超过限制", status_code=413)
                    digest.update(data)
                    output.write(data)
            if not size:
                raise AppException("文件内容为空", status_code=422)
            duplicate = db.scalar(
                select(FileRecord).where(
                    FileRecord.owner_id == current_user.id,
                    FileRecord.file_md5 == digest.hexdigest(),
                    FileRecord.storage_status == FileStorageStatus.PRESENT,
                )
            )
            if duplicate:
                destination.unlink(missing_ok=True)
                results.append(
                    FileUploadResult(
                        filename=name,
                        accepted=False,
                        file_id=duplicate.id,
                        error="文件已上传",
                    )
                )
                continue
            record = FileRecord(
                owner_id=current_user.id,
                filename=name,
                stored_filename=destination.name,
                storage_path=str(destination),
                file_type=suffix,
                mime_type=upload.content_type,
                file_size=size,
                file_md5=digest.hexdigest(),
                status=FileStatus.UPLOADED,
                storage_status=FileStorageStatus.PRESENT,
            )
            db.add(record)
            db.flush()
            audit(
                db,
                action="file.uploaded",
                target_type="file",
                target_id=record.id,
                operator_id=current_user.id,
            )
            db.commit()
            db.refresh(record)
            results.append(
                FileUploadResult(
                    filename=name,
                    accepted=True,
                    file_id=record.id,
                    file=_read(record),
                )
            )
        except AppException as exc:
            db.rollback()
            destination.unlink(missing_ok=True)
            results.append(FileUploadResult(filename=name, accepted=False, error=exc.message))
    return results


def list_items(
    db: Session,
    current_user,
    *,
    file_status: FileStatus | None,
    page: int,
    page_size: int,
) -> FilePageRead:
    stmt = select(FileRecord).where(FileRecord.owner_id == current_user.id)
    if file_status:
        stmt = stmt.where(FileRecord.status == file_status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(FileRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return FilePageRead(
        items=[_read(row) for row in rows], total=total, page=page, page_size=page_size
    )


def detail(db: Session, file_id: int, current_user) -> FileRead:
    record = db.scalar(select(FileRecord).where(FileRecord.id == file_id))
    if record is None:
        raise AppException("文件不存在", status_code=404)
    ensure_owner(record.owner_id, current_user, resource="文件")
    return _read(record)


def delete_source(db: Session, file_id: int, current_user) -> SourceDeleteRead:
    record = _owned_file(db, file_id, current_user)
    if record.status in {FileStatus.UPLOADING, FileStatus.PARSE_PENDING, FileStatus.PARSING}:
        raise AppException("文件正在处理中，不可删除源文件", status_code=409)
    if record.storage_status == FileStorageStatus.PHYSICAL_DELETED:
        raise AppException("源文件已删除", status_code=409)
    if record.storage_path:
        Path(record.storage_path).unlink(missing_ok=True)
    record.storage_path = None
    record.stored_filename = None
    record.storage_status = FileStorageStatus.PHYSICAL_DELETED
    audit(
        db,
        action="file.source_deleted",
        target_type="file",
        target_id=file_id,
        operator_id=current_user.id,
    )
    db.commit()
    return SourceDeleteRead(file_id=file_id, storage_status=record.storage_status)
