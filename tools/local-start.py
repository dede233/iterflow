"""Run the current IterFlow working tree against an isolated ServBay schema.

Usage (in separate terminals):
    backend/.venv/bin/python \
        tools/local-start.py api
    backend/.venv/bin/python \
        tools/local-start.py web

The original .env is read only. No credential is copied into this script.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import subprocess
import sys
from http.client import HTTPException
from pathlib import Path
from urllib.request import urlopen

from dotenv import dotenv_values
from redis import Redis
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
STORAGE_ROOT = ROOT / "data/uploads"
SOURCE_ENV = ROOT / ".env"
PYTHON = ROOT / "backend/.venv/bin/python"
SCHEMA = "iterflow_v150_local"
REDIS_URL = "redis://127.0.0.1:6379/14"
BUILD_SHA = subprocess.check_output(
    ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
).strip()


def backend_environment() -> dict[str, str]:
    values = dotenv_values(SOURCE_ENV)
    for key in ("DATABASE_URL", "JWT_SECRET"):
        if not values.get(key):
            raise SystemExit(f"Missing {key} in {SOURCE_ENV}")

    env = os.environ.copy()
    env["DATABASE_URL"] = values["DATABASE_URL"]
    env["JWT_SECRET"] = hmac.new(
        values["JWT_SECRET"].encode(), SCHEMA.encode(), hashlib.sha256
    ).hexdigest()
    env["REDIS_URL"] = REDIS_URL
    env["PGOPTIONS"] = f"-c search_path={SCHEMA}"
    env["APP_ENV"] = "development"
    env["ALLOWED_HOSTS"] = ""
    env["CORS_ORIGINS"] = "http://localhost:5173,http://127.0.0.1:5173"
    env["TRUST_PROXY_HEADERS"] = "false"
    env["ENABLE_API_DOCS"] = "true"
    env["STORAGE_DRIVER"] = "local"
    env["LOCAL_STORAGE_PATH"] = str(STORAGE_ROOT)
    env["BUILD_SHA"] = BUILD_SHA
    return env


def check_dependencies(env: dict[str, str]) -> None:
    engine = create_engine(
        env["DATABASE_URL"], connect_args={"options": env["PGOPTIONS"]}
    )
    try:
        with engine.connect() as connection:
            schema = connection.scalar(text("SELECT current_schema()"))
            if schema != SCHEMA:
                raise SystemExit(f"Refusing to use unexpected schema: {schema}")
            revision = connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
            if revision != "0004_integrity":
                raise SystemExit(f"Refusing to run against revision {revision}")
    finally:
        engine.dispose()
    redis = Redis.from_url(REDIS_URL, socket_connect_timeout=2)
    try:
        redis.ping()
    finally:
        redis.close()


def status() -> None:
    for name, url in (
        ("API health", "http://127.0.0.1:8000/health"),
        ("API ready", "http://127.0.0.1:8000/ready"),
        ("Web", "http://127.0.0.1:5173/"),
    ):
        try:
            with urlopen(url, timeout=3) as response:
                print(f"{name}: HTTP {response.status}")
        except (OSError, HTTPException) as exc:
            print(f"{name}: unavailable ({type(exc).__name__})")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"api", "web", "status"}:
        raise SystemExit("Usage: tools/local-start.py {api|web|status}")
    mode = sys.argv[1]
    if mode == "status":
        status()
        return
    if mode == "web":
        os.chdir(ROOT / "frontend")
        node = "/Applications/ServBay/package/node/current/bin/node"
        os.execve(
            node,
            (
                node,
                str(ROOT / "frontend/node_modules/vite/bin/vite.js"),
                "--host",
                "127.0.0.1",
                "--port",
                "5173",
                "--strictPort",
            ),
            os.environ.copy(),
        )

    env = backend_environment()
    check_dependencies(env)
    os.chdir(ROOT / "backend")
    os.execve(
        PYTHON,
        (
            str(PYTHON),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ),
        env,
    )


if __name__ == "__main__":
    main()
