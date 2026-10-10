from datetime import UTC, datetime

from sqlalchemy import delete, exists, func, select, update
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
from app.models.enums import NotificationType, RequirementStatus, UserStatus
from app.repositories.requirement_repository import RequirementRepository
from app.repositories.user_repository import UserRepository
from app.schemas.requirement import (
    AssigneeOption,
    AssigneeOptionsPage,
    DeveloperCompletion,
    DevelopmentCompletionRequest,
    RequirementCollaboratorGroupUpdate,
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

    def require_development_completed(self, requirement_id: int) -> None:
        # The caller holds the requirement parent lock acquired by revision CAS.
        # Current reads serialize with personal confirmations and roster changes.
        developers = list(
            self.db.scalars(
                select(RequirementParticipant)
                .where(
                    RequirementParticipant.requirement_id == requirement_id,
                    RequirementParticipant.discipline == "DEVELOPMENT",
                )
                .order_by(RequirementParticipant.user_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        if not developers:
            raise AppError(40913, "尚未分配开发人员，不能将需求标记为已完成", 409)  # noqa: RUF001
        if any(developer.completed_at is None for developer in developers):
            raise AppError(40913, "开发人员尚未全部本人确认完成，不能将需求标记为已完成", 409)  # noqa: RUF001

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
            select(RequirementParticipant.discipline, RequirementParticipant.completed_at, User)
            .join(User, User.id == RequirementParticipant.user_id)
            .where(RequirementParticipant.requirement_id == requirement.id)
            .order_by(User.id)
        ).all()
        owner = self.db.get(User, requirement.owner_id) if requirement.owner_id else None
        return RequirementCollaboratorsOut(
            revision=requirement.revision,
            owner=self._option(owner) if owner else None,
            developers=[self._option(u) for kind, _, u in rows if kind == "DEVELOPMENT"],
            designers=[self._option(u) for kind, _, u in rows if kind == "DESIGN"],
            development_completions=[
                DeveloperCompletion(user_id=u.id, completed_at=at)
                for kind, at, u in rows
                if kind == "DEVELOPMENT"
            ],
        )

    def apply_members(self, requirement: Requirement, kind: str, ids: list[int]) -> None:
        users = self.db.scalars(
            select(User)
            .where(User.id.in_(ids), User.status == UserStatus.ACTIVE, eligible_user_criterion())
            .order_by(User.id)
            .with_for_update()
        ).all()
        if len(users) != len(ids):
            raise AppError(42212, "阶段人员必须是启用且具备需求查看权限的账号", 422)
        options = [self._option(u) for u in users]
        if kind == "DEVELOPMENT" and any(not u.can_develop for u in options):
            raise AppError(42212, "请选择具备开发人员或研发负责人角色的账号", 422)
        if kind == "DESIGN" and any(not u.can_design for u in options):
            raise AppError(42212, "请选择具备设计人员角色的账号", 422)
        before = self.read(requirement).model_dump(mode="json")
        completions = dict(
            self.db.execute(
                select(RequirementParticipant.user_id, RequirementParticipant.completed_at).where(
                    RequirementParticipant.requirement_id == requirement.id,
                    RequirementParticipant.discipline == kind,
                )
            ).all()
        )
        self.db.execute(
            delete(RequirementParticipant).where(
                RequirementParticipant.requirement_id == requirement.id,
                RequirementParticipant.discipline == kind,
            )
        )
        self.db.add_all(
            RequirementParticipant(
                requirement_id=requirement.id,
                user_id=uid,
                discipline=kind,
                completed_at=completions.get(uid),
            )
            for uid in ids
        )
        self.db.flush()
        AuditService(self.db).log(
            "REQUIREMENT",
            requirement.id,
            "ASSIGN_" + kind,
            before=before,
            after=self.read(requirement).model_dump(mode="json"),
        )

    def replace_group(
        self, requirement_id: int, payload: RequirementCollaboratorGroupUpdate, operator_id: int
    ) -> RequirementCollaboratorsOut:
        requirement = self.db.scalar(
            select(Requirement)
            .where(Requirement.id == requirement_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if requirement is None:
            raise NotFoundError("需求不存在")
        if requirement.revision != payload.revision:
            raise ConflictError("需求已被其他用户修改", revision_conflict_data(requirement))
        if payload.kind == "OWNER":
            if (
                payload.owner_id is not None
                and self.db.scalar(
                    select(User.id)
                    .where(
                        User.id == payload.owner_id,
                        User.status == UserStatus.ACTIVE,
                        eligible_user_criterion(),
                    )
                    .with_for_update()
                )
                is None
            ):
                raise AppError(42212, "总负责人必须是启用且具备需求查看权限的账号", 422)
            before = self.read(requirement).model_dump(mode="json")
            if not RequirementRepository(self.db).update_with_revision(
                requirement_id,
                payload.revision,
                {"owner_id": payload.owner_id, "updated_by": operator_id},
            ):
                raise ConflictError("需求已被其他用户修改", revision_conflict_data(requirement))
            self.db.refresh(requirement)
            AuditService(self.db).log(
                "REQUIREMENT",
                requirement_id,
                "ASSIGN_OWNER",
                before=before,
                after=self.read(requirement).model_dump(mode="json"),
            )
            self.notify(requirement, operator_id, "负责人已更新", "请查看最新总负责人。")
            self.db.commit()
            return self.read(requirement)
        allowed = (
            {RequirementStatus.DESIGNING}
            if payload.kind == "DESIGN"
            else {RequirementStatus.DEVELOPING, RequirementStatus.TESTING, RequirementStatus.DONE}
        )
        if requirement.status not in allowed:
            raise ConflictError("请在对应设计或开发阶段调整人员")
        if not payload.user_ids:
            raise AppError(42212, "当前阶段至少需要一名参与人员", 422)
        self.apply_members(requirement, payload.kind, payload.user_ids)
        if not RequirementRepository(self.db).update_with_revision(
            requirement_id, payload.revision, {"updated_by": operator_id}
        ):
            raise ConflictError("需求已被其他用户修改", revision_conflict_data(requirement))
        self.db.refresh(requirement)
        self.notify(
            requirement,
            operator_id,
            "阶段分工已更新",
            "请查看当前阶段的人员分工。",
            discipline=payload.kind,
        )
        self.db.commit()
        return self.read(requirement)

    def replace(
        self, requirement_id: int, payload: RequirementCollaboratorsUpdate, operator_id: int
    ) -> RequirementCollaboratorsOut:
        requirement = self.db.scalar(
            select(Requirement)
            .where(Requirement.id == requirement_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if requirement is None:
            raise NotFoundError("需求不存在")
        if requirement.revision != payload.revision:
            raise ConflictError(
                "需求已被其他用户修改。请刷新后重试", revision_conflict_data(requirement)
            )
        if requirement.status in {RequirementStatus.ONLINE, RequirementStatus.CANCELED}:
            raise ConflictError("终态需求不能重新分配协作人员")
        if (
            requirement.status
            in {RequirementStatus.DEVELOPING, RequirementStatus.TESTING, RequirementStatus.DONE}
            and not payload.developer_ids
        ):
            raise AppError(42212, "开发阶段至少保留一名开发人员", 422)
        if requirement.status == RequirementStatus.DESIGNING and not payload.designer_ids:
            raise AppError(42212, "设计阶段至少保留一名设计人员", 422)
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
        before = self.read(requirement).model_dump(mode="json")
        completions = {
            (p.user_id, p.discipline): p.completed_at
            for p in self.db.scalars(
                select(RequirementParticipant).where(
                    RequirementParticipant.requirement_id == requirement_id
                )
            )
        }
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
            RequirementParticipant(
                requirement_id=requirement_id,
                user_id=uid,
                discipline=kind,
                completed_at=completions.get((uid, kind)),
            )
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
            after=result.model_dump(mode="json"),
        )
        self.notify(requirement, operator_id, "协作分工已更新", "请查看总负责人、开发和设计分工。")
        self.db.commit()
        return result

    def reset_development(self, requirement_id: int) -> None:
        before = list(
            self.db.execute(
                select(RequirementParticipant.user_id, RequirementParticipant.completed_at).where(
                    RequirementParticipant.requirement_id == requirement_id,
                    RequirementParticipant.discipline == "DEVELOPMENT",
                    RequirementParticipant.completed_at.is_not(None),
                )
            ).all()
        )
        self.db.execute(
            update(RequirementParticipant)
            .where(
                RequirementParticipant.requirement_id == requirement_id,
                RequirementParticipant.discipline == "DEVELOPMENT",
            )
            .values(completed_at=None)
        )
        if before:
            AuditService(self.db).log(
                "REQUIREMENT",
                requirement_id,
                "RESET_DEVELOPMENT_COMPLETION",
                before={
                    "confirmations": [
                        {"user_id": uid, "completed_at": at.isoformat() if at is not None else None}
                        for uid, at in before
                    ]
                },
                after={"completed": False},
            )

    def confirm_development(
        self, requirement_id: int, payload: DevelopmentCompletionRequest, operator_id: int
    ) -> RequirementCollaboratorsOut:
        requirement = self.db.scalar(
            select(Requirement)
            .where(Requirement.id == requirement_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if requirement is None:
            raise NotFoundError("需求不存在")
        if requirement.revision != payload.revision:
            raise ConflictError("需求已被其他用户修改", revision_conflict_data(requirement))
        participant = self.db.get(
            RequirementParticipant, (requirement_id, operator_id, "DEVELOPMENT")
        )
        user = self.db.get(User, operator_id)
        if (
            participant is None
            or user is None
            or user.status != UserStatus.ACTIVE
            or not self._option(user).can_develop
        ):
            raise AppError(40300, "只能确认本人绑定的开发工作。不能代确认", 403)
        if requirement.status not in {
            RequirementStatus.DEVELOPING,
            RequirementStatus.TESTING,
            RequirementStatus.DONE,
        }:
            raise ConflictError("仅开发、测试或完成阶段可以确认开发完成")
        if participant.completed_at is not None:
            raise ConflictError("本人已确认完成。无需重复确认")
        if not RequirementRepository(self.db).update_with_revision(
            requirement_id, payload.revision, {"updated_by": operator_id}
        ):
            raise ConflictError("需求已被其他用户修改", revision_conflict_data(requirement))
        participant.completed_at = datetime.now(UTC)
        self.db.flush()
        self.db.refresh(requirement)
        AuditService(self.db).log(
            "REQUIREMENT",
            requirement_id,
            "CONFIRM_DEVELOPMENT_COMPLETION",
            before={"user_id": operator_id, "completed_at": None},
            after={"user_id": operator_id, "completed_at": participant.completed_at.isoformat()},
        )
        self.notify(
            requirement,
            operator_id,
            "开发人员已确认完成",
            f"{user.display_name} 已确认本人开发完成。全部开发人员确认后才可发布。",
            discipline="DEVELOPMENT",
        )
        self.db.commit()
        return self.read(requirement)

    def notify(
        self,
        requirement: Requirement,
        operator_id: int,
        title: str,
        content: str,
        *,
        discipline: str | None = None,
    ) -> None:
        recipients = set(
            self.db.scalars(
                select(RequirementParticipant.user_id).where(
                    RequirementParticipant.requirement_id == requirement.id,
                    *([RequirementParticipant.discipline == discipline] if discipline else []),
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
