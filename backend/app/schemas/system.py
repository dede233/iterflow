from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BusinessSystemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    enabled: bool
    sort_order: int
    created_at: datetime
    created_by: int | None
    updated_at: datetime
    updated_by: int | None
    revision: int


class BusinessModuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    system_id: int
    code: str
    name: str
    enabled: bool
    sort_order: int
    created_at: datetime
    created_by: int | None
    updated_at: datetime
    updated_by: int | None
    revision: int


class BusinessSystemCatalogOut(BaseModel):
    systems: list[BusinessSystemOut]
    modules: list[BusinessModuleOut]
