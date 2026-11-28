from collections.abc import Collection
from datetime import datetime

from sqlalchemy import and_, false, func, or_, select, true
from sqlalchemy.orm import Session

from app.models.entities import (
    AdProduction,
    Feedback,
    OperationLog,
    Release,
    Requirement,
    User,
    Version,
)
from app.models.enums import AdProductionKind, DataScope
from app.repositories.ad_production_repository import AD_PRODUCTION_ENTITY, AdProductionRepository
from app.repositories.requirement_repository import RequirementRepository


class AuditRepository:
    """Read-only persistence queries for OperationLog.

    Audit records are scoped through the entity they describe.  Keeping this
    policy here makes the count query, page query, and detail query use the
    exact same visibility predicate.
    """

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _version_ids(user_id: int, all_scope: bool, *, active_entities_only: bool):
        query = select(Version.id)
        if not all_scope:
            query = query.where(or_(Version.owner_id == user_id, Version.created_by == user_id))
        if active_entities_only:
            query = query.where(Version.deleted_at.is_(None))
        return query

    @classmethod
    def _visibility_criteria(
        cls,
        *,
        user_id: int,
        data_scope: DataScope,
        entity_types: set[str],
        ad_production_kinds: Collection[AdProductionKind] = (),
        active_entities_only: bool = False,
    ):
        """Build an allow-list predicate for records the caller may inspect."""

        all_scope = data_scope is DataScope.ALL
        branches = []

        if "FEEDBACK" in entity_types:
            predicate = true() if all_scope else Feedback.submitter_id == user_id
            if active_entities_only:
                predicate = and_(predicate, Feedback.deleted_at.is_(None))
            branches.append(
                and_(
                    OperationLog.entity_type == "FEEDBACK",
                    OperationLog.entity_id.in_(select(Feedback.id).where(predicate)),
                )
            )

        if "REQUIREMENT" in entity_types:
            predicate = true() if all_scope else RequirementRepository.self_criterion(user_id)
            if active_entities_only:
                predicate = and_(predicate, Requirement.deleted_at.is_(None))
            branches.append(
                and_(
                    OperationLog.entity_type == "REQUIREMENT",
                    OperationLog.entity_id.in_(select(Requirement.id).where(predicate)),
                )
            )

        if "VERSION" in entity_types:
            version_ids = cls._version_ids(
                user_id, all_scope, active_entities_only=active_entities_only
            )
            branches.append(
                and_(
                    OperationLog.entity_type == "VERSION",
                    OperationLog.entity_id.in_(version_ids),
                )
            )

        if "RELEASE" in entity_types:
            version_ids = cls._version_ids(
                user_id, all_scope, active_entities_only=active_entities_only
            )
            release_ids = select(Release.id).where(Release.version_id.in_(version_ids))
            branches.append(
                and_(OperationLog.entity_type == "RELEASE", OperationLog.entity_id.in_(release_ids))
            )

        if AD_PRODUCTION_ENTITY in entity_types and ad_production_kinds:
            predicate = AdProductionRepository.scope_criterion(
                user_id, data_scope, ad_production_kinds
            )
            branches.append(
                and_(
                    OperationLog.entity_type == AD_PRODUCTION_ENTITY,
                    OperationLog.entity_id.in_(select(AdProduction.id).where(predicate)),
                )
            )

        # User and authentication records refer to a User id.  A self-scoped
        # administrator can inspect only records concerning their own account.
        for entity_type in ("USER", "AUTH"):
            if entity_type in entity_types:
                predicate = true() if all_scope else OperationLog.entity_id == user_id
                branches.append(and_(OperationLog.entity_type == entity_type, predicate))

        # Role and system objects are global configuration.  They have no
        # per-user ownership, so SELF never grants their audit history.
        if all_scope:
            for entity_type in (
                "ANNOUNCEMENT",
                "ROLE",
                "SYSTEM",
                "DICTIONARY",
                "BUSINESS_SYSTEM",
                "BUSINESS_MODULE",
            ):
                if entity_type in entity_types:
                    branches.append(OperationLog.entity_type == entity_type)

        return or_(*branches) if branches else false()

    @staticmethod
    def _filters(
        *,
        entity_type: str | None,
        entity_id: int | None,
        action: str | None,
        operator_id: int | None,
        time_from: datetime | None,
        time_to: datetime | None,
    ):
        criteria = []
        if entity_type is not None:
            criteria.append(OperationLog.entity_type == entity_type)
        if entity_id is not None:
            criteria.append(OperationLog.entity_id == entity_id)
        if action is not None:
            criteria.append(OperationLog.action == action)
        if operator_id is not None:
            criteria.append(OperationLog.operator_id == operator_id)
        if time_from is not None:
            criteria.append(OperationLog.created_at >= time_from)
        if time_to is not None:
            criteria.append(OperationLog.created_at <= time_to)
        return criteria

    def list_recent_scoped(
        self,
        *,
        user_id: int,
        data_scope: DataScope,
        entity_types: set[str],
        limit: int = 15,
    ) -> list[OperationLog]:
        """Read recent visible records without joining or exposing an operator."""
        return list(
            self.db.scalars(
                select(OperationLog)
                .where(
                    self._visibility_criteria(
                        user_id=user_id,
                        data_scope=data_scope,
                        entity_types=entity_types,
                        active_entities_only=True,
                    )
                )
                .order_by(OperationLog.created_at.desc(), OperationLog.id.desc())
                .limit(limit)
            ).all()
        )

    def list_for_entity(self, entity_type: str, entity_id: int):
        """Read ten records after the service authorizes the current object."""
        return self.db.execute(
            select(OperationLog, User)
            .outerjoin(User, User.id == OperationLog.operator_id)
            .where(
                OperationLog.entity_type == entity_type,
                OperationLog.entity_id == entity_id,
            )
            .order_by(OperationLog.created_at.desc(), OperationLog.id.desc())
            .limit(10)
        ).all()

    def list_scoped(
        self,
        *,
        user_id: int,
        data_scope: DataScope,
        entity_types: set[str],
        ad_production_kinds: Collection[AdProductionKind],
        page: int,
        size: int,
        entity_type: str | None = None,
        entity_id: int | None = None,
        action: str | None = None,
        operator_id: int | None = None,
        time_from: datetime | None = None,
        time_to: datetime | None = None,
    ) -> tuple[list[tuple[OperationLog, User | None]], int]:
        criteria = [
            self._visibility_criteria(
                user_id=user_id,
                data_scope=data_scope,
                entity_types=entity_types,
                ad_production_kinds=ad_production_kinds,
            ),
            *self._filters(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                operator_id=operator_id,
                time_from=time_from,
                time_to=time_to,
            ),
        ]
        total = self.db.scalar(select(func.count()).select_from(OperationLog).where(*criteria)) or 0
        rows = self.db.execute(
            select(OperationLog, User)
            .outerjoin(User, User.id == OperationLog.operator_id)
            .where(*criteria)
            .order_by(OperationLog.created_at.desc(), OperationLog.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        ).all()
        return [(row[0], row[1]) for row in rows], total

    def get_scoped(
        self,
        audit_id: int,
        *,
        user_id: int,
        data_scope: DataScope,
        entity_types: set[str],
        ad_production_kinds: Collection[AdProductionKind],
    ) -> tuple[OperationLog, User | None] | None:
        row = self.db.execute(
            select(OperationLog, User)
            .outerjoin(User, User.id == OperationLog.operator_id)
            .where(
                OperationLog.id == audit_id,
                self._visibility_criteria(
                    user_id=user_id,
                    data_scope=data_scope,
                    entity_types=entity_types,
                    ad_production_kinds=ad_production_kinds,
                ),
            )
        ).one_or_none()
        return (row[0], row[1]) if row is not None else None
