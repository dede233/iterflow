from pydantic import BaseModel, ConfigDict, Field


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    data_scope: str
    enabled: bool


class RoleCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    data_scope: str = "ALL"
    permission_ids: list[int] = []


class RolePermissionUpdate(BaseModel):
    permission_ids: list[int]
    revision: int = Field(ge=1)
