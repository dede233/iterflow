from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDenied
from app.core.security import hash_password
from app.models.entities import Role, User, UserRole
from app.models.enums import UserStatus
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserOut, UserRoleUpdate, UserStatusChange, UserUpdate
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService


class UserAdministrationService:
    """Security-sensitive user administration transaction boundary.

    Every create, role assignment, and status transaction first locks the
    system SUPER_ADMIN role row. This serializes all operations that can change
    the effective SUPER_ADMIN set before user revision or UserRole mutation.
    """

    LAST_SUPER_ADMIN_MESSAGE = "至少必须保留一个有效的超级管理员"

    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.audit = AuditService(db)

    def _out(self, user: User) -> UserOut:
        return UserOut.model_validate(user).model_copy(
            update={"role_ids": self.users.role_ids(user.id)}
        )

    def _lock_super_admin_role(self) -> Role:
        role = self.users.get_super_admin_role_for_update()
        if role is None:
            raise ConflictError("SUPER_ADMIN 系统角色不存在或配置异常")
        return role

    def _user_or_404(self, user_id: int) -> User:
        user = self.users.get_fresh(user_id)
        if user is None:
            raise NotFoundError("用户不存在")
        return user

    def _validate_role_ids(self, role_ids: list[int]) -> dict[int, Role]:
        roles = self.users.roles_by_ids(role_ids)
        by_id = {role.id: role for role in roles}
        missing_ids = sorted(set(role_ids) - set(by_id))
        if missing_ids:
            raise AppError(42202, "包含不存在的角色", 422, {"role_ids": missing_ids})
        disabled_ids = sorted(role.id for role in roles if not role.enabled)
        if disabled_ids:
            raise AppError(42203, "不能分配已禁用的角色", 422, {"role_ids": disabled_ids})
        return by_id

    def _ensure_operator_is_effective_super_admin(
        self, operator_id: int, super_admin_role: Role
    ) -> None:
        if not self.users.is_effective_super_admin(operator_id, super_admin_role.id):
            raise PermissionDenied("只有有效的超级管理员可以变更 SUPER_ADMIN 授权")

    def _effective_super_admin_count(self, super_admin_role: Role) -> int:
        count = self.users.effective_super_admin_count(super_admin_role.id)
        if count < 1:
            raise ConflictError(self.LAST_SUPER_ADMIN_MESSAGE)
        return count

    def _user_conflict(self, user_id: int, message: str) -> ConflictError:
        latest = self.users.get_fresh(user_id)
        return ConflictError(
            message,
            {
                "current_revision": latest.revision if latest else None,
                "current_updated_at": latest.updated_at.isoformat() if latest else None,
                "current_updated_by": latest.updated_by if latest else None,
            },
        )

    def create(self, payload: UserCreate, operator_id: int) -> UserOut:
        password_hash = hash_password(payload.password)
        super_admin_role = self._lock_super_admin_role()
        self._effective_super_admin_count(super_admin_role)
        self._validate_role_ids(payload.role_ids)
        if super_admin_role.id in payload.role_ids:
            self._ensure_operator_is_effective_super_admin(operator_id, super_admin_role)
        if self.users.by_username(payload.username) is not None:
            raise ConflictError("用户名已存在")

        user = User(
            username=payload.username,
            display_name=payload.display_name,
            email=payload.email,
            mobile=payload.mobile,
            password_hash=password_hash,
            must_change_password=True,
            created_by=operator_id,
            updated_by=operator_id,
        )
        self.db.add(user)
        self.db.flush()
        for role_id in payload.role_ids:
            self.db.add(UserRole(user_id=user.id, role_id=role_id))
        self.db.flush()
        role_ids = self.users.role_ids(user.id)
        self.audit.log(
            "USER",
            user.id,
            "CREATE",
            after={"username": user.username, "role_ids": role_ids},
        )
        self.db.commit()
        self.db.refresh(user)
        return self._out(user)

    def update_profile(self, user_id: int, payload: UserUpdate, operator_id: int) -> UserOut:
        user = self._user_or_404(user_id)
        before = {
            "display_name": user.display_name,
            "email": user.email,
            "mobile": user.mobile,
        }
        values = payload.model_dump(exclude={"revision"}, exclude_unset=True)
        values["updated_by"] = operator_id
        if not self.users.update_with_revision(user_id, payload.revision, values):
            raise self._user_conflict(user_id, "用户已被其他用户修改")

        self.db.refresh(user)
        self.audit.log("USER", user_id, "UPDATE", before=before, after=values)
        self.db.commit()
        self.db.refresh(user)
        return self._out(user)

    def update_roles(self, user_id: int, payload: UserRoleUpdate, operator_id: int) -> UserOut:
        super_admin_role = self._lock_super_admin_role()
        user = self._user_or_404(user_id)
        self._validate_role_ids(payload.role_ids)

        before_role_ids = self.users.role_ids(user_id)
        had_super_admin = super_admin_role.id in before_role_ids
        will_have_super_admin = super_admin_role.id in payload.role_ids
        changes_super_admin = had_super_admin != will_have_super_admin
        if changes_super_admin:
            self._ensure_operator_is_effective_super_admin(operator_id, super_admin_role)

        effective_count = self._effective_super_admin_count(super_admin_role)
        removes_effective_super_admin = (
            had_super_admin
            and not will_have_super_admin
            and user.status is UserStatus.ACTIVE
            and super_admin_role.enabled
        )
        if removes_effective_super_admin and effective_count <= 1:
            raise ConflictError(self.LAST_SUPER_ADMIN_MESSAGE)

        if not self.users.update_with_revision(
            user_id,
            payload.revision,
            {"updated_by": operator_id},
        ):
            raise self._user_conflict(user_id, "用户角色已被其他用户修改")

        self.db.execute(delete(UserRole).where(UserRole.user_id == user_id))
        for role_id in payload.role_ids:
            self.db.add(UserRole(user_id=user_id, role_id=role_id))
        self.db.flush()
        after_role_ids = self.users.role_ids(user_id)
        self.db.refresh(user)
        self.audit.log(
            "USER",
            user_id,
            "ROLES_UPDATE",
            before={"role_ids": before_role_ids},
            after={"role_ids": after_role_ids},
        )
        self.db.commit()
        self.db.refresh(user)
        return self._out(user)

    def set_status(self, user_id: int, payload: UserStatusChange, operator_id: int) -> UserOut:
        super_admin_role = self._lock_super_admin_role()
        user = self._user_or_404(user_id)
        has_super_admin = self.users.has_role(user_id, super_admin_role.id)
        if has_super_admin:
            self._ensure_operator_is_effective_super_admin(operator_id, super_admin_role)

        effective_count = self._effective_super_admin_count(super_admin_role)
        removes_effective_super_admin = (
            has_super_admin
            and user.status is UserStatus.ACTIVE
            and payload.status is not UserStatus.ACTIVE
            and super_admin_role.enabled
        )
        if removes_effective_super_admin and effective_count <= 1:
            raise ConflictError(self.LAST_SUPER_ADMIN_MESSAGE)

        previous_status = user.status
        if not self.users.update_with_revision(
            user_id,
            payload.revision,
            {"status": payload.status, "updated_by": operator_id},
        ):
            raise self._user_conflict(user_id, "用户已被其他用户修改")

        revoked_sessions = 0
        if payload.status is not UserStatus.ACTIVE:
            revoked_sessions = AuthService(self.db).revoke_user_sessions(
                user_id, reason="USER_DISABLED"
            )
        self.db.refresh(user)
        self.audit.log(
            "USER",
            user_id,
            "STATUS_CHANGE",
            before={"status": previous_status},
            after={
                "status": payload.status,
                "revoked_session_count": revoked_sessions,
            },
        )
        self.db.commit()
        self.db.refresh(user)
        return self._out(user)
