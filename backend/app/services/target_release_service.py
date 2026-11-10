from datetime import UTC, datetime, timedelta
from functools import wraps

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDenied
from app.models.entities import (
    BusinessSystem,
    Release,
    ReleaseBatch,
    ReleaseBatchTarget,
    ReleaseTarget,
    User,
    Version,
)
from app.models.enums import DataScope
from app.repositories.base import BaseRepository
from app.repositories.user_repository import UserRepository
from app.repositories.version_repository import VersionRepository
from app.schemas.target_release import ReleaseBatchOut, ReleaseBatchTargetOut, ReleaseTargetOut
from app.services.audit_service import AuditService
from app.services.revision_conflict import revision_conflict_data
from app.services.system_binding_service import SystemBindingService

MINI_PROGRAM_SUFFIXES = {"WECHAT_MINI_PROGRAM": "_WX", "ALIPAY_MINI_PROGRAM": "_ALIPAY"}


def transactional(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception:
            self.db.rollback()
            raise

    return call


class TargetReleaseService:
    """Catalog writes lock system then targets; coverage locks version, batch, targets."""

    def __init__(self, db: Session):
        self.db = db

    def manager(self, actor_id: int):
        users = UserRepository(self.db)
        codes = users.permission_codes(actor_id)
        if ("*" not in codes and "sys.system.manage" not in codes) or users.data_scope(
            actor_id
        ) is not DataScope.ALL:
            raise PermissionDenied()

    def catalog(self, system_id: int, actor_id: int):
        self.manager(actor_id)
        if self.db.get(BusinessSystem, system_id) is None:
            raise NotFoundError("业务系统不存在")
        return list(
            self.db.scalars(
                select(ReleaseTarget)
                .where(ReleaseTarget.system_id == system_id)
                .order_by(ReleaseTarget.id)
            )
        )

    @transactional
    def create_target(self, system_id, payload, actor_id):
        self.manager(actor_id)
        self.db.scalar(
            select(BusinessSystem).where(BusinessSystem.id == system_id).with_for_update()
        )
        SystemBindingService(self.db).validate_catalog(system_id)
        item = ReleaseTarget(
            system_id=system_id, created_by=actor_id, updated_by=actor_id, **payload.model_dump()
        )
        self.db.add(item)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            raise AppError(40981, "该业务系统内的发布目标编码已存在", 409) from None
        AuditService(self.db).log(
            "SYSTEM",
            system_id,
            "RELEASE_TARGET_CREATE",
            after={"target_id": item.id, "name": item.name},
        )
        self.db.commit()
        return item

    @transactional
    def update_target(self, ident, payload, actor_id):
        self.manager(actor_id)
        original = self.db.get(ReleaseTarget, ident)
        if original is None:
            raise NotFoundError("发布目标不存在")
        self.db.scalar(
            select(BusinessSystem).where(BusinessSystem.id == original.system_id).with_for_update()
        )
        item = self.db.scalar(
            select(ReleaseTarget)
            .where(ReleaseTarget.id == ident)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if item is None:
            raise NotFoundError("发布目标不存在")
        if len(self.mini_program_members(item)) > 1:
            raise AppError(40982, "该目标属于多平台小程序, 请刷新后在品牌表单中统一编辑", 409)
        self.check_revision(item, payload.revision)
        values = payload.model_dump(exclude_unset=True, exclude={"revision"})
        try:
            self.cas(item, payload.revision, values, actor_id)
        except IntegrityError:
            self.db.rollback()
            raise AppError(40981, "该业务系统内的发布目标编码已存在", 409) from None
        AuditService(self.db).log(
            "SYSTEM", item.system_id, "RELEASE_TARGET_UPDATE", after={"target_id": ident, **values}
        )
        self.db.commit()
        self.db.refresh(item)
        return item

    def mini_program_members(self, item):
        suffix = MINI_PROGRAM_SUFFIXES.get(item.platform)
        if not suffix or not item.code.endswith(suffix) or len(item.code) == len(suffix):
            return [item]
        prefix = item.code[: -len(suffix)]
        candidates = self.db.scalars(
            select(ReleaseTarget)
            .where(
                ReleaseTarget.system_id == item.system_id,
                ReleaseTarget.code.in_([prefix + s for s in MINI_PROGRAM_SUFFIXES.values()]),
            )
            .order_by(ReleaseTarget.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return [
            row
            for row in candidates
            if row.name == item.name
            and row.platform in MINI_PROGRAM_SUFFIXES
            and row.code == prefix + MINI_PROGRAM_SUFFIXES[row.platform]
        ]

    @transactional
    def save_mini_program(self, system_id, payload, actor_id, target_id=None):
        self.manager(actor_id)
        if target_id is not None:
            original = self.db.get(ReleaseTarget, target_id)
            if original is None:
                raise NotFoundError("发布目标不存在")
            system_id = original.system_id
        self.db.scalar(
            select(BusinessSystem).where(BusinessSystem.id == system_id).with_for_update()
        )
        SystemBindingService(self.db).validate_catalog(system_id)
        members = []
        if target_id is not None:
            original = self.db.scalar(
                select(ReleaseTarget)
                .where(ReleaseTarget.id == target_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if original.platform not in MINI_PROGRAM_SUFFIXES:
                raise AppError(40982, "PC Web 目标不能转换为小程序品牌", 409)
            members = self.mini_program_members(original)
            expected = {item.id: item.revision for item in payload.members}
            if expected.keys() != {row.id for row in members}:
                raise ConflictError("小程序平台配置已变化, 请刷新后重新编辑")
            for row in members:
                self.check_revision(row, expected[row.id])
        configured = {item.platform: item for item in payload.platforms}
        if any(row.platform not in configured for row in members):
            raise AppError(40982, "已配置平台不能删除, 请保留该平台并设为停用", 409)
        codes = [payload.code + suffix for suffix in MINI_PROGRAM_SUFFIXES.values()]
        existing_ids = {row.id for row in members}
        collisions = self.db.scalars(
            select(ReleaseTarget.id).where(
                ReleaseTarget.system_id == system_id,
                ReleaseTarget.code.in_(codes),
                ReleaseTarget.id.not_in(existing_ids),
            )
        ).all()
        if collisions:
            raise AppError(40981, "该业务系统内的小程序品牌编码或平台编码已存在", 409)
        by_platform = {row.platform: row for row in members}
        saved = []
        for platform, config in configured.items():
            row = by_platform.get(platform)
            if config.enabled and not config.app_id and (row is None or row.app_id):
                raise AppError(40982, "启用小程序平台前请填写对应 AppID", 409)
            values = dict(
                code=payload.code + MINI_PROGRAM_SUFFIXES[platform],
                name=payload.name,
                platform=platform,
                app_id=config.app_id or None,
                url=None,
                enabled=config.enabled,
            )
            if row is None:
                row = ReleaseTarget(
                    system_id=system_id, created_by=actor_id, updated_by=actor_id, **values
                )
                self.db.add(row)
            else:
                self.cas(row, row.revision, values, actor_id)
            saved.append(row)
        try:
            self.db.flush()
        except IntegrityError:
            raise AppError(40981, "该业务系统内的小程序品牌编码或平台编码已存在", 409) from None
        AuditService(self.db).log(
            "SYSTEM",
            system_id,
            "RELEASE_TARGET_BUNDLE_UPDATE"
            if target_id is not None
            else "RELEASE_TARGET_BUNDLE_CREATE",
            after={"name": payload.name, "code": payload.code, "target_ids": [r.id for r in saved]},
        )
        self.db.commit()
        for row in saved:
            self.db.refresh(row)
        return saved

    def version(self, ident: int, actor_id: int, *, write=False) -> Version:
        users = UserRepository(self.db)
        codes = users.permission_codes(actor_id)
        allowed = (
            {"rd.version.publish"}
            if write
            else {"rd.version.publish", "rd.version.view", "rd.release.view"}
        )
        if "*" not in codes and not allowed.intersection(codes):
            raise PermissionDenied()
        query = select(Version).where(Version.id == ident)
        if users.data_scope(actor_id) is not DataScope.ALL:
            query = query.where(VersionRepository.self_criterion(actor_id))
        if write:
            query = query.with_for_update()
        item = self.db.scalar(query.execution_options(populate_existing=True))
        if item is None:
            raise NotFoundError("版本不存在")
        return item

    @staticmethod
    def check_revision(item, revision):
        if item.revision != revision:
            raise ConflictError(
                "发布信息已被其他用户修改, 请刷新后重新确认", revision_conflict_data(item)
            )

    def cas(self, item, revision, values, actor_id):
        if not BaseRepository(self.db, type(item)).update_with_revision(
            item.id, revision, {**values, "updated_by": actor_id}
        ):
            raise ConflictError("发布信息已被其他用户修改, 请刷新后重新确认")
        self.db.flush()

    def batch(self, version_id, batch_id) -> ReleaseBatch:
        item = self.db.scalar(
            select(ReleaseBatch)
            .where(ReleaseBatch.version_id == version_id, ReleaseBatch.id == batch_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if item is None:
            raise NotFoundError("发布批次不存在")
        return item

    def rows(self, batch_id, *, lock=False):
        query = (
            select(ReleaseBatchTarget)
            .where(ReleaseBatchTarget.batch_id == batch_id)
            .order_by(ReleaseBatchTarget.id)
        )
        if lock:
            query = query.with_for_update()
        return list(self.db.scalars(query.execution_options(populate_existing=True)))

    def resolved_system(self, version):
        if version.system_id is not None:
            return version.system_id
        actual = (
            select(ReleaseBatchTarget.id)
            .where(
                ReleaseBatchTarget.batch_id == ReleaseBatch.id,
                ReleaseBatchTarget.completed_at.is_not(None),
            )
            .exists()
        )
        return self.db.scalar(
            select(ReleaseBatch.system_id)
            .where(
                ReleaseBatch.version_id == version.id, (ReleaseBatch.status != "CANCELED") | actual
            )
            .order_by(ReleaseBatch.id)
            .limit(1)
        )

    def target_options(self, version_id, actor_id, system_id=None):
        version = self.version(version_id, actor_id)
        resolved = self.resolved_system(version)
        if resolved is not None and system_id is not None and resolved != system_id:
            raise AppError(40982, "不能选择其他业务系统的发布目标", 409)
        target_system = resolved if resolved is not None else system_id
        if target_system is None:
            return []
        SystemBindingService(self.db).validate_catalog(target_system)
        covered = self.covered(version_id)
        pending = set(
            self.db.scalars(
                select(ReleaseBatchTarget.target_id)
                .join(ReleaseBatch)
                .where(
                    ReleaseBatch.version_id == version_id,
                    ReleaseBatch.status.in_(["PLANNED", "IN_PROGRESS"]),
                    ReleaseBatchTarget.active.is_(True),
                    ReleaseBatchTarget.completed_at.is_(None),
                )
            )
        )
        targets = self.db.scalars(
            select(ReleaseTarget)
            .where(ReleaseTarget.system_id == target_system, ReleaseTarget.enabled.is_(True))
            .order_by(ReleaseTarget.id)
        )
        return [
            ReleaseTargetOut.model_validate(target).model_copy(
                update={"covered": target.id in covered, "pending": target.id in pending}
            )
            for target in targets
        ]

    def covered(self, version_id):
        return set(
            self.db.scalars(
                select(ReleaseBatchTarget.target_id)
                .join(ReleaseBatch)
                .where(
                    ReleaseBatch.version_id == version_id,
                    ReleaseBatchTarget.completed_at.is_not(None),
                )
            )
        )

    def out(self, item: ReleaseBatch, version: Version) -> ReleaseBatchOut:
        rows = self.rows(item.id)
        return ReleaseBatchOut(
            **{
                k: getattr(item, k)
                for k in (
                    "id",
                    "version_id",
                    "system_id",
                    "kind",
                    "status",
                    "release_notes",
                    "reason",
                    "revision",
                    "created_at",
                    "updated_at",
                )
            },
            version_revision=version.revision,
            release_id=self.db.scalar(select(Release.id).where(Release.version_id == version.id)),
            total=sum(r.active for r in rows),
            completed=sum(r.active and r.completed_at is not None for r in rows),
            targets=[ReleaseBatchTargetOut.model_validate(r) for r in rows],
        )

    def listing(self, version_id, actor_id, page=1, page_size=20):
        version = self.version(version_id, actor_id)
        query = select(ReleaseBatch).where(ReleaseBatch.version_id == version_id)
        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
        batches = self.db.scalars(
            query.order_by(ReleaseBatch.id.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all()
        initial = self.db.scalar(
            select(ReleaseBatch.id).where(
                ReleaseBatch.version_id == version_id,
                ReleaseBatch.kind == "INITIAL",
                ReleaseBatch.status == "COMPLETED",
            )
        )
        return dict(
            version_id=version_id,
            version_revision=version.revision,
            system_id=self.resolved_system(version),
            release_frozen=version.release_frozen,
            legacy_unrecorded=version.status == "RELEASED" and initial is None,
            coverage_count=len(self.covered(version_id)),
            items=[self.out(b, version) for b in batches],
            total=total,
            page=page,
            page_size=page_size,
        )

    def valid_targets(self, system_id, ids):
        targets = list(
            self.db.scalars(
                select(ReleaseTarget)
                .where(ReleaseTarget.id.in_(ids))
                .order_by(ReleaseTarget.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        if len(targets) != len(ids) or any(
            t.system_id != system_id or not t.enabled for t in targets
        ):
            raise AppError(40982, "目标不存在、已停用或不属于本次业务系统", 409)
        return targets

    def log(self, version_id, action, actor_id, batch_id, detail=None):
        AuditService(self.db).log(
            "VERSION", version_id, action, after={"batch_id": batch_id, **(detail or {})}
        )

    def retired_plan(self, version_id, revision, actor_id):
        version = self.version(version_id, actor_id, write=True)
        self.check_revision(version, revision)
        raise AppError(
            40984, "发布目标已改为覆盖记录, 请正常发布版本, 或在发布后补记已发布目标", 409
        )

    @transactional
    def create_batch(self, version_id, payload, actor_id):
        return self.retired_plan(version_id, payload.version_revision, actor_id)

    @transactional
    def edit_batch(self, version_id, batch_id, payload, actor_id, *, cancel=False):
        return self.retired_plan(version_id, payload.version_revision, actor_id)

    @transactional
    def complete(self, version_id, batch_id, target_row_id, payload, actor_id):
        return self.retired_plan(version_id, payload.version_revision, actor_id)

    def close_legacy_plans(self, version, actor_id):
        # Historical actual records are immutable. Unfinished plans do not mean published.
        batches = list(
            self.db.scalars(
                select(ReleaseBatch)
                .where(
                    ReleaseBatch.version_id == version.id,
                    ReleaseBatch.status.in_(["PLANNED", "IN_PROGRESS"]),
                )
                .order_by(ReleaseBatch.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        for batch in batches:
            for row in self.rows(batch.id, lock=True):
                if row.active and row.completed_at is None:
                    self.cas(
                        row,
                        row.revision,
                        {"active": False, "removed_reason": "改用发布覆盖记录, 旧计划未登记发布"},
                        actor_id,
                    )
            self.cas(batch, batch.revision, {"status": "CANCELED"}, actor_id)
            self.log(
                version.id,
                "RELEASE_BATCH_CANCEL",
                actor_id,
                batch.id,
                {"reason": "改用发布覆盖记录, 保留历史实际发布"},
            )

    def coverage_targets(self, version, ids, system_id=None):
        resolved = self.resolved_system(version)
        if resolved is not None and system_id is not None and resolved != system_id:
            raise AppError(40982, "发布目标业务系统必须与版本一致", 409)
        system_id = resolved or system_id
        if system_id is None:
            raise AppError(40982, "请明确本次历史版本目标所属业务系统", 409)
        SystemBindingService(self.db).validate_catalog(system_id)
        targets = self.valid_targets(system_id, ids)
        if self.covered(version.id).intersection(ids):
            raise AppError(40983, "所选目标已有发布记录, 请刷新后仅勾选尚未登记的目标", 409)
        return system_id, targets

    @staticmethod
    def actual_time(value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise AppError(42281, "实际上线时间必须包含时区", 422)
        value = value.astimezone(UTC)
        if value > datetime.now(UTC) + timedelta(minutes=5):
            raise AppError(42281, "实际上线时间不能晚于当前时间", 422)
        return value

    def prepare_publish(self, version, payload, actor_id):
        if payload.initial_batch_id is not None:
            raise AppError(40984, "旧计划发布入口已停用, 请刷新后正常发布版本", 409)
        self.close_legacy_plans(version, actor_id)
        if not payload.target_ids:
            return None
        self.actual_time(payload.released_at)
        return self.coverage_targets(version, payload.target_ids)

    def append_coverage(
        self, version, system_id, targets, released_at, actor_id, *, kind, notes=None, evidence=None
    ):
        actor = self.db.get(User, actor_id)
        now = datetime.now(UTC)
        batch = ReleaseBatch(
            version_id=version.id,
            system_id=system_id,
            kind=kind,
            status="COMPLETED",
            release_notes=notes or "已发布目标登记",
            created_by=actor_id,
            updated_by=actor_id,
        )
        self.db.add(batch)
        self.db.flush()
        for target in targets:
            self.db.add(
                ReleaseBatchTarget(
                    batch_id=batch.id,
                    target_id=target.id,
                    active=True,
                    completed_at=released_at,
                    recorded_at=now,
                    completed_by=actor_id,
                    operator_name=actor.display_name or actor.username,
                    notes=notes,
                    evidence=evidence,
                    created_by=actor_id,
                    updated_by=actor_id,
                    **{
                        k: getattr(target, k) for k in ("name", "code", "platform", "app_id", "url")
                    },
                )
            )
        self.db.flush()
        self.log(
            version.id,
            "RELEASE_COVERAGE_RECORD",
            actor_id,
            batch.id,
            {"target_ids": [t.id for t in targets], "released_at": released_at.isoformat()},
        )
        return batch

    @transactional
    def record_coverage(self, version_id, payload, actor_id):
        version = self.version(version_id, actor_id, write=True)
        self.check_revision(version, payload.version_revision)
        if (
            version.status != "RELEASED"
            or self.db.scalar(select(Release.id).where(Release.version_id == version_id)) is None
        ):
            raise AppError(40983, "请先正常发布版本, 再补记已发布目标", 409)
        released_at = self.actual_time(payload.released_at)
        # Keep version -> batch -> target lock order; resolve the historical system first.
        resolved = self.resolved_system(version)
        if resolved is not None and payload.system_id is not None and resolved != payload.system_id:
            raise AppError(40982, "发布目标业务系统必须与版本一致", 409)
        self.close_legacy_plans(version, actor_id)
        system_id, targets = self.coverage_targets(
            version, payload.target_ids, resolved or payload.system_id
        )
        batch = self.append_coverage(
            version,
            system_id,
            targets,
            released_at,
            actor_id,
            kind="SUPPLEMENT",
            notes=payload.notes,
            evidence=payload.evidence,
        )
        self.cas(version, payload.version_revision, {}, actor_id)
        self.db.commit()
        self.db.refresh(version)
        self.db.refresh(batch)
        return self.out(batch, version)

    def record_scope(self, actor_id):
        users = UserRepository(self.db)
        codes = users.permission_codes(actor_id)
        if "*" not in codes and "rd.release.view" not in codes:
            raise PermissionDenied()
        return (
            []
            if users.data_scope(actor_id) is DataScope.ALL
            else [VersionRepository.self_criterion(actor_id)]
        )

    def records(self, actor_id, page, page_size, target_id=None, version_id=None):
        criteria = [ReleaseBatchTarget.completed_at.is_not(None), *self.record_scope(actor_id)]
        if target_id is not None:
            criteria.append(ReleaseBatchTarget.target_id == target_id)
        if version_id is not None:
            criteria.append(Version.id == version_id)
        query = (
            select(ReleaseBatchTarget, ReleaseBatch, Version)
            .join(ReleaseBatch, ReleaseBatch.id == ReleaseBatchTarget.batch_id)
            .join(Version, Version.id == ReleaseBatch.version_id)
            .where(*criteria)
        )
        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self.db.execute(
            query.order_by(ReleaseBatchTarget.completed_at.desc(), ReleaseBatchTarget.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        items = [
            dict(
                **ReleaseBatchTargetOut.model_validate(r).model_dump(),
                version_id=v.id,
                version_no=v.version_no,
                version_name=v.name,
                system_id=b.system_id,
                batch_id=b.id,
                batch_kind=b.kind,
            )
            for r, b, v in rows
        ]
        return dict(items=items, page=page, page_size=page_size, total=total)

    def record_options(self, actor_id):
        rows = self.db.execute(
            select(
                ReleaseTarget.id, ReleaseTarget.name, BusinessSystem.name, ReleaseTarget.platform
            )
            .join(BusinessSystem, BusinessSystem.id == ReleaseTarget.system_id)
            .join(ReleaseBatchTarget, ReleaseBatchTarget.target_id == ReleaseTarget.id)
            .join(ReleaseBatch, ReleaseBatch.id == ReleaseBatchTarget.batch_id)
            .join(Version, Version.id == ReleaseBatch.version_id)
            .where(ReleaseBatchTarget.completed_at.is_not(None), *self.record_scope(actor_id))
            .distinct()
            .order_by(ReleaseTarget.id)
        ).all()
        labels = {
            "PC_WEB": "PC Web",
            "WECHAT_MINI_PROGRAM": "微信小程序",
            "ALIPAY_MINI_PROGRAM": "支付宝小程序",
        }
        return [
            dict(id=ident, label=system + " / " + name + " · " + labels[platform])
            for ident, name, system, platform in rows
        ]
