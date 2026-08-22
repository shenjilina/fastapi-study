import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from api.files import crud
from api.files.enums import FileStatus
from api.files.schema import FileUploadRead
from api.knowledge import crud as knowledge_crud
from common.dependencies import ensure_owner
from config.settings import get_settings
from core.exceptions import AppException


def _storage_dir() -> Path:
    path = Path(get_settings().file_storage_dir).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _owned_knowledge_base(db: Session, knowledge_base_id: int, current_user):
    knowledge_base = knowledge_crud.get_knowledge_base_by_id(db, knowledge_base_id)
    if knowledge_base is None:
        raise AppException("知识库不存在", status_code=404)
    ensure_owner(knowledge_base.owner_id, current_user, resource="知识库")
    return knowledge_base


def upload_file(
    db: Session, knowledge_base_id: int, upload: UploadFile, current_user
) -> FileUploadRead:
    _owned_knowledge_base(db, knowledge_base_id, current_user)
    settings = get_settings()
    original = upload.filename or "unknown"
    suffix = Path(original).suffix.lower().lstrip(".")
    if suffix not in settings.allowed_file_extensions:
        raise AppException(f"不支持的文件类型: .{suffix}", status_code=400)

    stored_name = f"{uuid4().hex}.{suffix}"
    destination = _storage_dir() / stored_name
    digest = hashlib.md5()
    size = 0
    record = None
    try:
        with destination.open("wb") as output:
            while chunk := upload.file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_size_mb * 1024 * 1024:
                    raise AppException("文件大小超过限制", status_code=413)
                digest.update(chunk)
                output.write(chunk)
        if size == 0:
            raise AppException("文件内容为空", status_code=422)

        file_md5 = digest.hexdigest()
        duplicate = crud.find_duplicate(db, file_md5)
        if duplicate is not None:
            raise AppException("系统中已存在相同 MD5 的文件", status_code=409)

        record = crud.create_file(
            db,
            owner_id=current_user.id,
            knowledge_base_id=knowledge_base_id,
            filename=original,
            stored_filename=stored_name,
            storage_path=str(destination),
            file_type=suffix or None,
            mime_type=upload.content_type,
            file_size=size,
            file_md5=file_md5,
            status=FileStatus.UPLOADING,
        )
        record.status = FileStatus.UPLOADED
        db.commit()
        return FileUploadRead(
            file_id=record.id,
            filename=record.filename,
            stored_filename=record.stored_filename,
            file_size=record.file_size,
            file_md5=record.file_md5,
            mime_type=record.mime_type,
            status=record.status,
            created_at=record.created_at,
        )
    except AppException:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    except IntegrityError as exc:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise AppException("文件已存在，请勿重复上传", status_code=409) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise AppException("文件记录创建失败，请稍后重试", status_code=500) from exc


def delete_file(db: Session, file_id: int, current_user) -> dict:
    record = crud.get_file(db, file_id)
    if record is None or record.status == FileStatus.PHYSICAL_DELETED:
        raise AppException("文件不存在", status_code=404)
    ensure_owner(record.owner_id, current_user, resource="文件")

    if record.document is not None and record.document.deleted_at is None:
        from api.document.service import delete_document

        delete_document(db, record.document.id, current_user)
    if record.storage_path:
        Path(record.storage_path).unlink(missing_ok=True)
    record.stored_filename = None
    record.storage_path = None
    record.status = FileStatus.PHYSICAL_DELETED
    db.commit()
    return {"file_id": record.id, "status": record.status, "deleted": True}
