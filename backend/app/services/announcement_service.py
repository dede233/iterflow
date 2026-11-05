from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, PermissionDenied
from app.models.entities import Announcement, AnnouncementRead, User
from app.repositories.base import BaseRepository
from app.repositories.user_repository import UserRepository
from app.schemas.announcement import (
    AnnouncementCreate,
    AnnouncementNotice,
    AnnouncementOut,
    AnnouncementPage,
    AnnouncementUpdate,
)
from app.services.audit_service import AuditService
from app.services.requirement_images import bind_images
from app.services.revision_conflict import revision_conflict_data

IMAGE_ENTITY = "ANNOUNCEMENT_IMAGE"


class AnnouncementService:
    def __init__(self, db: Session):
        self.db = db

    def can_manage(self, user: User) -> bool:
        return UserRepository(self.db).can_manage_announcements(user.id)

    def require_manager(self, user: User) -> None:
        if not self.can_manage(user):
            raise PermissionDenied("仅超级管理员可管理产品更新公告")

    def get(self, ident: int, user: User, *, lock: bool = False) -> Announcement:
        query = select(Announcement).where(Announcement.id == ident)
        if not self.can_manage(user):
            query = query.where(Announcement.published_at.is_not(None))
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        item = self.db.scalar(query)
        if item is None:
            raise NotFoundError()
        return item

    def out(self, item: Announcement, user: User) -> AnnouncementOut:
        read = self.db.get(AnnouncementRead, (item.id, user.id))
        return AnnouncementOut(
            **{key: getattr(item, key) for key in AnnouncementOut.model_fields if key != "read_at"},
            read_at=read.read_at if read else None,
        )

    def unread_query(self, user: User):
        read = select(AnnouncementRead.announcement_id).where(AnnouncementRead.user_id == user.id)
        return select(Announcement).where(
            Announcement.published_at.is_not(None), Announcement.id.not_in(read)
        )

    def unread_count(self, user: User) -> int:
        return (
            self.db.scalar(select(func.count()).select_from(self.unread_query(user).subquery()))
            or 0
        )

    def listing(self, user: User, page: int, page_size: int, manage: bool) -> AnnouncementPage:
        if manage:
            self.require_manager(user)
        query = select(Announcement)
        if not manage:
            query = query.where(Announcement.published_at.is_not(None))
        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
        order = Announcement.created_at if manage else Announcement.published_at
        items = self.db.scalars(
            query.order_by(order.desc(), Announcement.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return AnnouncementPage(
            items=[self.out(item, user) for item in items],
            page=page,
            page_size=page_size,
            total=total,
            unread_count=self.unread_count(user),
            can_manage=self.can_manage(user),
        )

    def notice(self, user: User) -> AnnouncementNotice:
        query = self.unread_query(user).order_by(
            Announcement.published_at.desc(), Announcement.id.desc()
        )
        latest = self.db.scalar(query.limit(1))
        important = self.db.scalar(query.where(Announcement.important.is_(True)).limit(1))
        return AnnouncementNotice(
            unread_count=self.unread_count(user),
            latest=self.out(latest, user) if latest else None,
            important=self.out(important, user) if important else None,
        )

    def create(self, payload: AnnouncementCreate, user: User) -> AnnouncementOut:
        self.require_manager(user)
        item = Announcement(
            **payload.model_dump(exclude={"image_uploads"}), created_by=user.id, updated_by=user.id
        )
        self.db.add(item)
        self.db.flush()
        item.content = bind_images(
            self.db,
            item.id,
            user.id,
            item.content,
            "HTML",
            payload.image_uploads,
            entity_type=IMAGE_ENTITY,
        )
        self.db.flush()
        AuditService(self.db).log("ANNOUNCEMENT", item.id, "CREATE", after={"title": item.title})
        self.db.commit()
        return self.out(item, user)

    def update(self, ident: int, payload: AnnouncementUpdate, user: User) -> AnnouncementOut:
        self.require_manager(user)
        item = self.get(ident, user, lock=True)
        self.check_revision(item, payload.revision)
        data = payload.model_dump(exclude={"revision", "image_uploads"})
        data["content"] = bind_images(
            self.db,
            item.id,
            user.id,
            payload.content,
            "HTML",
            payload.image_uploads,
            entity_type=IMAGE_ENTITY,
        )
        data["updated_by"] = user.id
        before = {"title": item.title, "revision": item.revision}
        if not BaseRepository(self.db, Announcement).update_with_revision(
            ident, payload.revision, data
        ):
            raise ConflictError("公告已更新。请刷新重试", revision_conflict_data(item))
        AuditService(self.db).log(
            "ANNOUNCEMENT",
            ident,
            "UPDATE",
            before=before,
            after={"title": payload.title, "revision": payload.revision + 1},
        )
        self.db.commit()
        self.db.refresh(item)
        return self.out(item, user)

    @staticmethod
    def check_revision(item: Announcement, revision: int) -> None:
        if item.revision != revision:
            raise ConflictError("公告已更新。请刷新重试", revision_conflict_data(item))

    def publish(self, ident: int, revision: int, user: User) -> AnnouncementOut:
        self.require_manager(user)
        item = self.get(ident, user, lock=True)
        self.check_revision(item, revision)
        if item.published_at is not None:
            raise ConflictError("公告已发布。请勿重复发布")
        BaseRepository(self.db, Announcement).update_with_revision(
            ident,
            revision,
            {
                "published_at": datetime.now(UTC),
                "updated_by": user.id,
            },
        )
        AuditService(self.db).log("ANNOUNCEMENT", ident, "PUBLISH", after={"title": item.title})
        self.db.commit()
        self.db.refresh(item)
        return self.out(item, user)

    def mark_read(self, ident: int, revision: int, user: User) -> AnnouncementOut:
        # Serialize per announcement; reading neither changes its revision nor other users' state.
        item = self.get(ident, user, lock=True)
        if item.published_at is None:
            raise NotFoundError()
        read = self.db.get(AnnouncementRead, (ident, user.id))
        if read is None:
            self.check_revision(item, revision)
            self.db.add(AnnouncementRead(announcement_id=ident, user_id=user.id))
        self.db.commit()
        return self.out(item, user)
