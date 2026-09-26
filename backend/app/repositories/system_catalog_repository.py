from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.models.entities import BusinessModule, BusinessSystem


class SystemCatalogRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_all(self) -> dict[str, list[BusinessSystem] | list[BusinessModule]]:
        systems = self.db.scalars(
            select(BusinessSystem).order_by(BusinessSystem.sort_order, BusinessSystem.id)
        ).all()
        modules = self.db.scalars(
            select(BusinessModule).order_by(
                BusinessModule.system_id, BusinessModule.sort_order, BusinessModule.id
            )
        ).all()
        return {"systems": list(systems), "modules": list(modules)}

    def system_by_code(self, code: str) -> BusinessSystem | None:
        return self.db.scalar(select(BusinessSystem).where(BusinessSystem.code == code))

    def module_by_code(self, system_id: int, code: str) -> BusinessModule | None:
        return self.db.scalar(
            select(BusinessModule).where(
                BusinessModule.system_id == system_id, BusinessModule.code == code
            )
        )

    def update_system(self, system_id: int, revision: int, values: dict[str, Any]) -> bool:
        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(BusinessSystem)
                .where(BusinessSystem.id == system_id, BusinessSystem.revision == revision)
                .values(**values, revision=BusinessSystem.revision + 1)
            ),
        )
        return bool(result.rowcount)

    def update_module(self, module_id: int, revision: int, values: dict[str, Any]) -> bool:
        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(BusinessModule)
                .where(BusinessModule.id == module_id, BusinessModule.revision == revision)
                .values(**values, revision=BusinessModule.revision + 1)
            ),
        )
        return bool(result.rowcount)
