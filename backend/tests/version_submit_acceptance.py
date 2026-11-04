"""Version-scoped submission gates, atomicity and lock races on isolated real databases."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier, Event

from sqlalchemy import delete, event, func, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.entities import (
    CollaborationEvent,
    OperationLog,
    Permission,
    Requirement,
    RequirementParticipant,
    RequirementStep,
    Role,
    RolePermission,
    User,
    UserRole,
    Version,
    VersionRequirement,
)
from app.models.enums import DataScope
from app.schemas.version import VersionRequirementSubmitAcceptance
from app.services.audit_service import AuditService
from app.services.version_requirement_workflow_service import VersionRequirementWorkflowService

SCENARIOS = [
    "shortcut",
    "developing",
    "admin_override",
    "admin_without_reason",
    "missing_reason",
    "stale_requirement",
    "stale_version",
    "missing_developer",
    "missing_acceptance",
    "disabled_acceptance",
    "disabled_developer",
    "not_developer",
    "unconfirmed",
    "design_pending",
    "wrong_pointer",
    "inactive_relation",
    "deleted_requirement",
    "version_released",
    "version_canceled",
    "state_draft",
    "state_testing",
    "state_done",
    "state_paused",
    "state_canceled",
    "state_online",
    "hidden_version",
    "hidden_requirement",
    "missing_permission",
    "mixed",
    "audit_failure",
    "ordinary_paths",
    "duplicate_race",
    "personnel_race",
    "permission_between_items",
]


def exercise_version_submit(fixture, scenario, monkeypatch):
    client, engine, admin_id, admin_headers = fixture
    with Session(engine, expire_on_commit=False) as db:
        actor = User(
            username="version-submit-developer",
            display_name="提验开发",
            password_hash="unused",
            must_change_password=False,
        )
        other = User(
            username="version-submit-acceptor",
            display_name="提验验收",
            password_hash="unused",
            must_change_password=False,
        )
        role = Role(code="VERSION_SUBMIT", name="版本提验", data_scope=DataScope.ALL)
        db.add_all([actor, other, role])
        db.flush()
        required = {"rd.version.view", "rd.requirement.view", "rd.requirement.status"}
        for permission in db.scalars(select(Permission).where(Permission.code.in_(required))):
            db.add(RolePermission(role_id=role.id, permission_id=permission.id))
        db.add(UserRole(user_id=actor.id, role_id=role.id))
        version = Version(version_no="SUBMIT-ONE", name="集中提验版本", created_by=actor.id)
        db.add(version)
        db.flush()
        requirements = []
        for number in range(2):
            item = Requirement(
                requirement_no=f"SUBMIT-{number}",
                title=f"集中提验{number}",
                description="隔离验收的完整需求",
                requirement_type="FEATURE",
                status="CONFIRMED",
                current_version_id=version.id if engine.dialect.name != "mysql" else None,
                created_by=actor.id,
                content_revision=1,
                confirmed_revision=1,
                design_status="NOT_REQUIRED",
            )
            db.add(item)
            db.flush()
            db.add_all(
                [
                    VersionRequirement(
                        version_id=version.id, requirement_id=item.id, added_by=actor.id
                    ),
                    RequirementParticipant(
                        requirement_id=item.id, user_id=actor.id, role="DEVELOP"
                    ),
                    RequirementParticipant(requirement_id=item.id, user_id=other.id, role="ACCEPT"),
                ]
            )
            requirements.append(item)
        db.commit()
        rid = requirements[0].id
        second_id = requirements[1].id
        vid, actor_id, role_id = version.id, actor.id, role.id
        body = {
            "version_revision": 1,
            "items": [{"id": rid, "revision": 1}],
            "reason": "实际已完成开发",
        }
        headers = {"Authorization": "Bearer " + create_access_token(actor_id)}
        target = requirements[0]
        expected_error = None
        if scenario in {"developing", "admin_without_reason"}:
            target.status = "DEVELOPING"
            body.pop("reason")
        if scenario in {"admin_override", "admin_without_reason", "disabled_developer"}:
            headers = admin_headers
        if scenario == "missing_reason":
            body.pop("reason")
            expected_error = 422
        elif scenario == "admin_without_reason":
            expected_error = 403
        elif scenario == "stale_requirement":
            target.revision = 2
            expected_error = 409
        elif scenario == "stale_version":
            version.revision = 2
            expected_error = 409
        elif scenario in {"missing_developer", "missing_acceptance"}:
            db.execute(
                delete(RequirementParticipant).where(
                    RequirementParticipant.requirement_id == rid,
                    RequirementParticipant.role
                    == ("DEVELOP" if scenario == "missing_developer" else "ACCEPT"),
                )
            )
            expected_error = 409
        elif scenario in {"disabled_acceptance", "disabled_developer"}:
            (actor if scenario == "disabled_developer" else other).status = "DISABLED"
            expected_error = 409
        elif scenario in {"not_developer", "hidden_requirement"}:
            person = db.scalar(
                select(RequirementParticipant).where(
                    RequirementParticipant.requirement_id == rid,
                    RequirementParticipant.role == "DEVELOP",
                )
            )
            person.user_id = other.id
            expected_error = 403
            if scenario == "hidden_requirement":
                role.data_scope = DataScope.SELF
                target.created_by = admin_id
                expected_error = 404
        elif scenario == "unconfirmed":
            target.confirmed_revision = None
            expected_error = 409
        elif scenario == "design_pending":
            target.design_status = "PENDING"
            expected_error = 409
        elif scenario == "wrong_pointer":
            # Keep database-level relation invariants valid while the submitted
            # version context becomes stale: move the active link elsewhere.
            db.scalar(
                select(VersionRequirement).where(VersionRequirement.requirement_id == rid)
            ).active = False
            db.flush()
            destination = Version(version_no="SUBMIT-OTHER", name="另一版本", created_by=actor.id)
            db.add(destination)
            db.flush()
            db.add(
                VersionRequirement(version_id=destination.id, requirement_id=rid, added_by=actor.id)
            )
            if engine.dialect.name != "mysql":
                target.current_version_id = destination.id
            expected_error = 409
        elif scenario == "inactive_relation":
            db.scalar(
                select(VersionRequirement).where(VersionRequirement.requirement_id == rid)
            ).active = False
            if engine.dialect.name != "mysql":
                target.current_version_id = None
            expected_error = 409
        elif scenario == "deleted_requirement":
            target.deleted_at = datetime.now(UTC)
            expected_error = 404
        elif scenario in {"version_released", "version_canceled"}:
            version.status = scenario.removeprefix("version_").upper()
            expected_error = 409
        elif scenario.startswith("state_"):
            target.status = scenario.removeprefix("state_").upper()
            expected_error = 409
        elif scenario == "hidden_version":
            role.data_scope = DataScope.SELF
            version.created_by = admin_id
        elif scenario == "missing_permission":
            permission_id = db.scalar(
                select(Permission.id).where(Permission.code == "rd.requirement.status")
            )
            db.execute(
                delete(RolePermission).where(
                    RolePermission.role_id == role.id, RolePermission.permission_id == permission_id
                )
            )
        elif scenario in {"mixed", "permission_between_items"}:
            body["items"].append({"id": second_id, "revision": 1})
            if scenario == "mixed":
                requirements[1].confirmed_revision = None
        db.commit()
        initial_status, initial_revision = target.status, target.revision
        initial_version_revision = version.revision

    def snapshot():
        with Session(engine) as db:
            return tuple(
                db.scalar(select(func.count()).select_from(model))
                for model in (RequirementStep, CollaborationEvent, OperationLog)
            )

    before = snapshot()
    path = f"/api/v1/versions/{vid}/requirements/submit-acceptance"
    if scenario == "audit_failure":
        original = AuditService.log

        def fail(self, entity_type, entity_id, action, **kwargs):
            if entity_type == "REQUIREMENT" and entity_id == rid and action == "STATUS_CHANGE":
                raise RuntimeError("isolated injected audit failure")
            return original(self, entity_type, entity_id, action, **kwargs)

        monkeypatch.setattr(AuditService, "log", fail)
        expected_error = 500
    elif scenario == "permission_between_items":
        original = VersionRequirementWorkflowService._submit_one

        def revoke(self, version_id, payload, requirement_id, revision, operator_id):
            if requirement_id == second_id:
                with Session(engine) as db:
                    db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
                    db.commit()
            return original(self, version_id, payload, requirement_id, revision, operator_id)

        monkeypatch.setattr(VersionRequirementWorkflowService, "_submit_one", revoke)
    if scenario == "ordinary_paths":
        direct = client.patch(
            f"/api/v1/requirements/{rid}/status",
            headers=headers,
            json={"status": "TESTING", "revision": 1, "reason": "实际已完成开发"},
        )
        assert direct.status_code == 409, direct.text
        original_batch = client.post(
            "/api/v1/requirements/batch-actions",
            headers=headers,
            json={"action": "TESTING", "items": body["items"], "reason": body["reason"]},
        )
        assert (
            original_batch.status_code == 200
            and original_batch.json()["results"][0]["status_code"] == 409
        )
        assert snapshot() == before
        return
    if scenario == "duplicate_race":
        barrier = Barrier(2)

        def submit(_):
            with Session(engine) as db:
                barrier.wait(timeout=10)
                return (
                    VersionRequirementWorkflowService(db)
                    .submit_acceptance(
                        vid, VersionRequirementSubmitAcceptance.model_validate(body), actor_id
                    )
                    .results[0]
                    .status_code
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(submit, [0, 1]))
        assert sorted(outcomes) == [200, 409]
    elif scenario == "personnel_race":
        waiting = Event()

        def on_statement(_conn, _cursor, statement, _params, _context, _many):
            if "FOR UPDATE" in statement.upper() and Requirement.__tablename__ in statement:
                waiting.set()

        def submit_waiting():
            with Session(engine) as db:
                return (
                    VersionRequirementWorkflowService(db)
                    .submit_acceptance(
                        vid, VersionRequirementSubmitAcceptance.model_validate(body), actor_id
                    )
                    .results[0]
                    .status_code
                )

        with Session(engine) as personnel:
            personnel.execute(select(Requirement.id).where(Requirement.id == rid).with_for_update())
            personnel.execute(
                delete(RequirementParticipant).where(
                    RequirementParticipant.requirement_id == rid,
                    RequirementParticipant.role == "ACCEPT",
                )
            )
            event.listen(engine, "before_cursor_execute", on_statement)
            pool = ThreadPoolExecutor(max_workers=1)
            try:
                future = pool.submit(submit_waiting)
                assert waiting.wait(timeout=10), "submission did not reach requirement lock"
                personnel.commit()
                assert future.result(timeout=20) == 409
            finally:
                # Release the held row before joining, including assertion failure.
                personnel.rollback()
                pool.shutdown(wait=True, cancel_futures=True)
                event.remove(engine, "before_cursor_execute", on_statement)
        expected_error = 409
    else:
        response = client.post(path, headers=headers, json=body)
        if scenario in {"hidden_version", "missing_permission"}:
            assert response.status_code == (404 if scenario == "hidden_version" else 403), (
                response.text
            )
            assert snapshot() == before
            return
        assert response.status_code == 200, response.text
        result = response.json()["results"]
        assert result[0]["status_code"] == (expected_error or 200), result
        if scenario in {"mixed", "permission_between_items"}:
            assert result[1]["status_code"] == (409 if scenario == "mixed" else 403), result
    with Session(engine) as db:
        latest = db.get(Requirement, rid)
        assert db.get(Version, vid).revision == initial_version_revision
        assert db.get(Requirement, second_id).revision == 1
        if expected_error:
            assert latest.status == initial_status and latest.revision == initial_revision
            assert snapshot() == before
        else:
            assert latest.status == "TESTING" and latest.revision == initial_revision + 1
            steps = list(
                db.scalars(select(RequirementStep).where(RequirementStep.requirement_id == rid))
            )
            assert len(steps) == 1 and steps[0].action == "STATUS_TESTING"
            assert steps[0].actor_id == (admin_id if scenario == "admin_override" else actor_id)
            assert steps[0].detail["from"] == initial_status
            assert steps[0].detail["shortcut"] == (initial_status == "CONFIRMED")
            assert steps[0].detail["reason"] == body.get("reason")
            assert steps[0].detail["source"] == "VERSION_SUBMIT_ACCEPTANCE"
            assert (
                len(
                    list(
                        db.scalars(
                            select(CollaborationEvent).where(
                                CollaborationEvent.entity_id == rid,
                                CollaborationEvent.action == "STATUS_TESTING",
                            )
                        )
                    )
                )
                == 1
            )
            assert snapshot() == tuple(count + 1 for count in before)
