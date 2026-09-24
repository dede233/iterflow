#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
BACKUP_DIR="${1:?Usage: backup-database.sh /absolute/new/backup/directory}"
if [[ "$BACKUP_DIR" != /* ]] || [[ -e "$BACKUP_DIR" ]]; then
  echo "Backup destination must be an absolute path that does not yet exist" >&2
  exit 2
fi
COMPOSE=(docker compose -f deploy/docker-compose.yml)
MODE="$("${COMPOSE[@]}" config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["api"]["environment"]["STORAGE_DRIVER"])')"
if [[ "$MODE" != local && "$MODE" != s3 ]]; then
  echo "Unsupported storage mode: $MODE" >&2
  exit 2
fi

mkdir -m 700 "$BACKUP_DIR"
restart_services() { "${COMPOSE[@]}" up -d api web; }
trap restart_services EXIT
"${COMPOSE[@]}" stop web api
"${COMPOSE[@]}" exec -T db pg_dump -U iterflow -d iterflow -Fc > "$BACKUP_DIR/database.dump"
REVISION="$("${COMPOSE[@]}" exec -T db psql -U iterflow -d iterflow -tAc 'SELECT version_num FROM alembic_version')"
BUILD="${BUILD_SHA:-$(git rev-parse HEAD)}"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
BACKUP_DIR="$BACKUP_DIR" REVISION="$REVISION" BUILD="$BUILD" TIMESTAMP="$TIMESTAMP" MODE="$MODE" \
  python3 -c 'import json, os, pathlib; p=pathlib.Path(os.environ["BACKUP_DIR"]); (p / "manifest.json").write_text(json.dumps({"timestamp": os.environ["TIMESTAMP"], "build_sha": os.environ["BUILD"], "database_revision": os.environ["REVISION"], "storage_mode": os.environ["MODE"], "objects_included": False}, indent=2) + "\n")'
(cd "$BACKUP_DIR" && shasum -a 256 database.dump > SHA256SUMS)
echo "Database-only backup complete: $BACKUP_DIR (objects excluded)"
