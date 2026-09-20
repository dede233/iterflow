import json
from datetime import UTC, datetime

from redis import Redis
from redis.exceptions import WatchError

from app.core.config import get_settings


class EditingService:
    def __init__(self):
        self.redis = Redis.from_url(get_settings().redis_url, decode_responses=True)

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
