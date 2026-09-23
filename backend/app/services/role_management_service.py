from typing import Any, cast

from sqlalchemy import delete, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.models.entities import Role, RolePermission
from app.repositories.role_repository import RoleRepository
from app.schemas.role import RoleCreate, RoleDeleteOut, RoleOut, RolePermissionUpdate, RoleUpdate
from app.services.audit_service import AuditService


class RoleManagementService:
    """Role CRUD, permission assignment, constraints, and audit transactions."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = RoleRepository(db)
        self.audit = AuditService(db)

    def _out(self, role: Role) -> RoleOut:
        return RoleOut.model_validate(role).model_copy(
            update={"permission_ids": self.repo.permission_ids(role.id)}
        )

    def _snapshot(self, role: Role) -> dict[str, Any]:
        return self._out(role).model_dump(mode="json")

    def _role_or_404(self, role_id: int) -> Role:
        role = self.repo.get(role_id)
        if role is None:
            raise NotFoundError("角色不存在")
        return role

    @staticmethod
    def _ensure_custom_role(role: Role) -> None:
        if role.is_system:
            raise ConflictError("系统角色为只读基线, 禁止修改")

    def _validate_permission_ids(self, permission_ids: list[int]) -> None:
        existing_ids = self.repo.existing_permission_ids(permission_ids)
        missing_ids = sorted(set(permission_ids) - existing_ids)
        if missing_ids:
            raise AppError(42201, "包含不存在的权限", 422, {"permission_ids": missing_ids})

    def list(self) -> list[RoleOut]:
        return [self._out(role) for role in self.repo.list_roles()]

    def get(self, role_id: int) -> RoleOut:
        return self._out(self._role_or_404(role_id))

    def list_permissions(self):
        return self.repo.list_permissions()

    def create(self, payload: RoleCreate, operator_id: int) -> RoleOut:
        self._validate_permission_ids(payload.permission_ids)
        if self.repo.by_code(payload.code) is not None:
            raise ConflictError("角色编码已存在")
        role = Role(
            code=payload.code,
            name=payload.name,
            data_scope=payload.data_scope,
            is_system=False,
            created_by=operator_id,
            updated_by=operator_id,
        )
        self.db.add(role)
        self.db.flush()
        for permission_id in payload.permission_ids:
            self.db.add(RolePermission(role_id=role.id, permission_id=permission_id))
        self.db.flush()
        self.audit.log("ROLE", role.id, "ROLE_CREATE", after=self._snapshot(role))
        self.db.commit()
        self.db.refresh(role)
        return self._out(role)

    def update(self, role_id: int, payload: RoleUpdate, operator_id: int) -> RoleOut:
        role = self._role_or_404(role_id)
        self._ensure_custom_role(role)
        before = self._snapshot(role)
        values = payload.model_dump(exclude={"revision"}, exclude_unset=True)
        if "code" in values:
            same_code_role = self.repo.by_code(values["code"])
            if same_code_role is not None and same_code_role.id != role_id:
                raise ConflictError("角色编码已存在")
        values["updated_by"] = operator_id
        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(Role)
                .where(Role.id == role_id, Role.revision == payload.revision)
                .values(**values, revision=Role.revision + 1)
            ),
        )
        if not result.rowcount:
            self.db.refresh(role)
            raise ConflictError("角色已被其他用户修改", {"current_revision": role.revision})
        self.db.refresh(role)
        self.audit.log("ROLE", role_id, "ROLE_UPDATE", before=before, after=self._snapshot(role))
        self.db.commit()
        self.db.refresh(role)
        return self._out(role)

    def update_permissions(
        self, role_id: int, payload: RolePermissionUpdate, operator_id: int
    ) -> RoleOut:
        role = self._role_or_404(role_id)
        self._ensure_custom_role(role)
        self._validate_permission_ids(payload.permission_ids)
        before = self._snapshot(role)
        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(Role)
                .where(Role.id == role_id, Role.revision == payload.revision)
                .values(updated_by=operator_id, revision=Role.revision + 1)
            ),
        )
        if not result.rowcount:
            self.db.refresh(role)
            raise ConflictError("角色权限已被其他用户修改", {"current_revision": role.revision})
        self.db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        for permission_id in payload.permission_ids:
            self.db.add(RolePermission(role_id=role_id, permission_id=permission_id))
        self.db.flush()
        self.db.refresh(role)
        self.audit.log(
            "ROLE",
            role_id,
            "ROLE_PERMISSION_UPDATE",
            before=before,
            after=self._snapshot(role),
        )
        self.db.commit()
        self.db.refresh(role)
        return self._out(role)

    def delete(self, role_id: int, operator_id: int) -> RoleDeleteOut:
        role = self._role_or_404(role_id)
        self._ensure_custom_role(role)
        user_count = self.repo.user_count(role_id)
        if user_count:
            raise ConflictError("角色已分配给用户, 无法删除", {"user_count": user_count})
        before = self._snapshot(role)
        self.db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        self.db.delete(role)
        self.audit.log("ROLE", role_id, "ROLE_DELETE", before=before, after=None)
        self.db.commit()
        return RoleDeleteOut(id=role_id)
