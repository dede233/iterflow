from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

ParticipantRole = Literal["CONFIRM", "DESIGN", "DEVELOP", "ACCEPT"]


class PersonOption(BaseModel):
    id: int
    display_name: str


class PersonPage(BaseModel):
    items: list[PersonOption]
    total: int
    page: int
    page_size: int


class ParticipantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(gt=0)
    role: ParticipantRole


class ParticipantOut(ParticipantInput):
    display_name: str
    active: bool


class ParticipantsChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    participants: list[ParticipantInput] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_roles(self) -> Self:
        pairs = [(p.user_id, p.role) for p in self.participants]
        if len(set(pairs)) != len(pairs):
            raise ValueError("人员与环节不能重复")
        if sum(p.role == "CONFIRM" for p in self.participants) > 1:
            raise ValueError("需求确认人最多一位")
        return self


class ParticipantsOut(BaseModel):
    revision: int
    participants: list[ParticipantOut]


class RecipientsChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    recipient_ids: list[int] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_recipients(self) -> Self:
        if len(set(self.recipient_ids)) != len(self.recipient_ids):
            raise ValueError("接收人不能重复")
        if any(user_id <= 0 for user_id in self.recipient_ids):
            raise ValueError("接收人 ID 必须为正整数")
        return self


class FeedbackCollaborationOut(BaseModel):
    revision: int
    recipients: list[PersonOption]
    handler_id: int | None
    accepted_by: int | None
    accepted_at: datetime | None


class FeedbackTransfer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    handler_id: int = Field(gt=0)
    reason: str = Field(min_length=2, max_length=500)
