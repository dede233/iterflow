from collections import defaultdict
from collections.abc import Collection, Sequence
from datetime import date, datetime

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.domain.ad_production_permissions import AD_PRODUCTION_PERMISSIONS
from app.models.entities import (
    AdProduction,
    AttachmentRelation,
    FileObject,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.models.enums import AdProductionKind, AdProductionStatus, DataScope, UserStatus
from app.repositories.base import BaseRepository

AD_PRODUCTION_ENTITY = "AD_PRODUCTION"
ARCHIVED_AD_PRODUCTION_ENTITY = "AD_PRODUCTION_ARCHIVED"


class AdProductionRepository(BaseRepository[AdProduction]):
    def __init__(self, db: Session):
        super().__init__(db, AdProduction)

    @staticmethod
    def scope_criterion(
        user_id: int, data_scope: DataScope, kinds: Collection[AdProductionKind]
    ) -> ColumnElement[bool]:
        kind_criterion = AdProduction.kind.in_(kinds)
        if data_scope is DataScope.ALL:
            return kind_criterion
        return and_(
            kind_criterion,
            or_(
                AdProduction.created_by == user_id,
                AdProduction.receiver_id == user_id,
                AdProduction.completed_by_id == user_id,
            ),
        )

    def active_designers(
        self, kind: AdProductionKind, *, lock_user_ids: set[int] | None = None
    ) -> dict[int, str]:
        codes = AD_PRODUCTION_PERMISSIONS[kind]
        required_permissions = {codes.view, codes.edit}
        # The qualifying design role and the roles granting access can differ.
        permission_membership = aliased(UserRole)
        permission_role = aliased(Role)
        stmt = (
            select(User.id, User.display_name, Permission.code)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .join(permission_membership, permission_membership.user_id == User.id)
            .join(permission_role, permission_role.id == permission_membership.role_id)
            .join(RolePermission, RolePermission.role_id == permission_role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(
                User.status == UserStatus.ACTIVE,
                Role.code.in_(("DESIGNER", "AD_PRODUCTION_COMPLETER")),
                Role.enabled.is_(True),
                Role.is_system.is_(True),
                permission_role.enabled.is_(True),
                Permission.code.in_(required_permissions | {"*"}),
            )
            .order_by(User.id)
        )
        if lock_user_ids is not None:
            # User administration locks the account before updating role memberships.
            # Take the account locks first, independent of the optimizer's join order.
            locked_ids = self.db.scalars(
                select(User.id)
                .where(User.id.in_(lock_user_ids), User.status == UserStatus.ACTIVE)
                .order_by(User.id)
                .with_for_update(read=True)
            ).all()
            if not locked_ids:
                return {}
            stmt = stmt.where(User.id.in_(locked_ids)).with_for_update(read=True)
        names: dict[int, str] = {}
        permissions: dict[int, set[str]] = defaultdict(set)
        for user_id, name, code in self.db.execute(stmt):
            names[user_id] = name
            permissions[user_id].add(code)
        return {
            user_id: name
            for user_id, name in names.items()
            if "*" in permissions[user_id] or required_permissions <= permissions[user_id]
        }

    def participant_display_names(self, user_ids: set[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        rows = self.db.execute(select(User.id, User.display_name).where(User.id.in_(user_ids)))
        return {user_id: name for user_id, name in rows}

    def get_scoped(
        self,
        ad_id: int,
        user_id: int,
        data_scope: DataScope,
        kinds: Collection[AdProductionKind],
        *,
        lock: bool = False,
    ) -> AdProduction | None:
        stmt = select(AdProduction).where(
            AdProduction.id == ad_id, self.scope_criterion(user_id, data_scope, kinds)
        )
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return self.db.scalar(stmt)

    def list_scoped(
        self,
        user_id: int,
        data_scope: DataScope,
        *,
        kind: AdProductionKind,
        page: int,
        page_size: int,
        keyword: str,
        status: AdProductionStatus | None,
        date_from: date | None,
        date_to: date | None,
        published_from: datetime | None,
        published_before: datetime | None,
    ) -> tuple[list[AdProduction], int]:
        criteria = [self.scope_criterion(user_id, data_scope, (kind,))]
        if keyword:
            criteria.append(
                or_(
                    AdProduction.title.icontains(keyword, autoescape=True),
                    AdProduction.content.icontains(keyword, autoescape=True),
                    AdProduction.issuer.icontains(keyword, autoescape=True),
                )
            )
        if status is not None:
            criteria.append(AdProduction.status == status)
        if date_from is not None:
            criteria.append(AdProduction.work_date >= date_from)
        if date_to is not None:
            criteria.append(AdProduction.work_date <= date_to)
        if published_from is not None:
            criteria.append(AdProduction.created_at >= published_from)
        if published_before is not None:
            criteria.append(AdProduction.created_at < published_before)

        total = self.db.scalar(select(func.count()).select_from(AdProduction).where(*criteria)) or 0
        offset = (page - 1) * page_size
        if offset >= total:
            return [], total
        items = self.db.scalars(
            select(AdProduction)
            .where(*criteria)
            .order_by(AdProduction.created_at.desc(), AdProduction.id.desc())
            .offset(offset)
            .limit(page_size)
        ).all()
        return list(items), total

    def active_images(self, ad_ids: Sequence[int]) -> list[tuple[AttachmentRelation, FileObject]]:
        if not ad_ids:
            return []
        rows = self.db.execute(
            select(AttachmentRelation, FileObject)
            .join(FileObject, FileObject.id == AttachmentRelation.file_id)
            .where(
                AttachmentRelation.entity_type == AD_PRODUCTION_ENTITY,
                AttachmentRelation.entity_id.in_(ad_ids),
            )
            .order_by(AttachmentRelation.id)
        )
        return [(relation, item) for relation, item in rows]
