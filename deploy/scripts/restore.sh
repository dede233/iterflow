#!/usr/bin/env bash
set -euo pipefail

if [[ "${CONFIRM_RESTORE:-}" != "YES" ]]; then
  echo "Destructive restore requires CONFIRM_RESTORE=YES" >&2
  exit 2
fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
BACKUP_DIR="${1:?Usage: CONFIRM_RESTORE=YES restore.sh /absolute/backup/directory}"
if [[ "$BACKUP_DIR" != /* ]] || [[ ! -f "$BACKUP_DIR/database.dump" ]] || \
   [[ ! -f "$BACKUP_DIR/uploads.tar" ]] || [[ ! -f "$BACKUP_DIR/manifest.json" ]]; then
  echo "A complete absolute backup directory is required" >&2
  exit 2
fi
COMPOSE=(docker compose -f deploy/docker-compose.yml)
MODE="$("${COMPOSE[@]}" config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["api"]["environment"]["STORAGE_DRIVER"])')"
if [[ "$MODE" != "local" ]]; then
  echo "S3 objects need an independently verified provider restore point" >&2
  exit 2
fi
python3 deploy/scripts/verify_archive.py "$BACKUP_DIR/uploads.tar"
python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); assert data["storage_mode"] == "local", "backup storage mode mismatch"' "$BACKUP_DIR/manifest.json"
cd "$BACKUP_DIR"
shasum -a 256 -c SHA256SUMS
cd "$ROOT"
"${COMPOSE[@]}" stop web api

# Keep the application stopped if any destructive restore step fails.
"${COMPOSE[@]}" exec -T db pg_restore -U iterflow -d iterflow --clean --if-exists --no-owner --exit-on-error < "$BACKUP_DIR/database.dump"
"${COMPOSE[@]}" run -T --rm --no-deps api sh -c \
  'find /app/data/uploads -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +; tar -C /app/data/uploads -xf -' \
  < "$BACKUP_DIR/uploads.tar"
"${COMPOSE[@]}" exec -T db psql -U iterflow -d iterflow -tAc 'SELECT version_num FROM alembic_version'
"${COMPOSE[@]}" rm -f migrate seed
"${COMPOSE[@]}" up -d migrate seed api web
curl --fail --retry 20 --retry-delay 2 --retry-connrefused "http://127.0.0.1:${API_PORT:-8000}/ready"
echo "Restore complete; run login and business attachment smoke before returning traffic"
