from sqlalchemy import delete, exists, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.models.entities import (
    Notification,
    Permission,
    Requirement,
    RequirementParticipant,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.models.enums import NotificationType, UserStatus
from app.repositories.requirement_repository import RequirementRepository
from app.repositories.user_repository import UserRepository
from app.schemas.requirement import (
    AssigneeOption,
    AssigneeOptionsPage,
    RequirementCollaboratorsOut,
    RequirementCollaboratorsUpdate,
)
from app.services.audit_service import AuditService
from app.services.revision_conflict import revision_conflict_data


def eligible_user_criterion():
    return exists(
        select(UserRole.user_id)
        .join(Role, Role.id == UserRole.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            UserRole.user_id == User.id,
            Role.enabled.is_(True),
            Permission.code.in_(["rd.requirement.view", "*"]),
        )
    )


class RequirementCollaborationService:
    def __init__(self, db: Session):
        self.db = db

    def _option(self, user: User) -> AssigneeOption:
        roles = set(
            self.db.scalars(
                select(Role.code)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == user.id, Role.enabled.is_(True))
            )
        )
        return AssigneeOption(
            user_id=user.id,
            display_name=user.display_name,
            can_develop=bool(roles & {"DEVELOPER", "DEVELOPMENT_LEAD"}),
            can_design="DESIGNER" in roles,
        )

    def options(self, keyword: str | None, page: int, kind: str = "OWNER") -> AssigneeOptionsPage:
        criteria = [User.status == UserStatus.ACTIVE, eligible_user_criterion()]
        if kind != "OWNER":
            codes = ["DEVELOPER", "DEVELOPMENT_LEAD"] if kind == "DEVELOPER" else ["DESIGNER"]
            criteria.append(
                exists(
                    select(UserRole.user_id)
                    .join(Role, Role.id == UserRole.role_id)
                    .where(
                        UserRole.user_id == User.id, Role.enabled.is_(True), Role.code.in_(codes)
                    )
                )
            )
        if keyword and keyword.strip():
            literal = keyword.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            criteria.append(User.display_name.ilike(f"%{literal}%", escape="\\"))
        total = self.db.scalar(select(func.count()).select_from(User).where(*criteria)) or 0
        users = self.db.scalars(
            select(User).where(*criteria).order_by(User.id).offset((page - 1) * 50).limit(50)
        ).all()
        return AssigneeOptionsPage(
            items=[self._option(u) for u in users], total=total, page=page, page_size=50
        )

    def read(self, requirement: Requirement) -> RequirementCollaboratorsOut:
        rows = self.db.execute(
            select(RequirementParticipant.discipline, User)
            .join(User, User.id == RequirementParticipant.user_id)
            .where(RequirementParticipant.requirement_id == requirement.id)
            .order_by(User.id)
        ).all()
        owner = self.db.get(User, requirement.owner_id) if requirement.owner_id else None
        return RequirementCollaboratorsOut(
            revision=requirement.revision,
            owner=self._option(owner) if owner else None,
            developers=[self._option(u) for kind, u in rows if kind == "DEVELOPMENT"],
            designers=[self._option(u) for kind, u in rows if kind == "DESIGN"],
        )

    def replace(
        self, requirement_id: int, payload: RequirementCollaboratorsUpdate, operator_id: int
    ) -> RequirementCollaboratorsOut:
        requirement = self.db.scalar(
            select(Requirement).where(Requirement.id == requirement_id).with_for_update()
        )
        if requirement is None:
            raise NotFoundError("需求不存在")
        if requirement.revision != payload.revision:
            raise ConflictError(
                "需求已被其他用户修改。请刷新后重试", revision_conflict_data(requirement)
            )
        ids = set(payload.developer_ids + payload.designer_ids)
        if payload.owner_id is not None:
            ids.add(payload.owner_id)
        users = {
            u.id: u
            for u in self.db.scalars(
                select(User)
                .where(
                    User.id.in_(ids), User.status == UserStatus.ACTIVE, eligible_user_criterion()
                )
                .order_by(User.id)
                .with_for_update()
            )
        }
        if ids != set(users):
            raise AppError(42212, "协作人员必须是启用且具备需求查看权限的账号", 422)
        options = {uid: self._option(u) for uid, u in users.items()}
        if any(not options[uid].can_develop for uid in payload.developer_ids):
            raise AppError(42212, "开发人员需要启用的开发人员或研发负责人角色", 422)
        if any(not options[uid].can_design for uid in payload.designer_ids):
            raise AppError(42212, "设计人员需要启用的设计人员角色", 422)
        before = self.read(requirement).model_dump()
        if not RequirementRepository(self.db).update_with_revision(
            requirement_id,
            payload.revision,
            {"owner_id": payload.owner_id, "updated_by": operator_id},
        ):
            self.db.expire_all()
            raise ConflictError(
                "需求已被其他用户修改。请刷新后重试",
                revision_conflict_data(self.db.get(Requirement, requirement_id)),
            )
        self.db.execute(
            delete(RequirementParticipant).where(
                RequirementParticipant.requirement_id == requirement_id
            )
        )
        self.db.add_all(
            RequirementParticipant(requirement_id=requirement_id, user_id=uid, discipline=kind)
            for kind, members in [
                ("DEVELOPMENT", payload.developer_ids),
                ("DESIGN", payload.designer_ids),
            ]
            for uid in members
        )
        self.db.flush()
        self.db.refresh(requirement)
        result = self.read(requirement)
        AuditService(self.db).log(
            "REQUIREMENT",
            requirement_id,
            "ASSIGN_COLLABORATORS",
            before=before,
            after=result.model_dump(),
        )
        self.notify(requirement, operator_id, "协作分工已更新", "请查看总负责人、开发和设计分工。")
        self.db.commit()
        return result

    def notify(self, requirement: Requirement, operator_id: int, title: str, content: str) -> None:
        recipients = set(
            self.db.scalars(
                select(RequirementParticipant.user_id).where(
                    RequirementParticipant.requirement_id == requirement.id
                )
            )
        )
        recipients.update(
            uid for uid in (requirement.owner_id, requirement.created_by) if uid is not None
        )
        recipients.discard(operator_id)
        repository = UserRepository(self.db)
        for user in self.db.scalars(
            select(User).where(User.id.in_(recipients), User.status == UserStatus.ACTIVE)
        ):
            permissions = repository.permission_codes(user.id)
            if permissions.isdisjoint({"rd.requirement.view", "*"}):
                continue
            if (
                RequirementRepository(self.db).get_scoped(
                    requirement.id, user.id, repository.data_scope(user.id)
                )
                is None
            ):
                continue
            self.db.add(
                Notification(
                    user_id=user.id,
                    type=NotificationType.REQUIREMENT,
                    title=f"需求 {requirement.requirement_no} {title}",
                    content=content,
                    entity_type="REQUIREMENT",
                    entity_id=requirement.id,
                )
            )
