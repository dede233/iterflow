import json
from datetime import datetime, timezone
from redis import Redis
from app.core.config import get_settings


class EditingService:
    def __init__(self):
        self.redis = Redis.from_url(get_settings().redis_url, decode_responses=True)

    @staticmethod
    def key(entity_type: str, entity_id: int) -> str:
        return f"edit_lock:{entity_type}:{entity_id}"

    def start(self, entity_type: str, entity_id: int, user_id: int, display_name: str, ttl_seconds: int = 600):
        key = self.key(entity_type, entity_id)
        existing = self.redis.get(key)
        payload = {
            "user_id": user_id,
            "display_name": display_name,
            "active_at": datetime.now(timezone.utc).isoformat(),
        }
        self.redis.set(key, json.dumps(payload), ex=ttl_seconds)
        return json.loads(existing) if existing else None

    def heartbeat(self, entity_type: str, entity_id: int, user_id: int, display_name: str, ttl_seconds: int = 600):
        self.redis.set(self.key(entity_type, entity_id), json.dumps({
            "user_id": user_id,
            "display_name": display_name,
            "active_at": datetime.now(timezone.utc).isoformat(),
        }), ex=ttl_seconds)

    def end(self, entity_type: str, entity_id: int, user_id: int):
        key = self.key(entity_type, entity_id)
        raw = self.redis.get(key)
        if not raw:
            return
        data = json.loads(raw)
        if data.get("user_id") == user_id:
            self.redis.delete(key)
