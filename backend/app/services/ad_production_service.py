import re
from base64 import b64encode
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from typing import BinaryIO, cast

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDenied
from app.domain.ad_production_permissions import (
    AD_PRODUCTION_PERMISSIONS,
    viewable_ad_production_kinds,
)
from app.models.entities import (
    AdProduction,
    AttachmentRelation,
    FileObject,
    Notification,
    User,
    utcnow,
)
from app.models.enums import AdProductionKind, AdProductionStatus, NotificationType
from app.repositories.ad_production_repository import (
    AD_PRODUCTION_ENTITY,
    ARCHIVED_AD_PRODUCTION_ENTITY,
    AdProductionRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.ad_production import (
    MAX_CONTENT_CHARACTERS,
    MAX_IMAGES,
    AdProductionContentFormat,
    AdProductionCreateForm,
    AdProductionDesignerOption,
    AdProductionForm,
    AdProductionOut,
    AdProductionPage,
    AdProductionStatusChange,
    AdProductionUpdateForm,
    validate_plain_content,
)
from app.schemas.file import AttachmentOut
from app.services.audit_service import AuditService
from app.services.file_service import FileService
from app.services.requirement_images import bind_images
from app.services.revision_conflict import revision_conflict_data
from app.services.rich_text import sanitize_editor_content

IMAGE_MEDIA_TYPES = ("image/png", "image/jpeg", "image/webp")
CONTENT_IMAGE_ENTITY = "AD_PRODUCTION_IMAGE"
MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_CONTENT_IMAGE_SIZE = 4 * 1024 * 1024
MAX_NEW_CONTENT_IMAGES_SIZE = 8 * 1024 * 1024
MAX_NEW_IMAGES_SIZE = 15 * 1024 * 1024
TEMP_IMAGE_KEY = re.compile(r"local-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}")


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


class AdProductionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AdProductionRepository(db)
        self.users = UserRepository(db)
        self.audit = AuditService(db)
        self.files = FileService(db)

    def _require_permissions(self, actor_id: int, *codes: str) -> None:
        permissions = self.users.permission_codes(actor_id)
        if "*" not in permissions and not permissions.issuperset(codes):
            raise PermissionDenied()

    def _get_scoped(self, ad_id: int, actor_id: int, *, for_update: bool = False) -> AdProduction:
        permissions = self.users.permission_codes(actor_id)
        kinds = viewable_ad_production_kinds(permissions)
        if not kinds:
            raise PermissionDenied()
        item = self.repo.get_scoped(
            ad_id, actor_id, self.users.data_scope(actor_id), kinds, lock=for_update
        )
        if item is None:
            raise NotFoundError("制作需求不存在")
        if (
            for_update
            and "*" not in permissions
            and AD_PRODUCTION_PERMISSIONS[item.kind].edit not in permissions
        ):
            raise PermissionDenied()
        return item

    def _get_for_update(self, ad_id: int, actor_id: int, revision: int) -> AdProduction:
        item = self._get_scoped(ad_id, actor_id, for_update=True)
        if item.revision != revision:
            raise ConflictError("制作需求已更新。请刷新重试", revision_conflict_data(item))
        return item

    def _update_with_revision(
        self, item: AdProduction, revision: int, actor_id: int, values: dict
    ) -> None:
        if not self.repo.update_with_revision(
            item.id, revision, {**values, "updated_by": actor_id}
        ):
            raise ConflictError("制作需求已更新。请刷新重试", revision_conflict_data(item))

    def _people_names(self, items: Iterable[AdProduction]) -> dict[int, str]:
        return self.repo.participant_display_names(
            {
                user_id
                for item in items
                for user_id in (item.created_by, item.receiver_id, item.completed_by_id)
                if user_id is not None
            }
        )

    @staticmethod
    def _output(
        item: AdProduction, images: Iterable[FileObject], names: dict[int, str]
    ) -> AdProductionOut:
        return AdProductionOut(
            id=item.id,
            work_date=item.work_date,
            title=item.title,
            content=item.content,
            content_format=cast(AdProductionContentFormat, item.content_format),
            issuer=item.issuer,
            due_at=item.due_at,
            status=item.status,
            kind=item.kind,
            processing_result=item.processing_result,
            receiver_id=item.receiver_id,
            receiver_display_name=(
                names.get(item.receiver_id) if item.receiver_id is not None else None
            ),
            completed_by_id=item.completed_by_id,
            completed_by_display_name=(
                names.get(item.completed_by_id) if item.completed_by_id is not None else None
            ),
            created_by=item.created_by,
            publisher_display_name=names.get(item.created_by),
            created_at=item.created_at,
            updated_at=item.updated_at,
            revision=item.revision,
            images=[
                AttachmentOut(
                    file_id=image.id,
                    original_name=image.original_name,
                    size=image.size,
                    mime_type=image.mime_type,
                    created_at=image.created_at,
                    created_by=image.created_by,
                )
                for image in images
            ],
        )

    @staticmethod
    def _status_snapshot(item: AdProduction) -> dict:
        values = {
            "status": item.status.value,
            "completed_by_id": item.completed_by_id,
            "revision": item.revision,
        }
        if item.kind is AdProductionKind.MERCHANT_AD:
            values["kind"] = item.kind.value
            values["processing_result"] = item.processing_result
        return values

    @classmethod
    def _audit_snapshot(cls, item: AdProduction, images: Iterable[FileObject]) -> dict:
        return {
            **cls._status_snapshot(item),
            "work_date": item.work_date.isoformat(),
            "title": item.title,
            "content": item.content,
            "content_format": item.content_format,
            "issuer": item.issuer,
            "due_at": item.due_at.isoformat() if item.due_at is not None else None,
            "receiver_id": item.receiver_id,
            "image_ids": [image.id for image in images],
        }

    def listing(
        self,
        actor: User,
        *,
        kind: AdProductionKind,
        page: int,
        page_size: int,
        keyword: str | None,
        status: AdProductionStatus | None,
        date_from: date | None,
        date_to: date | None,
        published_from: datetime | None = None,
        published_before: datetime | None = None,
    ) -> AdProductionPage:
        self._require_permissions(actor.id, AD_PRODUCTION_PERMISSIONS[kind].view)
        if date_from is not None and date_to is not None and date_from > date_to:
            raise AppError(42290, "开始日期不能晚于结束日期", 422)
        if (
            published_from is not None
            and published_before is not None
            and published_from >= published_before
        ):
            raise AppError(42290, "发布时间上界必须晚于下界", 422)
        if keyword and "\x00" in keyword:
            raise AppError(42290, "关键词不能包含空字符", 422)
        items, total = self.repo.list_scoped(
            actor.id,
            self.users.data_scope(actor.id),
            page=page,
            page_size=page_size,
            keyword=(keyword or "").strip(),
            kind=kind,
            status=status,
            date_from=date_from,
            date_to=date_to,
            published_from=published_from,
            published_before=published_before,
        )
        images_by_ad: dict[int, list[FileObject]] = defaultdict(list)
        for relation, file in self.repo.active_images([item.id for item in items]):
            images_by_ad[relation.entity_id].append(file)
        names = self._people_names(items)
        return AdProductionPage(
            items=[self._output(item, images_by_ad[item.id], names) for item in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get(self, ad_id: int, actor: User) -> AdProductionOut:
        item = self._get_scoped(ad_id, actor.id)
        return self._output(
            item, (file for _, file in self.repo.active_images([ad_id])), self._people_names([item])
        )

    def designer_options(
        self, actor: User, kind: AdProductionKind
    ) -> list[AdProductionDesignerOption]:
        self._require_permissions(actor.id, AD_PRODUCTION_PERMISSIONS[kind].view)
        return [
            AdProductionDesignerOption(id=user_id, display_name=name)
            for user_id, name in self.repo.active_designers(kind).items()
        ]

    def open_image(
        self, ad_id: int, file_id: int, actor: User, *, inline: bool = False
    ) -> tuple[FileObject, BinaryIO]:
        self._get_scoped(ad_id, actor.id)
        file, stream = self.files.open_authorized_attachment(
            file_id,
            entity_type=CONTENT_IMAGE_ENTITY if inline else AD_PRODUCTION_ENTITY,
            entity_id=ad_id,
        )
        if file.mime_type not in IMAGE_MEDIA_TYPES:
            stream.close()
            raise NotFoundError("图片不存在")
        return file, stream

    @staticmethod
    def _clean_content(payload: AdProductionForm) -> str:
        try:
            if payload.content_format == "HTML":
                return sanitize_editor_content(
                    payload.content,
                    "HTML",
                    label="工作内容",
                    min_chars=1,
                    max_chars=MAX_CONTENT_CHARACTERS,
                )
            return validate_plain_content(payload.content)
        except ValueError as exc:
            raise AppError(
                42290,
                "请求参数或业务数据无效",
                422,
                {"errors": [{"loc": ["body", "content"], "msg": str(exc)}]},
            ) from exc

    @staticmethod
    def _read_images(images: list[UploadFile], retained_count: int) -> list[tuple[bytes, str, str]]:
        if retained_count + len(images) > MAX_IMAGES:
            raise AppError(42291, "每条物料制作记录最多保留 5 张图片", 422)

        uploads = []
        total_size = 0
        for image in images:
            mime = image.content_type
            if mime is None or mime not in IMAGE_MEDIA_TYPES:
                raise AppError(42292, "仅支持 PNG、JPEG 和 WebP 图片", 422)
            content = image.file.read(MAX_IMAGE_SIZE + 1)
            if len(content) > MAX_IMAGE_SIZE:
                raise AppError(42292, "单张图片不能超过 5 MiB", 422)
            total_size += len(content)
            if total_size > MAX_NEW_IMAGES_SIZE:
                raise AppError(42292, "单次新增图片合计不能超过 15 MiB", 422)
            uploads.append((content, image.filename or "", mime))
        return uploads

    def _store_images(
        self, ad_id: int, actor_id: int, uploads: list[tuple[bytes, str, str]]
    ) -> list[FileObject]:
        added = []
        for content, name, mime in uploads:
            item = self.files.store_in_transaction(content, name, mime, actor_id)
            self.db.add(
                AttachmentRelation(
                    entity_type=AD_PRODUCTION_ENTITY, entity_id=ad_id, file_id=item.id
                )
            )
            added.append(item)
        return added

    def _bind_content_images(
        self,
        ad_id: int,
        actor_id: int,
        content: str,
        content_format: str,
        images: list[UploadFile],
        gallery_uploads: list[tuple[bytes, str, str]],
    ) -> str:
        gallery_size = sum(len(content) for content, _, _ in gallery_uploads)
        inline_size = 0
        uploads = {}
        for image in images:
            key = image.filename or ""
            if not TEMP_IMAGE_KEY.fullmatch(key) or key in uploads:
                raise AppError(42265, "正文图片引用无效或重复。请重新插入", 422)
            mime = image.content_type
            if mime not in IMAGE_MEDIA_TYPES:
                raise AppError(42265, "仅支持 PNG、JPEG 和 WebP 图片", 422)
            binary = image.file.read(MAX_CONTENT_IMAGE_SIZE + 1)
            if len(binary) > MAX_CONTENT_IMAGE_SIZE:
                raise AppError(42265, "单张正文图片不能超过 4 MiB", 422)
            inline_size += len(binary)
            if inline_size > MAX_NEW_CONTENT_IMAGES_SIZE:
                raise AppError(42265, "单次新增正文图片合计不能超过 8 MiB", 422)
            if gallery_size + inline_size > MAX_NEW_IMAGES_SIZE:
                raise AppError(42292, "单次新增图片合计不能超过 15 MiB", 422)
            uploads[key] = f"data:{mime};base64,{b64encode(binary).decode('ascii')}"

        return bind_images(
            self.db,
            ad_id,
            actor_id,
            content,
            content_format,
            uploads,
            entity_type=CONTENT_IMAGE_ENTITY,
        )

    def _people_changes(
        self,
        kind: AdProductionKind,
        status: AdProductionStatus,
        *,
        receiver_id: int | None = None,
        completed_by_id: int | None = None,
        item: AdProduction | None = None,
    ) -> dict[str, int | None]:
        completed = status is AdProductionStatus.COMPLETED
        if not completed and completed_by_id:
            raise AppError(
                42290, "仅已完成的记录可以设置实际完成人", 422, {"field": "completed_by_id"}
            )

        fields = (
            ("receiver_id", receiver_id, item.receiver_id if item is not None else None),
            (
                "completed_by_id",
                completed_by_id if completed else 0,
                item.completed_by_id if item is not None else None,
            ),
        )
        changes: dict[str, int | None] = {}
        for field, requested, current in fields:
            if requested is not None and (requested or None) != current:
                changes[field] = requested or None

        candidates = {user_id for user_id in changes.values() if user_id is not None}
        if candidates:
            eligible = self.repo.active_designers(kind, lock_user_ids=candidates)
            for field, user_id in changes.items():
                if user_id is not None and user_id not in eligible:
                    raise AppError(42290, "请选择启用的设计人员", 422, {"field": field})
        return changes

    @staticmethod
    def _processing_result(
        item: AdProduction,
        payload: AdProductionUpdateForm | AdProductionStatusChange,
        people: dict[str, int | None],
    ) -> str | None:
        result = payload.processing_result
        if item.kind is AdProductionKind.MATERIAL:
            if result is not None:
                raise AppError(
                    42290, "只有商家广告制作可填写处理结果", 422, {"field": "processing_result"}
                )
            return None

        if payload.status is AdProductionStatus.SHIPPING:
            raise AppError(42290, "商家广告没有运输阶段", 422, {"field": "status"})
        if payload.status is not AdProductionStatus.COMPLETED:
            if result is not None:
                raise AppError(
                    42290, "处理完成时才可填写处理结果", 422, {"field": "processing_result"}
                )
            return None

        if people.get("completed_by_id", item.completed_by_id) is None:
            raise AppError(42290, "请指定实际完成人", 422, {"field": "completed_by_id"})
        if "processing_result" not in payload.model_fields_set:
            result = item.processing_result
        if result is None:
            raise AppError(42290, "请填写处理结果", 422, {"field": "processing_result"})
        return result

    def _notify_merchant(self, item: AdProduction, user_id: int, title: str, content: str) -> None:
        self.db.add(
            Notification(
                user_id=user_id,
                type=NotificationType.SYSTEM,
                title=title,
                content=content,
                entity_type=AD_PRODUCTION_ENTITY,
                entity_id=item.id,
            )
        )

    def _notify_merchant_completion(self, item: AdProduction, previous: AdProductionStatus) -> None:
        if (
            item.kind is AdProductionKind.MERCHANT_AD
            and item.status is AdProductionStatus.COMPLETED
            and previous is not AdProductionStatus.COMPLETED
        ):
            self._notify_merchant(
                item,
                item.created_by,
                "商家广告制作需求已完成",
                "你发布的商家广告制作需求已完成。请查看处理结果。",
            )

    def create(self, payload: AdProductionCreateForm, actor: User) -> AdProductionOut:
        permissions = AD_PRODUCTION_PERMISSIONS[payload.kind]
        required = [permissions.view, permissions.create]
        if (
            payload.kind is AdProductionKind.MATERIAL
            and payload.status is AdProductionStatus.COMPLETED
        ):
            required.append(permissions.edit)
        self._require_permissions(actor.id, *required)
        if (
            payload.kind is AdProductionKind.MERCHANT_AD
            and payload.status is not AdProductionStatus.NOT_STARTED
        ):
            raise AppError(42290, "商家广告制作需求初始状态必须为未处理", 422, {"field": "status"})
        content = self._clean_content(payload)
        uploads = self._read_images(payload.images, 0)
        try:
            people = self._people_changes(
                payload.kind,
                payload.status,
                receiver_id=payload.receiver_id,
                completed_by_id=payload.completed_by_id,
            )
            created_at = utcnow()
            publisher_name = actor.display_name.strip() or actor.username
            issuer = payload.issuer if payload.kind is AdProductionKind.MATERIAL else None
            item = AdProduction(
                work_date=payload.work_date or created_at.date(),
                title=payload.title,
                content=content,
                content_format=payload.content_format,
                issuer=issuer or publisher_name,
                due_at=payload.due_at,
                status=payload.status,
                kind=payload.kind,
                created_by=actor.id,
                created_at=created_at,
                updated_by=actor.id,
                **people,
            )
            self.db.add(item)
            self.db.flush()
            item.content = self._bind_content_images(
                item.id, actor.id, content, payload.content_format, payload.content_images, uploads
            )
            images = self._store_images(item.id, actor.id, uploads)
            output = self._output(item, images, self._people_names([item]))
            self.audit.log(
                AD_PRODUCTION_ENTITY, item.id, "CREATE", after=self._audit_snapshot(item, images)
            )
            if item.kind is AdProductionKind.MERCHANT_AD:
                self._notify_merchant(
                    item,
                    payload.receiver_id,
                    "新的商家广告制作需求",
                    "你收到了一条商家广告制作需求。请查看详情。",
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return output

    def update(
        self,
        ad_id: int,
        payload: AdProductionUpdateForm,
        actor: User,
        *,
        content_format_provided: bool,
    ) -> AdProductionOut:
        try:
            item = self._get_for_update(ad_id, actor.id, payload.revision)
            if payload.clear_due_at and payload.due_at is not None:
                raise AppError(
                    42290, "设置与清除截止时间不能同时提交", 422, {"field": "clear_due_at"}
                )

            people = self._people_changes(
                item.kind,
                payload.status,
                receiver_id=payload.receiver_id,
                completed_by_id=payload.completed_by_id,
                item=item,
            )
            previous = item.status
            result = self._processing_result(item, payload, people)
            active = self.repo.active_images([ad_id])
            removed = set(payload.remove_image_ids)
            if not removed.issubset(file.id for _, file in active):
                raise AppError(42293, "要移除的图片不属于当前记录", 422)
            uploads = self._read_images(payload.images, len(active) - len(removed))
            before = self._audit_snapshot(item, (file for _, file in active))

            # Browsers can normalize newlines in scalar multipart fields.
            if (
                not payload.content_images
                and (not content_format_provided or payload.content_format == item.content_format)
                and _normalize_newlines(payload.content) == _normalize_newlines(item.content)
            ):
                content, content_format = item.content, item.content_format
            else:
                content_format = payload.content_format
                content = self._bind_content_images(
                    ad_id,
                    actor.id,
                    self._clean_content(payload),
                    content_format,
                    payload.content_images,
                    uploads,
                )
            values = {
                "work_date": payload.work_date,
                "content": content,
                "content_format": content_format,
                "issuer": payload.issuer if item.kind is AdProductionKind.MATERIAL else item.issuer,
                "status": payload.status,
                "processing_result": result,
                **people,
            }
            if payload.title is not None:
                values["title"] = payload.title
            if payload.clear_due_at or payload.due_at is not None:
                values["due_at"] = payload.due_at
            self._update_with_revision(item, payload.revision, actor.id, values)

            retained = []
            for relation, file in active:
                if file.id in removed:
                    # Keep the relation so historical files remain blocked by the generic file API.
                    relation.entity_type = ARCHIVED_AD_PRODUCTION_ENTITY
                else:
                    retained.append(file)
            added = self._store_images(ad_id, actor.id, uploads)
            self.db.refresh(item)
            images = [*retained, *added]
            output = self._output(item, images, self._people_names([item]))
            self.audit.log(
                AD_PRODUCTION_ENTITY,
                ad_id,
                "UPDATE",
                before=before,
                after=self._audit_snapshot(item, images),
            )
            self._notify_merchant_completion(item, previous)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return output

    def update_status(
        self, ad_id: int, payload: AdProductionStatusChange, actor: User
    ) -> AdProductionOut:
        try:
            item = self._get_for_update(ad_id, actor.id, payload.revision)
            people = self._people_changes(
                item.kind, payload.status, completed_by_id=payload.completed_by_id, item=item
            )
            previous = item.status
            result = self._processing_result(item, payload, people)
            before = self._status_snapshot(item)
            self._update_with_revision(
                item,
                payload.revision,
                actor.id,
                {"status": payload.status, "processing_result": result, **people},
            )
            self.db.refresh(item)
            output = self._output(
                item,
                (file for _, file in self.repo.active_images([ad_id])),
                self._people_names([item]),
            )
            self.audit.log(
                AD_PRODUCTION_ENTITY,
                ad_id,
                "STATUS_CHANGE",
                before=before,
                after=self._status_snapshot(item),
            )
            self._notify_merchant_completion(item, previous)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return output
