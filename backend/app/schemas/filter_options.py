from pydantic import BaseModel, Field

from app.schemas.common import PageResult


class FilterOption(BaseModel):
    id: int = Field(title="选项 ID")
    label: str = Field(title="显示名称")


class FilterOptionPage(PageResult[FilterOption]):
    pass
