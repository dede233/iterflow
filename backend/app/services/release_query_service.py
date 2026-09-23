from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.entities import Release, User, Version
from app.models.enums import DataScope
from app.repositories.user_repository import UserRepository
from app.repositories.version_repository import VersionRepository


class ReleaseQueryService:
    """Read-only Release queries scoped through the owning Version."""

    def __init__(self, db: Session):
        self.db = db

    def list_for_user(
        self,
        actor: User,
        *,
        page: int,
        page_size: int,
        version_id: int | None,
    ) -> dict[str, object]:
        scope = UserRepository(self.db).data_scope(actor.id)
        criteria = [] if scope is DataScope.ALL else [VersionRepository.self_criterion(actor.id)]
        if version_id is not None:
            criteria.append(Release.version_id == version_id)
        total = (
            self.db.scalar(
                select(func.count())
                .select_from(Release)
                .join(Version, Version.id == Release.version_id)
                .where(*criteria)
            )
            or 0
        )
        items = list(
            self.db.scalars(
                select(Release)
                .join(Version, Version.id == Release.version_id)
                .where(*criteria)
                .order_by(Release.released_at.desc(), Release.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def get_for_user(self, release_id: int, actor: User) -> Release:
        scope = UserRepository(self.db).data_scope(actor.id)
        criteria = [Release.id == release_id]
        if scope is not DataScope.ALL:
            criteria.append(VersionRepository.self_criterion(actor.id))
        release = self.db.scalar(
            select(Release).join(Version, Version.id == Release.version_id).where(*criteria)
        )
        if release is None:
            raise NotFoundError("发布记录不存在")
        return release
