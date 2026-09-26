from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class _CatalogCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    sort_order: int = 0

    @field_validator("code", "name")
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("编码和名称不能为空")
        return value


class BusinessSystemCreate(_CatalogCreate):
    pass


class BusinessModuleCreate(_CatalogCreate):
    pass


class _CatalogUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None
    sort_order: int | None = None
    revision: int = Field(ge=1)

    @field_validator("code", "name")
    @classmethod
    def strip_nonempty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("编码和名称不能为空")
        return value

    @model_validator(mode="after")
    def require_non_null_change(self) -> "_CatalogUpdate":
        fields = self.model_fields_set - {"revision"}
        if not fields:
            raise ValueError("至少需要修改一个字段")
        if any(getattr(self, field) is None for field in fields):
            raise ValueError("修改字段不能为 null")
        return self


class BusinessSystemUpdate(_CatalogUpdate):
    pass


class BusinessModuleUpdate(_CatalogUpdate):
    pass
