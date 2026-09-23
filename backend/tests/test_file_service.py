import hashlib
import io
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.models.entities import AttachmentRelation, FileObject, User
from app.models.enums import DataScope, StorageDriver
from app.schemas.file import FileOut
from app.services.file_service import FileService, validate_upload


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
    assert persisted.original_name == "customer-note.txt"
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


def test_all_scope_can_access_only_standalone_files(tmp_path: Path, file_session: Session) -> None:
    owner = User(id=20, username="owner-all", display_name="Owner", password_hash="unused")
    manager = User(id=21, username="manager-all", display_name="Manager", password_hash="unused")
    service = FileService(file_session, _settings(tmp_path / "uploads"))
    standalone = service.upload(
        content=b"standalone", original_name="standalone.txt", mime_type="text/plain", actor=owner
    )
    _, exists = service.exists(standalone.id, manager, DataScope.ALL)
    assert exists

    attached = service.upload(
        content=b"attached", original_name="attached.txt", mime_type="text/plain", actor=owner
    )
    file_session.add(AttachmentRelation(file_id=attached.id, entity_type="FEEDBACK", entity_id=3))
    file_session.commit()
    with pytest.raises(NotFoundError):
        service.exists(attached.id, manager, DataScope.ALL)
    with pytest.raises(NotFoundError):
        service.open(attached.id, manager, DataScope.ALL)


def test_file_out_does_not_expose_storage_key() -> None:
    assert "storage_key" not in FileOut.model_fields


def test_upload_validation_rejects_spoofing_before_storage(
    tmp_path: Path, file_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor = User(id=22, username="uploader", display_name="Uploader", password_hash="unused")
    service = FileService(file_session, _settings(tmp_path / "uploads"))
    storage = Mock()
    monkeypatch.setattr(service, "_storage", lambda _driver: storage)

    with pytest.raises(AppError) as raised:
        service.upload(
            content=b"not a png",
            original_name="image.png",
            mime_type="image/png",
            actor=actor,
        )
    assert raised.value.status_code == 422
    storage.upload.assert_not_called()
    assert file_session.query(FileObject).count() == 0


def test_storage_upload_is_compensated_when_file_metadata_insert_fails(
    tmp_path: Path, file_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor = User(id=23, username="failed-uploader", display_name="Uploader", password_hash="unused")
    service = FileService(file_session, _settings(tmp_path / "uploads"))
    storage = Mock()
    monkeypatch.setattr(service, "_storage", lambda _driver: storage)

    def fail_commit() -> None:
        raise RuntimeError("simulated file metadata insert failure")

    monkeypatch.setattr(file_session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="simulated file metadata insert failure"):
        service.upload(
            content=b"valid text",
            original_name="metadata-failure.txt",
            mime_type="text/plain",
            actor=actor,
        )

    storage.upload.assert_called_once()
    storage_key = storage.upload.call_args.args[0]
    storage.delete.assert_called_once_with(storage_key)
    assert file_session.query(FileObject).count() == 0


def test_upload_validation_requires_extension_to_match_mime() -> None:
    with pytest.raises(AppError) as raised:
        validate_upload(
            size=8,
            mime_type="image/png",
            original_name="payload.pdf",
            content=b"\x89PNG\r\n\x1a\n",
        )
    assert raised.value.status_code == 422


def test_upload_validation_accepts_png_and_sanitizes_path_and_controls() -> None:
    name = validate_upload(
        size=9,
        mime_type="image/png",
        original_name="../../secret\r\n.png",
        content=b"\x89PNG\r\n\x1a\nX",
    )
    assert name == "secret.png"
    assert "\r" not in name and "\n" not in name


def test_path_filename_keeps_only_safe_pdf_basename() -> None:
    assert (
        validate_upload(
            size=9,
            mime_type="application/pdf",
            original_name="../../secret.pdf",
            content=b"%PDF-1.7\n",
        )
        == "secret.pdf"
    )


def _minimal_ooxml(*members: str) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for member in members:
            archive.writestr(member, "<root/>")
    return stream.getvalue()


@pytest.mark.parametrize(
    ("mime_type", "filename", "members"),
    [
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "valid.docx",
            ("[Content_Types].xml", "_rels/.rels", "word/document.xml"),
        ),
        (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "valid.xlsx",
            ("[Content_Types].xml", "_rels/.rels", "xl/workbook.xml"),
        ),
    ],
)
def test_upload_validation_accepts_minimal_real_ooxml_structure(
    mime_type: str, filename: str, members: tuple[str, ...]
) -> None:
    content = _minimal_ooxml(*members)
    assert (
        validate_upload(
            size=len(content), mime_type=mime_type, original_name=filename, content=content
        )
        == filename
    )


def test_upload_validation_rejects_arbitrary_zip_as_docx() -> None:
    content = _minimal_ooxml("notes.txt")
    with pytest.raises(AppError) as raised:
        validate_upload(
            size=len(content),
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            original_name="fake.docx",
            content=content,
        )
    assert raised.value.status_code == 422


def test_upload_validation_rejects_binary_text_and_filename_controls() -> None:
    with pytest.raises(AppError):
        validate_upload(size=3, mime_type="text/plain", original_name="x.txt", content=b"a\x00b")
    with pytest.raises(AppError):
        validate_upload(size=1, mime_type="text/plain", original_name=" \r\n ", content=b"a")
