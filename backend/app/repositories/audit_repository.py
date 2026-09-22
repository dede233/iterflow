from datetime import datetime

from sqlalchemy import and_, false, func, or_, select, true
from sqlalchemy.orm import Session

from app.models.entities import Feedback, OperationLog, Release, Requirement, User, Version
from app.models.enums import DataScope


class AuditRepository:
    """Read-only persistence queries for OperationLog.

    Audit records are scoped through the entity they describe.  Keeping this
    policy here makes the count query, page query, and detail query use the
    exact same visibility predicate.
    """

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _scoped_version_ids(user_id: int):
        return select(Version.id).where(
            or_(Version.owner_id == user_id, Version.created_by == user_id)
        )

    @classmethod
    def _visibility_criteria(
        cls,
        *,
        user_id: int,
        data_scope: DataScope,
        entity_types: set[str],
    ):
        """Build an allow-list predicate for records the caller may inspect."""

        all_scope = data_scope is DataScope.ALL
        branches = []

        if "FEEDBACK" in entity_types:
            predicate = true() if all_scope else Feedback.submitter_id == user_id
            branches.append(
                and_(
                    OperationLog.entity_type == "FEEDBACK",
                    OperationLog.entity_id.in_(select(Feedback.id).where(predicate)),
                )
            )

        if "REQUIREMENT" in entity_types:
            predicate = (
                true()
                if all_scope
                else or_(Requirement.owner_id == user_id, Requirement.created_by == user_id)
            )
            branches.append(
                and_(
                    OperationLog.entity_type == "REQUIREMENT",
                    OperationLog.entity_id.in_(select(Requirement.id).where(predicate)),
                )
            )

        if "VERSION" in entity_types:
            version_ids = select(Version.id) if all_scope else cls._scoped_version_ids(user_id)
            branches.append(
                and_(
                    OperationLog.entity_type == "VERSION",
                    OperationLog.entity_id.in_(version_ids),
                )
            )

        if "RELEASE" in entity_types:
            version_ids = select(Version.id) if all_scope else cls._scoped_version_ids(user_id)
            release_ids = select(Release.id).where(Release.version_id.in_(version_ids))
            branches.append(
                and_(OperationLog.entity_type == "RELEASE", OperationLog.entity_id.in_(release_ids))
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
            for entity_type in ("ROLE", "SYSTEM", "DICTIONARY"):
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

    def list_scoped(
        self,
        *,
        user_id: int,
        data_scope: DataScope,
        entity_types: set[str],
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
                user_id=user_id, data_scope=data_scope, entity_types=entity_types
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
    ) -> tuple[OperationLog, User | None] | None:
        row = self.db.execute(
            select(OperationLog, User)
            .outerjoin(User, User.id == OperationLog.operator_id)
            .where(
                OperationLog.id == audit_id,
                self._visibility_criteria(
                    user_id=user_id, data_scope=data_scope, entity_types=entity_types
                ),
            )
        ).one_or_none()
        return (row[0], row[1]) if row is not None else None
