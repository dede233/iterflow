from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import BusinessModule, BusinessSystem


class SystemQueryService:
    def __init__(self, db: Session):
        self.db = db

    def list_enabled(self) -> dict[str, list[BusinessSystem] | list[BusinessModule]]:
        systems = self.db.scalars(
            select(BusinessSystem)
            .where(BusinessSystem.enabled.is_(True))
            .order_by(BusinessSystem.sort_order)
        ).all()
        modules = self.db.scalars(
            select(BusinessModule)
            .join(BusinessSystem, BusinessModule.system_id == BusinessSystem.id)
            .where(BusinessModule.enabled.is_(True), BusinessSystem.enabled.is_(True))
            .order_by(BusinessModule.system_id, BusinessModule.sort_order)
        ).all()
        return {"systems": list(systems), "modules": list(modules)}
