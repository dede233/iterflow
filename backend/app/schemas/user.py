from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import UserStatus


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    display_name: str
    email: str | None
    mobile: str | None = None
    status: UserStatus
    revision: int
    role_ids: list[int] = Field(default_factory=list)


class UserPage(BaseModel):
    items: list[UserOut]
    page: int
    page_size: int
    total: int


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    email: str | None = None
    mobile: str | None = Field(default=None, max_length=32)
    role_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def role_ids_must_be_unique(self) -> "UserCreate":
        if len(self.role_ids) != len(set(self.role_ids)):
            raise ValueError("role_ids must not contain duplicates")
        return self


class UserUpdate(BaseModel):
    """Editable account profile fields; credentials, status, and roles have dedicated APIs."""

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    mobile: str | None = Field(default=None, max_length=32)
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def require_non_null_change(self) -> "UserUpdate":
        change_fields = self.model_fields_set - {"revision"}
        if not change_fields:
            raise ValueError("at least one user field must be provided")
        if "display_name" in change_fields and self.display_name is None:
            raise ValueError("display_name cannot be null")
        return self


class UserStatusChange(BaseModel):
    status: UserStatus
    revision: int = Field(ge=1)


class UserRoleUpdate(BaseModel):
    role_ids: list[int]
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def role_ids_must_be_unique(self) -> "UserRoleUpdate":
        if len(self.role_ids) != len(set(self.role_ids)):
            raise ValueError("role_ids must not contain duplicates")
        return self
