import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from ops_production_permissions_acceptance import seed_collaboration_fixture
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core import database
from app.core.config import get_settings
from app.core.security import create_access_token
from app.main import app
from app.models.entities import User


class RedactedHeaders(dict):
    def __repr__(self):
        return "<authorization redacted>"


@pytest.fixture
def collaboration_pg(monkeypatch, tmp_path, request):
    url = os.environ.get("ITERFLOW_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Real PostgreSQL required for collaboration acceptance")
    schema = "collaboration_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    monkeypatch.setenv("PGOPTIONS", f"-c search_path={schema}")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"}, pool_size=8)
    try:
        with Session(engine) as db:
            seed_collaboration_fixture(
                db,
                username="collaboration-admin",
                password="Fresh-admin-password!",
                fresh=getattr(request, "param", None) == "fresh",
            )
            user = db.scalar(select(User).where(User.username == "collaboration-admin"))
            user.must_change_password = False
            db.commit()
            uid = user.id
        monkeypatch.setattr(
            database, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False)
        )
        with TestClient(app) as client:
            yield (
                client,
                engine,
                uid,
                RedactedHeaders(Authorization="Bearer " + create_access_token(uid)),
            )
    finally:
        engine.dispose()
        get_settings.cache_clear()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
