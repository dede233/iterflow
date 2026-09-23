#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-local}"
case "$MODE" in local|docker|all) ;; *) echo "Usage: release-check.sh [local|docker|all]" >&2; exit 2 ;; esac

if [[ "$MODE" == local || "$MODE" == all ]]; then
  cd "$ROOT/backend"
  PY="${ITERFLOW_PYTHON:-$ROOT/backend/.venv/bin/python}"
  "$PY" -m pytest -W error::DeprecationWarning -q
  "$PY" -m ruff check app tests
  "$PY" -m ruff format --check app tests
  "$PY" -m mypy app
  "$PY" -m compileall -q app
  "$PY" -m alembic check
  "$PY" -m pip_audit -r requirements.lock
  cd "$ROOT/frontend"
  npm audit --audit-level=moderate
  npm audit --omit=dev --audit-level=moderate
  npm test
  npm run check:api-types
  npm run build
  npm run check:bundle
fi

if [[ "$MODE" == docker || "$MODE" == all ]]; then
  cd "$ROOT"
  docker version
  docker compose version
  docker compose -f deploy/docker-compose.yml config --quiet
  docker compose -f deploy/docker-compose.yml build
  echo "For a destructive fresh-volume acceptance, run scripts/smoke-compose.sh in an isolated environment."
fi
