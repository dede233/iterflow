"""Run MySQL acceptance explicitly, without exposing local credentials."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

root = Path(__file__).resolve().parents[1]
env = dict(os.environ)
for line in (root / ".env").read_text().splitlines():
    if line and not line.startswith("#"):
        key, value = line.split("=", 1)
        env[key] = value
env["PYTHONPATH"] = str(root / "backend/tests") + os.pathsep + str(root / "backend")
assert env["DATABASE_URL"].startswith("mysql+pymysql://")
arguments = list(sys.argv[1:])
if "--portable" in arguments:
    arguments.remove("--portable")
    url = make_url(env["DATABASE_URL"])
    assert url.host == "127.0.0.1" and url.port == 57357
    env["DATABASE_URL"] = url.set(port=57358).render_as_string(hide_password=False)
    env["ITERFLOW_MYSQL_TEST_PROFILE"] = "portable"
raise SystemExit(
    subprocess.call(
        [
            str(root / ".venv/bin/python"),
            "-m",
            "pytest",
            "tests_mysql57",
            *arguments,
        ],
        cwd=root / "backend",
        env=env,
    )
)
