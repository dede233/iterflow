import json
from datetime import UTC, datetime
from typing import ClassVar

from redis import Redis
from redis.exceptions import WatchError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, PermissionDenied
from app.models.entities import Feedback, Requirement, Version
from app.models.enums import EditingEntityType
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.requirement_repository import RequirementRepository
from app.repositories.user_repository import UserRepository
from app.repositories.version_repository import VersionRepository


class EditingService:
    MUTATION_PERMISSIONS: ClassVar[dict[EditingEntityType, set[str]]] = {
        EditingEntityType.FEEDBACK: {"rd.feedback.edit", "rd.feedback.convert"},
        EditingEntityType.REQUIREMENT: {"rd.requirement.edit", "rd.requirement.status"},
        EditingEntityType.VERSION: {
            "rd.version.edit",
            "rd.version.status",
            "rd.version.publish",
        },
    }

    def __init__(self):
        self.redis = Redis.from_url(get_settings().redis_url, decode_responses=True)

    @classmethod
    def authorize_entity(
        cls, db: Session, entity_type: EditingEntityType, entity_id: int, user_id: int
    ) -> None:
        permissions = UserRepository(db).permission_codes(user_id)
        if "*" not in permissions and permissions.isdisjoint(cls.MUTATION_PERMISSIONS[entity_type]):
            raise PermissionDenied()

        scope = UserRepository(db).data_scope(user_id)
        entity: Feedback | Requirement | Version | None
        if entity_type is EditingEntityType.FEEDBACK:
            entity = FeedbackRepository(db).get_scoped(entity_id, user_id, scope)
        elif entity_type is EditingEntityType.REQUIREMENT:
            entity = RequirementRepository(db).get_scoped(entity_id, user_id, scope)
        else:
            entity = VersionRepository(db).get_scoped(entity_id, user_id, scope)
        if entity is None:
            raise NotFoundError("业务对象不存在")

    @staticmethod
    def key(entity_type: str, entity_id: int) -> str:
        return f"edit_lock:{entity_type}:{entity_id}"

    def _claim_or_refresh(
        self,
        entity_type: str,
        entity_id: int,
        user_id: int,
        display_name: str,
        ttl_seconds: int,
    ) -> dict | None:
        key = self.key(entity_type, entity_id)
        payload = {
            "user_id": user_id,
            "display_name": display_name,
            "active_at": datetime.now(UTC).isoformat(),
        }
        encoded = json.dumps(payload)
        while True:
            try:
                with self.redis.pipeline() as pipe:
                    pipe.watch(key)
                    raw = pipe.get(key)
                    if raw:
                        existing = json.loads(raw)
                        if existing.get("user_id") != user_id:
                            return existing
                    pipe.multi()
                    pipe.set(key, encoded, ex=ttl_seconds)
                    pipe.execute()
                    return None
            except WatchError:
                continue

    def start(
        self,
        entity_type: str,
        entity_id: int,
        user_id: int,
        display_name: str,
        ttl_seconds: int = 600,
    ) -> dict | None:
        return self._claim_or_refresh(
            entity_type,
            entity_id,
            user_id,
            display_name,
            ttl_seconds,
        )

    def heartbeat(
        self,
        entity_type: str,
        entity_id: int,
        user_id: int,
        display_name: str,
        ttl_seconds: int = 600,
    ) -> dict | None:
        return self._claim_or_refresh(
            entity_type,
            entity_id,
            user_id,
            display_name,
            ttl_seconds,
        )

    def end(self, entity_type: str, entity_id: int, user_id: int):
        key = self.key(entity_type, entity_id)
        while True:
            try:
                with self.redis.pipeline() as pipe:
                    pipe.watch(key)
                    raw = pipe.get(key)
                    if not raw or json.loads(raw).get("user_id") != user_id:
                        return
                    pipe.multi()
                    pipe.delete(key)
                    pipe.execute()
                    return
            except WatchError:
                continue
