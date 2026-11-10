from datetime import datetime
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator

from app.schemas.release import OffsetISODatetime

TargetPlatform = Literal["PC_WEB", "WECHAT_MINI_PROGRAM", "ALIPAY_MINI_PROGRAM"]
BatchKind = Literal["INITIAL", "SUPPLEMENT", "REPUBLISH"]
BatchStatus = Literal["PLANNED", "IN_PROGRESS", "COMPLETED", "CANCELED"]


class TargetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def clean_text(cls, value):
        if isinstance(value, str):
            if "\x00" in value:
                raise ValueError("文本不能包含 NUL")
            value = value.strip()
        return value


class ReleaseTargetCreate(TargetRequest):
    code: str = Field(min_length=1, max_length=64, title="目标编码")
    name: str = Field(min_length=1, max_length=100, title="目标名称")
    platform: TargetPlatform = Field(title="平台类型")
    app_id: str | None = Field(default=None, max_length=64, title="小程序 AppID")
    url: str | None = Field(default=None, max_length=500, title="访问地址")
    enabled: bool = Field(default=True, title="是否启用")

    @field_validator("url")
    @classmethod
    def public_http_url(cls, value):
        if value:
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
            ):
                raise ValueError("访问地址必须是 http/https 地址, 不能包含登录凭据")
        return value or None


class ReleaseTargetUpdate(TargetRequest):
    revision: int = Field(ge=1, title="修订号")
    code: str | None = Field(default=None, min_length=1, max_length=64, title="目标编码")
    name: str | None = Field(default=None, min_length=1, max_length=100, title="目标名称")
    platform: TargetPlatform | None = Field(default=None, title="平台类型")
    app_id: str | None = Field(default=None, max_length=64, title="小程序 AppID")
    url: str | None = Field(default=None, max_length=500, title="访问地址")
    enabled: bool | None = Field(default=None, title="是否启用")

    @field_validator("url")
    @classmethod
    def public_http_url(cls, value):
        return ReleaseTargetCreate.public_http_url(value)

    @model_validator(mode="after")
    def changed(self) -> Self:
        fields = self.model_fields_set - {"revision"}
        if not fields or any(getattr(self, k) is None for k in fields - {"app_id", "url"}):
            raise ValueError("请提供有效的修改内容")
        return self


class ReleaseTargetOut(BaseModel):
    covered: bool = Field(default=False, title="版本已覆盖该目标")
    pending: bool = Field(default=False, title="版本已有未完成目标计划")
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(title="目标 ID")
    system_id: int = Field(title="业务系统 ID")
    code: str = Field(title="目标编码")
    name: str = Field(title="目标名称")
    platform: TargetPlatform = Field(title="平台类型")
    app_id: str | None = Field(title="小程序 AppID")
    url: str | None = Field(title="访问地址")
    enabled: bool = Field(title="是否启用")
    revision: int = Field(title="修订号")
    created_at: datetime = Field(title="创建时间")
    updated_at: datetime = Field(title="更新时间")


class ReleaseBatchCreate(TargetRequest):
    version_revision: int = Field(ge=1, title="版本修订号")
    kind: BatchKind = Field(title="批次类型")
    system_id: int | None = Field(default=None, ge=1, title="历史版本补发业务系统 ID")
    target_ids: list[PositiveInt] = Field(min_length=1, max_length=50, title="计划目标 ID")
    release_notes: str = Field(min_length=2, max_length=5000, title="发布说明")
    reason: str | None = Field(default=None, min_length=2, max_length=500, title="重新发布原因")

    @field_validator("target_ids")
    @classmethod
    def distinct_targets(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("发布目标不能重复")
        return value

    @model_validator(mode="after")
    def republish_reason(self) -> Self:
        if self.kind == "REPUBLISH" and not self.reason:
            raise ValueError("重新发布必须填写原因")
        return self


class ReleaseCoverageCreate(TargetRequest):
    version_revision: int = Field(ge=1, title="版本修订号")
    system_id: int | None = Field(default=None, ge=1, title="历史版本目标所属业务系统 ID")
    target_ids: list[PositiveInt] = Field(min_length=1, max_length=50, title="已发布目标 ID")
    released_at: OffsetISODatetime = Field(title="实际上线时间")
    notes: str | None = Field(default=None, max_length=5000, title="发布说明")
    evidence: str | None = Field(default=None, max_length=1000, title="凭证说明或链接")

    @field_validator("target_ids")
    @classmethod
    def distinct_targets(cls, value):
        return ReleaseBatchCreate.distinct_targets(value)


class ReleaseBatchAdjust(TargetRequest):
    version_revision: int = Field(ge=1, title="版本修订号")
    revision: int = Field(ge=1, title="批次修订号")
    target_ids: list[PositiveInt] = Field(min_length=1, max_length=50, title="调整后目标 ID")
    reason: str = Field(min_length=2, max_length=500, title="调整原因")

    @field_validator("target_ids")
    @classmethod
    def distinct_targets(cls, value):
        return ReleaseBatchCreate.distinct_targets(value)


class ReleaseBatchCancel(TargetRequest):
    version_revision: int = Field(ge=1, title="版本修订号")
    revision: int = Field(ge=1, title="批次修订号")
    reason: str = Field(min_length=2, max_length=500, title="取消原因")


class ReleaseTargetComplete(TargetRequest):
    version_revision: int = Field(ge=1, title="版本修订号")
    batch_revision: int = Field(ge=1, title="批次修订号")
    revision: int = Field(ge=1, title="目标修订号")
    released_at: OffsetISODatetime = Field(title="实际上线时间")
    notes: str | None = Field(default=None, max_length=5000, title="目标发布说明")
    evidence: str | None = Field(default=None, max_length=1000, title="凭证说明或链接")


class ReleaseBatchTargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(title="批次目标 ID")
    target_id: int = Field(title="发布目标 ID")
    name: str = Field(title="计划目标名称快照")
    code: str = Field(title="计划目标编码快照")
    platform: TargetPlatform = Field(title="平台快照")
    app_id: str | None = Field(title="AppID 快照")
    url: str | None = Field(title="访问地址快照")
    active: bool = Field(title="仍在计划中")
    removed_reason: str | None = Field(title="移除原因")
    completed_at: datetime | None = Field(title="实际上线时间")
    recorded_at: datetime | None = Field(title="系统登记时间")
    completed_by: int | None = Field(title="实际登记人 ID")
    operator_name: str | None = Field(title="登记人名称快照")
    notes: str | None = Field(title="目标发布说明")
    evidence: str | None = Field(title="凭证说明或链接")
    revision: int = Field(title="目标修订号")


class ReleaseBatchOut(BaseModel):
    id: int = Field(title="批次 ID")
    version_id: int = Field(title="版本 ID")
    system_id: int = Field(title="业务系统 ID")
    kind: BatchKind = Field(title="批次类型")
    status: BatchStatus = Field(title="批次状态")
    release_notes: str = Field(title="发布说明")
    reason: str | None = Field(title="重新发布原因")
    release_id: int | None = Field(title="原整体发布记录 ID")
    revision: int = Field(title="批次修订号")
    version_revision: int = Field(title="版本修订号")
    created_at: datetime = Field(title="计划创建时间")
    updated_at: datetime = Field(title="最近登记时间")
    total: int = Field(title="当前计划目标数")
    completed: int = Field(title="已完成目标数")
    targets: list[ReleaseBatchTargetOut] = Field(title="计划及实际目标记录")


class ReleaseBatchesOut(BaseModel):
    version_id: int = Field(title="版本 ID")
    version_revision: int = Field(title="版本修订号")
    system_id: int | None = Field(title="有效发布系统 ID")
    release_frozen: bool = Field(title="首次发布内容已冻结")
    legacy_unrecorded: bool = Field(title="原整体发布未记录目标")
    coverage_count: int = Field(title="累计实际覆盖目标数")
    items: list[ReleaseBatchOut] = Field(title="发布批次")
    page: int = Field(title="页码")
    page_size: int = Field(title="每页数量")
    total: int = Field(title="批次总数")


class TargetReleaseRecordOut(ReleaseBatchTargetOut):
    version_id: int = Field(title="版本 ID")
    version_no: str = Field(title="版本号")
    version_name: str = Field(title="版本名称")
    system_id: int = Field(title="业务系统 ID")
    batch_id: int = Field(title="批次 ID")
    batch_kind: BatchKind = Field(title="批次类型")


class TargetReleasePage(BaseModel):
    items: list[TargetReleaseRecordOut] = Field(title="实际发布记录")
    page: int = Field(title="页码")
    page_size: int = Field(title="每页数量")
    total: int = Field(title="总记录数")


class TargetReleaseOption(BaseModel):
    id: int = Field(title="发布目标 ID")
    label: str = Field(title="目标显示名称")
