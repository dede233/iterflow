from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.entities import User
from app.repositories.user_repository import UserRepository
from app.schemas.file import FileExistsOut, FileOut
from app.services.file_service import MAX_UPLOAD_SIZE, FileService, validate_upload

router = APIRouter(prefix="/files", tags=["files"])


def _safe_content_disposition(original_name: str) -> str:
    cleaned = original_name.replace("\r", "").replace("\n", "").replace("\x00", "") or "file"
    return f"attachment; filename*=UTF-8''{quote(cleaned, safe='')}"


@router.post("", response_model=FileOut)
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.file.upload")),
) -> FileOut:
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    original_name = file.filename or "file"
    validate_upload(size=len(content), mime_type=file.content_type, original_name=original_name)
    # validate_upload has already rejected a None/unsupported content type.
    item = FileService(db).upload(
        content=content,
        original_name=original_name,
        mime_type=file.content_type or "application/octet-stream",
        actor=current,
    )
    return FileOut.model_validate(item)


@router.get("/{file_id}/download")
def download_file(
    file_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.file.download")),
) -> Response:
    scope = UserRepository(db).data_scope(current.id)
    service = FileService(db)
    signed_url = service.generate_download_url(file_id, current, scope)
    if signed_url:
        return RedirectResponse(signed_url, status_code=307)

    item, stream = service.open(file_id, current, scope)
    background_tasks.add_task(stream.close)
    return StreamingResponse(
        stream,
        media_type=item.mime_type,
        headers={"Content-Disposition": _safe_content_disposition(item.original_name)},
        background=background_tasks,
    )


@router.get("/{file_id}/exists", response_model=FileExistsOut)
def file_exists(
    file_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.file.download")),
) -> FileExistsOut:
    scope = UserRepository(db).data_scope(current.id)
    item, exists = FileService(db).exists(file_id, current, scope)
    return FileExistsOut(file_id=item.id, exists=exists)


@router.delete("/{file_id}", status_code=204)
def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.file.delete")),
) -> Response:
    scope = UserRepository(db).data_scope(current.id)
    FileService(db).delete(file_id, current, scope)
    return Response(status_code=204)
