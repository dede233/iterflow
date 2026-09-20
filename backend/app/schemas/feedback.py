from pydantic import BaseModel, ConfigDict, Field


class FeedbackCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    feedback_type: str
    urgency: str = "NORMAL"
    system_id: int | None = None
    module_id: int | None = None
    description: str = Field(min_length=2)
    expected_result: str | None = None
    actual_result: str | None = None
    reproduce_steps: str | None = None


class FeedbackUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    feedback_type: str | None = None
    urgency: str | None = None
    system_id: int | None = None
    module_id: int | None = None
    description: str | None = None
    expected_result: str | None = None
    actual_result: str | None = None
    reproduce_steps: str | None = None
    revision: int = Field(ge=1)


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    feedback_no: str
    title: str
    feedback_type: str
    urgency: str
    status: str
    system_id: int | None
    module_id: int | None
    submitter_id: int
    description: str
    main_requirement_id: int | None
    revision: int


class FeedbackConvertRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    requirement_type: str
    priority: str = "P2"
    owner_id: int | None = None
    description: str
    acceptance_criteria: str | None = None
    version_id: int | None = None
    revision: int = Field(ge=1)
