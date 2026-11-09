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
from app.schemas.version import PublishVersionRequest
from app.services.audit_service import AuditService
from app.services.publish_check_service import PublishCheckService
from app.services.revision_conflict import revision_conflict_data
from app.services.system_binding_service import SystemBindingService


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
    """All target writes serialize on version, then batch, target and requirement rows."""

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
        item = self.db.scalar(
            select(ReleaseTarget)
            .where(ReleaseTarget.id == ident)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if item is None:
            raise NotFoundError("发布目标不存在")
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

    def check_ready(self, version, actor_id):
        result = PublishCheckService(self.db).evaluate(version, lock=True, viewer_id=actor_id)
        if not result["passed"]:
            raise AppError(
                40923,
                "发布检查未通过",
                409,
                {
                    "checks": result["checks"],
                    "blocking_requirements": PublishCheckService.blocking_requirements(result),
                },
            )

    def log(self, version_id, action, actor_id, batch_id, detail=None):
        AuditService(self.db).log(
            "VERSION", version_id, action, after={"batch_id": batch_id, **(detail or {})}
        )

    @transactional
    def create_batch(self, version_id, payload, actor_id):
        version = self.version(version_id, actor_id, write=True)
        self.check_revision(version, payload.version_revision)
        system_id = self.resolved_system(version)
        if (
            system_id is not None
            and payload.system_id is not None
            and system_id != payload.system_id
        ):
            raise AppError(40982, "批次业务系统必须与版本一致", 409)
        system_id = system_id or payload.system_id
        if system_id is None:
            raise AppError(40982, "请明确本次历史版本补发所属业务系统", 409)
        SystemBindingService(self.db).validate_catalog(system_id)
        targets = self.valid_targets(system_id, payload.target_ids)
        actual = self.covered(version_id)
        if payload.kind == "INITIAL":
            if version.status in {"RELEASED", "CANCELED"} or version.release_frozen:
                raise AppError(40983, "当前版本不能创建首次发布计划", 409)
            if self.db.scalar(
                select(ReleaseBatch.id).where(
                    ReleaseBatch.version_id == version_id,
                    ReleaseBatch.kind == "INITIAL",
                    ReleaseBatch.status != "CANCELED",
                )
            ):
                raise AppError(40983, "已有首次发布计划, 请调整当前计划", 409)
            self.check_ready(version, actor_id)
        else:
            if (
                version.status != "RELEASED"
                or self.db.scalar(select(Release.id).where(Release.version_id == version_id))
                is None
            ):
                raise AppError(40983, "只有已整体上线的版本可补发或重新发布", 409)
            if (payload.kind == "SUPPLEMENT" and actual.intersection(payload.target_ids)) or (
                payload.kind == "REPUBLISH" and not set(payload.target_ids) <= actual
            ):
                raise AppError(40983, "补发请选择尚未覆盖目标; 已覆盖目标请明确使用重新发布", 409)
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
        if pending.intersection(payload.target_ids):
            raise AppError(40983, "目标已在其他未完成批次中, 请先处理该批次", 409)
        batch = ReleaseBatch(
            version_id=version_id,
            system_id=system_id,
            kind=payload.kind,
            release_notes=payload.release_notes,
            reason=payload.reason,
            created_by=actor_id,
            updated_by=actor_id,
        )
        self.db.add(batch)
        self.db.flush()
        for target in targets:
            self.add_target(batch, target, actor_id)
        self.cas(version, payload.version_revision, {}, actor_id)
        self.log(
            version_id,
            "RELEASE_BATCH_CREATE",
            actor_id,
            batch.id,
            {"kind": payload.kind, "target_ids": payload.target_ids, "reason": payload.reason},
        )
        self.db.commit()
        self.db.refresh(version)
        self.db.refresh(batch)
        return self.out(batch, version)

    def add_target(self, batch, target, actor_id):
        row = ReleaseBatchTarget(
            batch_id=batch.id,
            target_id=target.id,
            created_by=actor_id,
            updated_by=actor_id,
            **{k: getattr(target, k) for k in ("name", "code", "platform", "app_id", "url")},
        )
        self.db.add(row)

    @transactional
    def edit_batch(self, version_id, batch_id, payload, actor_id, *, cancel=False):
        version = self.version(version_id, actor_id, write=True)
        self.check_revision(version, payload.version_revision)
        batch = self.batch(version_id, batch_id)
        self.check_revision(batch, payload.revision)
        if batch.status not in {"PLANNED", "IN_PROGRESS"}:
            raise AppError(40984, "已结束批次不能修改, 请新增补发批次", 409)
        rows = self.rows(batch_id, lock=True)
        completed = {r.target_id for r in rows if r.completed_at is not None}
        if cancel:
            if completed and batch.kind == "INITIAL":
                raise AppError(40984, "首次已有实际成功, 不能取消; 请带原因调整未完成目标", 409)
            selected = completed
            targets = []
        else:
            selected = set(payload.target_ids)
            if not completed <= selected:
                raise AppError(40984, "已完成目标不能移除或改写", 409)
            new_ids = selected - {r.target_id for r in rows if r.active}
            targets = self.valid_targets(batch.system_id, new_ids)
            actual = self.covered(version_id)
            if (batch.kind == "SUPPLEMENT" and (new_ids & actual)) or (
                batch.kind == "REPUBLISH" and not new_ids <= actual
            ):
                raise AppError(40983, "请按目标覆盖情况选择补发或重新发布", 409)
            other = set(
                self.db.scalars(
                    select(ReleaseBatchTarget.target_id)
                    .join(ReleaseBatch)
                    .where(
                        ReleaseBatch.version_id == version_id,
                        ReleaseBatch.id != batch_id,
                        ReleaseBatch.status.in_(["PLANNED", "IN_PROGRESS"]),
                        ReleaseBatchTarget.active.is_(True),
                        ReleaseBatchTarget.completed_at.is_(None),
                    )
                )
            )
            if new_ids & other:
                raise AppError(40983, "目标已在其他未完成批次中", 409)
        by_id = {r.target_id: r for r in rows}
        for row in rows:
            wanted = row.target_id in selected
            if wanted != row.active:
                self.cas(
                    row,
                    row.revision,
                    {"active": wanted, "removed_reason": None if wanted else payload.reason},
                    actor_id,
                )
        for target in targets:
            if target.id not in by_id:
                self.add_target(batch, target, actor_id)
        status = (
            "CANCELED"
            if cancel
            else (
                "COMPLETED" if batch.kind != "INITIAL" and selected <= completed else batch.status
            )
        )
        self.cas(batch, payload.revision, {"status": status}, actor_id)
        self.cas(version, payload.version_revision, {}, actor_id)
        self.log(
            version_id,
            "RELEASE_BATCH_CANCEL" if cancel else "RELEASE_BATCH_ADJUST",
            actor_id,
            batch_id,
            {"target_ids": sorted(selected), "reason": payload.reason},
        )
        self.db.commit()
        self.db.refresh(batch)
        self.db.refresh(version)
        return self.out(batch, version)

    @transactional
    def complete(self, version_id, batch_id, target_row_id, payload, actor_id):
        version = self.version(version_id, actor_id, write=True)
        self.check_revision(version, payload.version_revision)
        batch = self.batch(version_id, batch_id)
        self.check_revision(batch, payload.batch_revision)
        if batch.status not in {"PLANNED", "IN_PROGRESS"}:
            raise AppError(40984, "当前批次已结束, 不能重复登记", 409)
        rows = self.rows(batch_id, lock=True)
        row = next((r for r in rows if r.id == target_row_id), None)
        if row is None:
            raise NotFoundError("批次目标不存在")
        self.check_revision(row, payload.revision)
        if not row.active or row.completed_at is not None:
            raise AppError(40984, "目标已完成或已移出计划, 不能重复登记", 409)
        self.valid_targets(batch.system_id, [row.target_id])
        if batch.kind == "INITIAL":
            self.check_ready(version, actor_id)
        elif version.status != "RELEASED":
            raise AppError(40983, "补发必须保持版本已整体上线", 409)
        released_at = payload.released_at.astimezone(UTC)
        now = datetime.now(UTC)
        if released_at > now + timedelta(minutes=5):
            raise AppError(42281, "实际上线时间不能晚于当前时间", 422)
        actor = self.db.get(User, actor_id)
        self.cas(
            row,
            payload.revision,
            {
                "completed_at": released_at,
                "recorded_at": now,
                "completed_by": actor_id,
                "operator_name": actor.display_name or actor.username,
                "notes": payload.notes,
                "evidence": payload.evidence,
            },
            actor_id,
        )
        self.log(
            version_id,
            "RELEASE_TARGET_COMPLETE",
            actor_id,
            batch_id,
            {
                "target_id": row.target_id,
                "batch_target_id": row.id,
                "released_at": released_at.isoformat(),
            },
        )
        finished = all(r.completed_at is not None for r in rows if r.active)
        if finished and batch.kind == "INITIAL":
            from app.services.version_service import VersionService

            VersionService(self.db).publish(
                version_id,
                PublishVersionRequest(
                    revision=version.revision,
                    initial_batch_id=batch_id,
                    batch_revision=batch.revision,
                    released_at=max(r.completed_at for r in rows if r.active),
                    release_notes=batch.release_notes,
                ),
                actor_id,
                commit=False,
            )
        else:
            self.cas(
                batch,
                payload.batch_revision,
                {"status": "COMPLETED" if finished else "IN_PROGRESS"},
                actor_id,
            )
            self.cas(
                version,
                payload.version_revision,
                {"release_frozen": version.release_frozen or batch.kind == "INITIAL"},
                actor_id,
            )
        self.db.commit()
        self.db.refresh(batch)
        self.db.refresh(version)
        return self.out(batch, version)

    def publish_guard(self, version, payload):
        initial = self.db.scalar(
            select(ReleaseBatch)
            .where(
                ReleaseBatch.version_id == version.id,
                ReleaseBatch.kind == "INITIAL",
                ReleaseBatch.status != "CANCELED",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if payload.initial_batch_id is not None:
            if initial is None or initial.id != payload.initial_batch_id:
                raise AppError(40984, "首次批次不存在或不属于当前版本", 409)
            self.check_revision(initial, payload.batch_revision)
            rows = [r for r in self.rows(initial.id, lock=True) if r.active]
            if (
                not rows
                or any(r.completed_at is None for r in rows)
                or initial.status not in {"PLANNED", "IN_PROGRESS"}
            ):
                raise AppError(40984, "首次计划目标尚未全部完成, 不能整体发布", 409)
            payload.released_at = max(r.completed_at for r in rows)
            payload.release_notes = initial.release_notes
            return initial
        if initial is not None or version.release_frozen:
            raise AppError(40984, "已有首次发布计划, 请逐个登记目标, 不能绕过计划发布", 409)
        configured = self.db.scalar(
            select(ReleaseTarget.id).where(ReleaseTarget.system_id == version.system_id).limit(1)
        )
        if configured and (not payload.legacy_single or not payload.legacy_reason):
            raise AppError(
                40984, "系统已配置发布目标; 请按目标发布, 或明确选择传统发布并说明原因", 409
            )
        return None

    def finish_initial(self, batch, actor_id):
        self.cas(batch, batch.revision, {"status": "COMPLETED"}, actor_id)
        self.log(batch.version_id, "RELEASE_BATCH_COMPLETE", actor_id, batch.id)

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
            select(ReleaseTarget.id, ReleaseTarget.name, BusinessSystem.name)
            .join(BusinessSystem, BusinessSystem.id == ReleaseTarget.system_id)
            .join(ReleaseBatchTarget, ReleaseBatchTarget.target_id == ReleaseTarget.id)
            .join(ReleaseBatch, ReleaseBatch.id == ReleaseBatchTarget.batch_id)
            .join(Version, Version.id == ReleaseBatch.version_id)
            .where(ReleaseBatchTarget.completed_at.is_not(None), *self.record_scope(actor_id))
            .distinct()
            .order_by(ReleaseTarget.id)
        ).all()
        return [dict(id=ident, label=system + " / " + name) for ident, name, system in rows]
