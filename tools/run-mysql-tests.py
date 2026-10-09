"""Run MySQL acceptance explicitly, without exposing local credentials."""

import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
env = dict(os.environ)
for line in (root / ".env").read_text().splitlines():
    if line and not line.startswith("#"):
        key, value = line.split("=", 1)
        env[key] = value
env["PYTHONPATH"] = str(root / "backend/tests") + os.pathsep + str(root / "backend")
assert env["DATABASE_URL"].startswith("mysql+pymysql://")
raise SystemExit(
    subprocess.call(
        [
            str(root / ".venv/bin/python"),
            "-m",
            "pytest",
            "tests_mysql57",
            *sys.argv[1:],
        ],
        cwd=root / "backend",
        env=env,
    )
)
