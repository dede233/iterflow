"""Resolve temporary editor references within the requirement write transaction."""

import base64
import binascii

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.entities import AttachmentRelation
from app.repositories.file_repository import FileRepository
from app.services.file_service import FileService
from app.services.rich_text import IMAGE_REFERENCE

IMAGE_ENTITY = "REQUIREMENT_IMAGE"
EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
MIB = 1024 * 1024


def bind_images(
    db: Session,
    requirement_id: int,
    actor_id: int,
    description: str,
    description_format: str,
    uploads: dict[str, str],
    *,
    entity_type: str = IMAGE_ENTITY,
) -> str:
    refs = set(IMAGE_REFERENCE.findall(description)) if description_format == "HTML" else set()
    if len(refs) > 12 or {key for key in refs if key.startswith("local-")} != set(uploads):
        raise AppError(42265, "内容最多支持 12 张图片。请重新选择未成功载入的图片", 422)
    if not refs:
        return description
    repository = FileRepository(db)
    resolved = {}
    total = 0
    for key in sorted(refs):
        if key not in uploads:
            if not repository.get_attached_to_entity(int(key), entity_type, requirement_id):
                raise AppError(42265, "图片不属于此内容。请重新插入", 422)
            continue
        header, _, encoded = uploads[key].partition(",")
        mime = header.removeprefix("data:").removesuffix(";base64")
        if mime not in EXTENSIONS or header != f"data:{mime};base64":
            raise AppError(42265, "仅支持 PNG、JPEG 和 WebP 图片", 422)
        if len(encoded) > ((4 * MIB + 2) // 3) * 4:
            raise AppError(42265, "单张图片不能超过 4 MiB", 422)
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise AppError(42265, "图片数据无效。请重新选择", 422) from exc
        total += len(content)
        if len(content) > 4 * MIB or total > 8 * MIB:
            raise AppError(42265, "单张图片限 4 MiB。新图片合计限 8 MiB", 422)
        item = FileService(db).store_in_transaction(
            content, f"图片.{EXTENSIONS[mime]}", mime, actor_id
        )
        db.add(
            AttachmentRelation(entity_type=entity_type, entity_id=requirement_id, file_id=item.id)
        )
        resolved[key] = str(item.id)
    return IMAGE_REFERENCE.sub(
        lambda m: f'<img data-file-id="{resolved.get(m[1], m[1])}">', description
    )
