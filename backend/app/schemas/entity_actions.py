from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator


class EntityDelete(BaseModel):
    revision: int = Field(ge=1)
    reason: str = Field(min_length=2, max_length=500)

    @model_validator(mode="after")
    def nonblank_reason(self) -> Self:
        self.reason = self.reason.strip()
        if len(self.reason) < 2:
            raise ValueError("请填写删除原因(至少 2 个字符)")
        return self


class EntityDeleted(BaseModel):
    id: int
    revision: int = Field(ge=1)
    deleted: Literal[True] = True


class BatchActionItem(BaseModel):
    id: int = Field(ge=1)
    revision: int = Field(ge=1)


class _BatchAction(BaseModel):
    items: list[BatchActionItem] = Field(min_length=1, max_length=50)
    reason: str | None = Field(default=None, min_length=2, max_length=500)

    @model_validator(mode="after")
    def unique_items(self) -> Self:
        if len({item.id for item in self.items}) != len(self.items):
            raise ValueError("批量操作不能包含重复记录")
        return self


class RequirementBatchAction(_BatchAction):
    action: Literal["CONFIRM", "DEVELOPING", "TESTING", "DONE"]


class FeedbackBatchAction(_BatchAction):
    action: Literal["ACCEPTED", "CLOSED"]


class BatchActionResult(BaseModel):
    id: int
    success: bool
    status_code: int
    code: int
    message: str
    revision: int | None


class BatchActionResponse(BaseModel):
    results: list[BatchActionResult]
