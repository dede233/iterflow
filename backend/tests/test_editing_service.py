import json

from app.services.editing_service import EditingService


class FakePipeline:
    def __init__(self, store: dict[str, str]):
        self.store = store
        self.pending: tuple[str, str | None] | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def watch(self, key: str):
        return None

    def get(self, key: str):
        return self.store.get(key)

    def multi(self):
        return None

    def set(self, key: str, value: str, ex: int):
        self.pending = (key, value)

    def delete(self, key: str):
        self.pending = (key, None)

    def execute(self):
        assert self.pending is not None
        key, value = self.pending
        if value is None:
            self.store.pop(key, None)
        else:
            self.store[key] = value
        return [True]


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    def pipeline(self):
        return FakePipeline(self.store)


def make_service(redis: FakeRedis) -> EditingService:
    service = EditingService.__new__(EditingService)
    service.redis = redis
    return service


def test_start_does_not_overwrite_another_editor():
    redis = FakeRedis()
    key = EditingService.key("REQUIREMENT", 42)
    redis.store[key] = json.dumps({"user_id": 1, "display_name": "Alice", "active_at": "earlier"})
    service = make_service(redis)

    existing = service.start("REQUIREMENT", 42, 2, "Bob")

    assert existing is not None
    assert existing["user_id"] == 1
    assert json.loads(redis.store[key])["user_id"] == 1


def test_heartbeat_refreshes_only_the_current_editor():
    redis = FakeRedis()
    service = make_service(redis)

    assert service.heartbeat("REQUIREMENT", 42, 1, "Alice") is None
    existing = service.heartbeat("REQUIREMENT", 42, 2, "Bob")

    assert existing is not None
    assert existing["user_id"] == 1
    assert json.loads(redis.store[EditingService.key("REQUIREMENT", 42)])["user_id"] == 1


def test_end_only_deletes_the_current_editors_marker():
    redis = FakeRedis()
    key = EditingService.key("REQUIREMENT", 42)
    redis.store[key] = json.dumps({"user_id": 1, "display_name": "Alice"})
    service = make_service(redis)

    service.end("REQUIREMENT", 42, 2)
    assert key in redis.store

    service.end("REQUIREMENT", 42, 1)
    assert key not in redis.store
