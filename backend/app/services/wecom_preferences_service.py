from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDenied
from app.models.entities import Role, User, WecomPreference
from app.models.enums import DataScope, UserStatus
from app.repositories.user_repository import UserRepository
from app.schemas.wecom import WecomMode, WecomPreferencesOut
from app.services.audit_service import AuditService


class WecomPreferencesService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    @staticmethod
    def _bound_for_corp(item: WecomPreference | None, corp_id: str) -> WecomPreference | None:
        if corp_id and item and item.corp_id == corp_id and item.member_user_id and item.binding_id:
            return item
        return None

    @classmethod
    def _view(cls, item: WecomPreference | None) -> WecomPreferencesOut:
        settings = get_settings()
        binding = cls._bound_for_corp(item, settings.wecom_corp_id.strip())
        return WecomPreferencesOut(
            revision=item.revision if item else 0,
            member_user_id=binding.member_user_id if binding else None,
            mode=cast(WecomMode, binding.mode) if binding else "OFF",
            enabled=settings.wecom_enabled,
        )

    def get(self, user_id: int) -> WecomPreferencesOut:
        return self._view(self.db.get(WecomPreference, user_id))

    def _check_binding_admin(self, operator_id: int, *, lock: bool) -> DataScope:
        if lock:
            role = self.users.get_super_admin_role_for_update()
            role_id = role.id if role else None
        else:
            role_id = self.db.scalar(
                select(Role.id).where(Role.code == "SUPER_ADMIN", Role.is_system.is_(True))
            )
        permissions = self.users.permission_codes(operator_id)
        scope = self.users.data_scope(operator_id)
        if (
            role_id is None
            or not self.users.is_effective_super_admin(operator_id, role_id)
            or permissions.isdisjoint({"*", "sys.user.edit"})
            or scope is not DataScope.ALL
        ):
            raise PermissionDenied("仅具有 ALL 数据范围的有效超级管理员可管理企业微信绑定")
        return scope

    def get_binding(self, operator_id: int, user_id: int) -> WecomPreferencesOut:
        scope = self._check_binding_admin(operator_id, lock=False)
        if not self.users.get_scoped(user_id, operator_id, scope):
            raise NotFoundError("用户不存在")
        return self.get(user_id)

    def _lock_preference(self, user_id: int, revision: int) -> WecomPreference | None:
        item = self.db.get(WecomPreference, user_id, with_for_update=True, populate_existing=True)
        current_revision = item.revision if item else 0
        if revision != current_revision:
            raise self._revision_conflict(current_revision)
        return item

    @staticmethod
    def _revision_conflict(current_revision: int) -> ConflictError:
        return ConflictError(
            "企业微信设置已修改, 请刷新后重试", {"current_revision": current_revision}
        )

    def _save(self, user_id: int, revision: int, **changes: Any) -> WecomPreferencesOut:
        if revision == 0:
            self.db.add(WecomPreference(user_id=user_id, revision=1, **changes))
        else:
            result = cast(
                CursorResult[Any],
                self.db.execute(
                    update(WecomPreference)
                    .where(WecomPreference.user_id == user_id, WecomPreference.revision == revision)
                    .values(**changes, revision=WecomPreference.revision + 1)
                ),
            )
            if not result.rowcount:
                current = self.db.get(WecomPreference, user_id, populate_existing=True)
                raise self._revision_conflict(current.revision if current else 0)
        self.db.flush()
        view = self._view(self.db.get(WecomPreference, user_id, populate_existing=True))
        self.db.commit()
        return view

    def change(self, user_id: int, revision: int, mode: WecomMode) -> WecomPreferencesOut:
        user = self.db.get(User, user_id, with_for_update=True, populate_existing=True)
        if not user or user.status is not UserStatus.ACTIVE:
            raise AppError(40103, "用户不可用", 401)
        item = self._lock_preference(user_id, revision)
        binding = self._bound_for_corp(item, get_settings().wecom_corp_id.strip())
        if mode != "OFF" and not binding:
            raise ConflictError("请先由超级管理员绑定企业微信成员", code=40901)
        previous_mode = item.mode if item else "OFF"
        eligible_since = item.eligible_since if item else None
        if mode != previous_mode:
            eligible_since = datetime.now(UTC) if mode != "OFF" else None
        AuditService(self.db).log(
            "USER",
            user_id,
            "WECOM_PREFERENCE",
            before={"mode": previous_mode},
            after={"mode": mode},
        )
        return self._save(user_id, revision, mode=mode, eligible_since=eligible_since)

    def change_binding(
        self, operator_id: int, user_id: int, revision: int, member_user_id: str | None
    ) -> WecomPreferencesOut:
        self._check_binding_admin(operator_id, lock=True)
        user = self.db.get(User, user_id, with_for_update=True, populate_existing=True)
        if not user:
            raise NotFoundError("用户不存在")
        item = self._lock_preference(user_id, revision)
        previous_member = item.member_user_id if item else None
        previous_corp = item.corp_id if item else None
        corp_id = get_settings().wecom_corp_id.strip() if member_user_id is not None else None
        if corp_id is not None and (not corp_id or len(corp_id) > 128):
            raise ConflictError("请先配置有效的企业微信企业 ID", code=40901)
        changes: dict[str, Any] = {}
        if (previous_corp, previous_member) != (corp_id, member_user_id):
            if member_user_id is not None and user.status is not UserStatus.ACTIVE:
                raise ConflictError("账号已停用", code=40901)
            member_key = member_user_id.lower() if member_user_id else None
            # The SUPER_ADMIN role lock serializes all writes that can claim a member key.
            if (
                member_key is not None
                and self.db.scalar(
                    select(WecomPreference.user_id).where(
                        WecomPreference.corp_id == corp_id,
                        WecomPreference.member_key == member_key,
                        WecomPreference.user_id != user_id,
                    )
                )
                is not None
            ):
                raise ConflictError("该企业微信成员无法绑定", code=40901)
            changes = {
                "corp_id": corp_id,
                "member_user_id": member_user_id,
                "member_key": member_key,
                "binding_id": str(uuid4()) if member_user_id else None,
                "mode": "OFF",
                "eligible_since": None,
            }
        AuditService(self.db).log(
            "USER",
            user_id,
            "WECOM_BINDING",
            before={"bound": previous_member is not None},
            after={"bound": member_user_id is not None, "changed": bool(changes)},
        )
        return self._save(user_id, revision, **changes)
