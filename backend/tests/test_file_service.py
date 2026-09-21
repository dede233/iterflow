import hashlib
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.entities import AttachmentRelation, FileObject, User
from app.models.enums import DataScope, StorageDriver
from app.services.file_service import FileService


def _settings(storage_root: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://unused/iterflow",
        redis_url="redis://localhost:6379/0",
        jwt_secret="storage-test-secret-that-is-at-least-32-characters",
        storage_driver="local",
        local_storage_path=storage_root,
    )


@pytest.fixture
def file_session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'metadata.db'}")
    FileObject.__table__.create(engine)
    AttachmentRelation.__table__.create(engine)
    next_ids = iter(range(1, 100))

    def assign_id(_mapper, _connection, target):
        if target.id is None:
            target.id = next(next_ids)

    event.listen(FileObject, "before_insert", assign_id)
    event.listen(AttachmentRelation, "before_insert", assign_id)
    try:
        with Session(engine) as session:
            yield session
    finally:
        event.remove(FileObject, "before_insert", assign_id)
        event.remove(AttachmentRelation, "before_insert", assign_id)
        engine.dispose()


def test_local_file_lifecycle_persists_metadata_and_content(
    tmp_path: Path, file_session: Session
) -> None:
    storage_root = tmp_path / "uploads"
    actor = User(id=7, username="owner", display_name="Owner", password_hash="unused")
    service = FileService(file_session, _settings(storage_root))
    content = b"iterflow local storage"

    item = service.upload(
        content=content,
        original_name="../../customer-note.txt",
        mime_type="text/plain",
        actor=actor,
    )

    persisted = file_session.scalar(select(FileObject).where(FileObject.id == item.id))
    assert persisted is not None
    assert persisted.original_name == "../../customer-note.txt"
    assert persisted.storage_driver is StorageDriver.LOCAL
    assert persisted.size == len(content)
    assert persisted.sha256 == hashlib.sha256(content).hexdigest()
    assert "customer-note" not in persisted.storage_key
    assert (storage_root / persisted.storage_key).read_bytes() == content

    _, exists = service.exists(item.id, actor, DataScope.SELF)
    assert exists is True
    downloaded, stream = service.open(item.id, actor, DataScope.SELF)
    try:
        assert downloaded.id == item.id
        assert stream.read() == content
    finally:
        stream.close()

    service.delete(item.id, actor, DataScope.SELF)
    assert file_session.get(FileObject, item.id) is None
    assert not (storage_root / item.storage_key).exists()


def test_linked_file_cannot_be_deleted(tmp_path: Path, file_session: Session) -> None:
    actor = User(id=8, username="owner", display_name="Owner", password_hash="unused")
    service = FileService(file_session, _settings(tmp_path / "uploads"))
    item = service.upload(
        content=b"linked",
        original_name="linked.txt",
        mime_type="text/plain",
        actor=actor,
    )
    file_session.add(AttachmentRelation(file_id=item.id, entity_type="FEEDBACK", entity_id=100))
    file_session.commit()

    with pytest.raises(ConflictError):
        service.delete(item.id, actor, DataScope.SELF)

    assert file_session.get(FileObject, item.id) is not None
    assert (tmp_path / "uploads" / item.storage_key).is_file()


def test_delete_keeps_physical_file_when_database_commit_fails(
    tmp_path: Path, file_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage_root = tmp_path / "uploads"
    actor = User(id=9, username="owner", display_name="Owner", password_hash="unused")
    service = FileService(file_session, _settings(storage_root))
    item = service.upload(
        content=b"must survive rollback",
        original_name="rollback.txt",
        mime_type="text/plain",
        actor=actor,
    )
    stored_path = storage_root / item.storage_key

    def fail_commit() -> None:
        raise RuntimeError("simulated database commit failure")

    monkeypatch.setattr(file_session, "commit", fail_commit)

    with pytest.raises(RuntimeError, match="simulated database commit failure"):
        service.delete(item.id, actor, DataScope.SELF)

    assert file_session.get(FileObject, item.id) is not None
    assert stored_path.read_bytes() == b"must survive rollback"


def test_delete_surfaces_storage_cleanup_failure_after_safe_database_delete(
    tmp_path: Path, file_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor = User(id=12, username="owner", display_name="Owner", password_hash="unused")
    service = FileService(file_session, _settings(tmp_path / "uploads"))
    item = service.upload(
        content=b"orphan candidate",
        original_name="orphan.txt",
        mime_type="text/plain",
        actor=actor,
    )
    storage = Mock()
    storage.delete.side_effect = RuntimeError("simulated storage cleanup failure")
    monkeypatch.setattr(service, "_storage", lambda _driver: storage)

    with pytest.raises(RuntimeError, match="simulated storage cleanup failure"):
        service.delete(item.id, actor, DataScope.SELF)

    # The error is surfaced and there is no live metadata row pointing to missing content.
    assert file_session.get(FileObject, item.id) is None
    storage.delete.assert_called_once_with(item.storage_key)


def test_file_self_scope_is_temporarily_limited_to_creator(
    tmp_path: Path, file_session: Session
) -> None:
    """Documents the Phase 1 rule until attachment-aware authorization is implemented."""

    owner = User(id=10, username="owner", display_name="Owner", password_hash="unused")
    other = User(id=11, username="other", display_name="Other", password_hash="unused")
    service = FileService(file_session, _settings(tmp_path / "uploads"))
    item = service.upload(
        content=b"creator scoped",
        original_name="scoped.txt",
        mime_type="text/plain",
        actor=owner,
    )

    with pytest.raises(NotFoundError):
        service.exists(item.id, other, DataScope.SELF)
