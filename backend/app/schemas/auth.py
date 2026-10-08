from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DataScope, UserStatus


class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    must_change_password: bool


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutResponse(BaseModel):
    ok: bool = True


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=6, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AuthMe(BaseModel):
    """The safe account shape returned only for the authenticated user."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    email: str | None
    status: UserStatus
    revision: int
    must_change_password: bool
    data_scope: DataScope
    role_ids: list[int]
    permission_codes: list[str]
    can_view_api_docs: bool = Field(
        default=False,
        description="当前账号是否具有启用的系统超级管理员或研发负责人角色。后端在每次读取文档时重新校验。",
    )
