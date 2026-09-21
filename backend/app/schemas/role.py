from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import DataScope

type ConfigurableDataScope = Literal[DataScope.SELF, DataScope.ALL]


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    data_scope: DataScope
    enabled: bool
    revision: int
    permission_ids: list[int] = Field(default_factory=list)


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    category: str


class RoleCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    data_scope: ConfigurableDataScope = DataScope.SELF
    permission_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def permission_ids_must_be_unique(self) -> "RoleCreate":
        if len(self.permission_ids) != len(set(self.permission_ids)):
            raise ValueError("permission_ids must not contain duplicates")
        return self


class RoleUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=2, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    data_scope: ConfigurableDataScope | None = None
    enabled: bool | None = None
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def require_non_null_change(self) -> "RoleUpdate":
        change_fields = self.model_fields_set - {"revision"}
        if not change_fields:
            raise ValueError("at least one role field must be provided")
        if any(getattr(self, field) is None for field in change_fields):
            raise ValueError("role fields cannot be null")
        return self


class RolePermissionUpdate(BaseModel):
    permission_ids: list[int]
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def permission_ids_must_be_unique(self) -> "RolePermissionUpdate":
        if len(self.permission_ids) != len(set(self.permission_ids)):
            raise ValueError("permission_ids must not contain duplicates")
        return self
