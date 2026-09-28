import json

from app.services.editing_service import EditingService


class FakePipeline:
    def __init__(self, redis: "FakeRedis"):
        self.redis = redis
        self.pending: tuple[str, str | None, int | None] | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def watch(self, key: str):
        return None

    def get(self, key: str):
        expires_at = self.redis.expires_at.get(key)
        if expires_at is not None and expires_at <= self.redis.now_seconds:
            self.redis.store.pop(key, None)
            self.redis.expires_at.pop(key, None)
        return self.redis.store.get(key)

    def multi(self):
        return None

    def set(self, key: str, value: str, ex: int):
        self.pending = (key, value, ex)

    def delete(self, key: str):
        self.pending = (key, None, None)

    def execute(self):
        assert self.pending is not None
        key, value, ttl = self.pending
        if value is None:
            self.redis.store.pop(key, None)
            self.redis.expires_at.pop(key, None)
        else:
            self.redis.store[key] = value
            assert ttl is not None
            self.redis.expires_at[key] = self.redis.now_seconds + ttl
        return [True]


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.expires_at: dict[str, int] = {}
        self.now_seconds = 0

    def pipeline(self):
        return FakePipeline(self)


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


def test_two_editors_get_owner_details_without_stealing_presence():
    redis = FakeRedis()
    service = make_service(redis)
    key = EditingService.key("FEEDBACK", 8)

    assert service.start("FEEDBACK", 8, 1, "测试用户A") is None
    assert service.heartbeat("FEEDBACK", 8, 1, "测试用户A") is None
    existing = service.start("FEEDBACK", 8, 2, "测试用户B")
    assert existing is not None
    assert existing["user_id"] == 1
    assert existing["display_name"] == "测试用户A"
    assert existing["active_at"]

    service.end("FEEDBACK", 8, 2)
    assert json.loads(redis.store[key])["user_id"] == 1
    service.end("FEEDBACK", 8, 1)
    assert service.start("FEEDBACK", 8, 2, "测试用户B") is None
    assert json.loads(redis.store[key])["user_id"] == 2


def test_presence_expires_after_short_ttl_and_can_be_claimed():
    redis = FakeRedis()
    service = make_service(redis)

    assert service.start("VERSION", 9, 1, "测试用户A", ttl_seconds=2) is None
    redis.now_seconds = 1
    assert service.start("VERSION", 9, 2, "测试用户B", ttl_seconds=2)
    redis.now_seconds = 2
    assert service.start("VERSION", 9, 2, "测试用户B", ttl_seconds=2) is None
    assert redis.expires_at[EditingService.key("VERSION", 9)] == 4
