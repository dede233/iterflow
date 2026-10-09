"""Generate fresh, local-only test configuration; refuse existing configuration."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = [root / ".env", root / "tools/mysql57-proof/.env"]
if any(path.exists() for path in files):
    raise SystemExit(
        "Test configuration already exists; preserved without modification"
    )
password = secrets.token_hex(24)
files[1].write_text("MYSQL_ROOT_PASSWORD=" + password + "\n")
files[0].write_text(
    "DATABASE_URL=mysql+pymysql://root:"
    + password
    + "@127.0.0.1:57357/iterflow_mysql57_proof?charset=utf8mb4\n"
    "REDIS_URL=redis://127.0.0.1:57379/15\n"
    "JWT_SECRET=" + secrets.token_hex(32) + "\n"
    "APP_ENV=test\nSTORAGE_DRIVER=local\nLOCAL_STORAGE_PATH=./data/mysql57-test-uploads\n"
)
for path in files:
    path.chmod(0o600)
print("Generated independent local test configuration (credentials not displayed)")
