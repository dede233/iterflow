from __future__ import annotations

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.entities import BusinessModule, BusinessSystem
from app.repositories.system_catalog_repository import SystemCatalogRepository
from app.schemas.system import (
    BusinessModuleCreate,
    BusinessModuleOut,
    BusinessModuleUpdate,
    BusinessSystemCatalogOut,
    BusinessSystemCreate,
    BusinessSystemOut,
    BusinessSystemUpdate,
)
from app.services.audit_service import AuditService


class SystemCatalogService:
    """Manage selectable business systems and modules without deleting historical references."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = SystemCatalogRepository(db)
        self.audit = AuditService(db)

    def list_all(self) -> BusinessSystemCatalogOut:
        return BusinessSystemCatalogOut.model_validate(self.repo.list_all())

    @staticmethod
    def _system_out(item: BusinessSystem) -> BusinessSystemOut:
        return BusinessSystemOut.model_validate(item)

    @staticmethod
    def _module_out(item: BusinessModule) -> BusinessModuleOut:
        return BusinessModuleOut.model_validate(item)

    @staticmethod
    def _conflict_data(item: BusinessSystem | BusinessModule | None) -> dict[str, Any]:
        if item is None:
            return {"current_revision": None}
        return {
            "current_revision": item.revision,
            "current_updated_at": item.updated_at.isoformat(),
            "current_updated_by": item.updated_by,
            "latest": {
                "id": item.id,
                "code": item.code,
                "name": item.name,
                "enabled": item.enabled,
            },
        }

    def create_system(self, payload: BusinessSystemCreate, operator_id: int) -> BusinessSystemOut:
        if self.repo.system_by_code(payload.code):
            raise ConflictError("系统编码已存在")
        item = BusinessSystem(
            **payload.model_dump(), created_by=operator_id, updated_by=operator_id
        )
        try:
            self.db.add(item)
            self.db.flush()
            result = self._system_out(item)
            self.audit.log(
                "BUSINESS_SYSTEM", item.id, "SYSTEM_CREATE", after=result.model_dump(mode="json")
            )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("系统编码已存在") from exc
        self.db.refresh(item)
        return self._system_out(item)

    def update_system(
        self, system_id: int, payload: BusinessSystemUpdate, operator_id: int
    ) -> BusinessSystemOut:
        item = self.db.get(BusinessSystem, system_id)
        if item is None:
            raise NotFoundError("业务系统不存在")
        before = self._system_out(item).model_dump(mode="json")
        changes = payload.model_dump(exclude={"revision"}, exclude_unset=True)
        if "code" in changes:
            existing = self.repo.system_by_code(changes["code"])
            if existing is not None and existing.id != system_id:
                raise ConflictError("系统编码已存在")
        try:
            changed = self.repo.update_system(
                system_id, payload.revision, changes | {"updated_by": operator_id}
            )
            if not changed:
                self.db.rollback()
                latest = self.db.get(BusinessSystem, system_id)
                raise ConflictError("业务系统已被其他用户修改", self._conflict_data(latest))
            self.db.refresh(item)
            result = self._system_out(item)
            self.audit.log(
                "BUSINESS_SYSTEM",
                system_id,
                "SYSTEM_UPDATE",
                before=before,
                after=result.model_dump(mode="json"),
            )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("系统编码已存在") from exc
        self.db.refresh(item)
        return self._system_out(item)

    def create_module(
        self, system_id: int, payload: BusinessModuleCreate, operator_id: int
    ) -> BusinessModuleOut:
        if self.db.get(BusinessSystem, system_id) is None:
            raise NotFoundError("所属系统不存在")
        if self.repo.module_by_code(system_id, payload.code):
            raise ConflictError("该系统下的模块编码已存在")
        item = BusinessModule(
            system_id=system_id,
            **payload.model_dump(),
            created_by=operator_id,
            updated_by=operator_id,
        )
        try:
            self.db.add(item)
            self.db.flush()
            result = self._module_out(item)
            self.audit.log(
                "BUSINESS_MODULE", item.id, "MODULE_CREATE", after=result.model_dump(mode="json")
            )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("该系统下的模块编码已存在") from exc
        self.db.refresh(item)
        return self._module_out(item)

    def update_module(
        self, module_id: int, payload: BusinessModuleUpdate, operator_id: int
    ) -> BusinessModuleOut:
        item = self.db.get(BusinessModule, module_id)
        if item is None:
            raise NotFoundError("业务模块不存在")
        before = self._module_out(item).model_dump(mode="json")
        changes = payload.model_dump(exclude={"revision"}, exclude_unset=True)
        if "code" in changes:
            existing = self.repo.module_by_code(item.system_id, changes["code"])
            if existing is not None and existing.id != module_id:
                raise ConflictError("该系统下的模块编码已存在")
        try:
            changed = self.repo.update_module(
                module_id, payload.revision, changes | {"updated_by": operator_id}
            )
            if not changed:
                self.db.rollback()
                latest = self.db.get(BusinessModule, module_id)
                raise ConflictError("业务模块已被其他用户修改", self._conflict_data(latest))
            self.db.refresh(item)
            result = self._module_out(item)
            self.audit.log(
                "BUSINESS_MODULE",
                module_id,
                "MODULE_UPDATE",
                before=before,
                after=result.model_dump(mode="json"),
            )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("该系统下的模块编码已存在") from exc
        self.db.refresh(item)
        return self._module_out(item)
