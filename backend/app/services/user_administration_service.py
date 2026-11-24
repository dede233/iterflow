from datetime import UTC, datetime

from sqlalchemy import delete, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDenied
from app.core.security import hash_password
from app.models.entities import MailPreference, Role, User, UserRole
from app.models.enums import UserStatus
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    EmailVerificationStatus,
    InvitationResult,
    UserCreate,
    UserCreated,
    UserOut,
    UserRoleUpdate,
    UserStatusChange,
    UserUpdate,
)
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.mail_preferences_service import (
    MailPreferencesService,
    current_email_challenge_id,
    current_email_verified_at,
)


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

    @staticmethod
    def _verification_status(
        user: User, record: tuple[MailPreference, str | None] | None, now: datetime
    ) -> EmailVerificationStatus:
        if not user.email:
            return "NO_EMAIL"
        if record is None:
            return "UNVERIFIED"
        preference, delivery = record
        if current_email_verified_at(user.email, preference) is not None:
            return "VERIFIED"
        if (
            not preference.challenge_id
            or preference.pending_email != user.email
            or preference.challenge_user_revision != user.revision
        ):
            return "UNVERIFIED"
        if delivery in {"FAILED", "SKIPPED"}:
            return "FAILED"
        if current_email_challenge_id(preference, user.revision, now):
            return "PENDING"
        return "UNVERIFIED"

    def present_users(self, users: list[User]) -> list[UserOut]:
        roles = self.users.role_ids_by_user([user.id for user in users])
        verification = self.users.verification_records([user.id for user in users if user.email])
        now = datetime.now(UTC)
        return [
            UserOut.model_validate(user).model_copy(
                update={
                    "role_ids": roles[user.id],
                    "email_verification_status": self._verification_status(
                        user, verification.get(user.id), now
                    ),
                }
            )
            for user in users
        ]

    def _out(self, user: User) -> UserOut:
        return self.present_users([user])[0]

    def invite_email(self, user_id: int, revision: int, operator_id: int) -> None:
        role = self._lock_super_admin_role()
        if not self.users.is_effective_super_admin(operator_id, role.id):
            raise PermissionDenied("仅有效的超级管理员可发送邮箱确认邮件")
        user = self._user_or_404(user_id)
        MailPreferencesService(self.db).invite(user, revision, operator_id)

    def _lock_super_admin_role(self) -> Role:
        role = self.users.get_super_admin_role_for_update()
        if role is None:
            raise ConflictError("SUPER_ADMIN 系统角色不存在或配置异常", code=40901)
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
            raise ConflictError(self.LAST_SUPER_ADMIN_MESSAGE, code=40901)
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

    def create(self, payload: UserCreate, operator_id: int) -> UserCreated:
        password_hash = hash_password(payload.password)
        super_admin_role = self._lock_super_admin_role()
        self._effective_super_admin_count(super_admin_role)
        self._validate_role_ids(payload.role_ids)
        if super_admin_role.id in payload.role_ids:
            self._ensure_operator_is_effective_super_admin(operator_id, super_admin_role)
        if self.users.by_username(payload.username) is not None:
            raise ConflictError("用户名已存在", code=40901)

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
        invitation: InvitationResult = "SKIPPED"
        if (
            user.email
            and get_settings().smtp_enabled
            and self.users.is_effective_super_admin(operator_id, super_admin_role.id)
        ):
            try:
                with self.db.begin_nested():
                    MailPreferencesService(self.db).invite(
                        user, user.revision, operator_id, commit=False
                    )
                invitation = "QUEUED"
            except (AppError, SQLAlchemyError):
                # Roll back the invitation only. The administrator can retry on this account.
                invitation = "FAILED"
        self.db.commit()
        self.db.refresh(user)
        return UserCreated(**self._out(user).model_dump(), verification_invitation=invitation)

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

        if "email" in values and values["email"] != before["email"]:
            # Email ownership never survives an administrative address change,
            # including changing away and later restoring a previously verified address.
            self.db.execute(
                update(MailPreference)
                .where(MailPreference.user_id == user_id)
                .values(
                    verified_email=None,
                    verified_at=None,
                    pending_email=None,
                    challenge_id=None,
                    challenge_expires_at=None,
                    revision=MailPreference.revision + 1,
                )
            )
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
            raise ConflictError(self.LAST_SUPER_ADMIN_MESSAGE, code=40901)

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
            raise ConflictError(self.LAST_SUPER_ADMIN_MESSAGE, code=40901)

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
