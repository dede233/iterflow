from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DictionaryBase(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    enabled: bool = True


class DictionaryCreate(DictionaryBase):
    pass


class DictionaryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    enabled: bool | None = None
    revision: int = Field(ge=1)


class DictionaryOut(DictionaryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    revision: int
    created_at: datetime
    updated_at: datetime


class DictionaryItemBase(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=255)
    sort_order: int = 0
    enabled: bool = True


class DictionaryItemCreate(DictionaryItemBase):
    dictionary_id: int = Field(gt=0)


class DictionaryItemUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    value: str | None = Field(default=None, min_length=1, max_length=255)
    sort_order: int | None = None
    enabled: bool | None = None
    revision: int = Field(ge=1)


class DictionaryItemOut(DictionaryItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dictionary_id: int
    revision: int
    created_at: datetime
    updated_at: datetime
