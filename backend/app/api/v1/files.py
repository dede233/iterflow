import hashlib
from uuid import uuid4

import boto3
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AppError
from app.models.entities import FileObject, User

router = APIRouter(prefix="/files", tags=["files"])
settings = get_settings()
ALLOWED_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
MAX_SIZE = 50 * 1024 * 1024


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key.get_secret_value(),
    )


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(current_user),
):
    content = await file.read(MAX_SIZE + 1)
    if len(content) > MAX_SIZE:
        raise AppError(42220, "单文件不能超过50MB", 422)
    if file.content_type not in ALLOWED_TYPES:
        raise AppError(42221, "不支持的文件类型", 422)
    digest = hashlib.sha256(content).hexdigest()
    key = f"uploads/{uuid4().hex}/{file.filename}"
    s3_client().put_object(
        Bucket=settings.minio_bucket,
        Key=key,
        Body=content,
        ContentType=file.content_type,
    )
    item = FileObject(
        storage_key=key,
        file_name=file.filename or "file",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        sha256=digest,
        created_by=current.id,
        updated_by=current.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
