#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
BASE="http://${ITERFLOW_WEB_HOST:-127.0.0.1}:${WEB_PORT:-8080}/api/v1"
COMPOSE=(docker compose -f deploy/docker-compose.yml)
TEMP_DIR="$(mktemp -d)"
stage="initialization"
trap 'result=$?; if (( result != 0 )); then echo "Restore drill failed during: $stage (line $LINENO)" >&2; fi; rm -rf -- "$TEMP_DIR"' EXIT
initial_password="${INIT_ADMIN_PASSWORD:?CI administrator password is required}"
new_password="${ITERFLOW_BROWSER_NEW_PASSWORD:?CI new password is required}"
username="${INIT_ADMIN_USERNAME:?CI administrator username is required}"

stage="initial administrator login"
login="$(curl --fail --silent --show-error -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg u "$username" --arg p "$initial_password" '{username:$u,password:$p}')" \
  "$BASE/auth/login")"
token="$(jq -r '.access_token' <<< "$login")"
stage="administrator password change"
change="$(curl --fail --silent --show-error -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $token" \
  -d "$(jq -nc --arg c "$initial_password" --arg n "$new_password" '{current_password:$c,new_password:$n}')" \
  "$BASE/auth/change-password")"
token="$(jq -r '.access_token' <<< "$change")"

stage="feedback creation"
title="restore-drill-$(date +%s)"
feedback="$(curl --fail --silent --show-error -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $token" \
  -d "$(jq -nc --arg t "$title" '{title:$t,feedback_type:"SYSTEM_ISSUE",description:"Local backup restore drill"}')" \
  "$BASE/feedbacks")"
feedback_id="$(jq -r '.id' <<< "$feedback")"
printf 'iterflow restore drill %s\n' "$title" > "$TEMP_DIR/attachment.txt"
stage="attachment upload"
attachment="$(curl --fail --silent --show-error -H "Authorization: Bearer $token" \
  -F "file=@$TEMP_DIR/attachment.txt;type=text/plain" \
  "$BASE/feedbacks/$feedback_id/attachments")"
file_id="$(jq -r '.file_id' <<< "$attachment")"
stage="attachment database lookup"
storage_key="$("${COMPOSE[@]}" exec -T db psql -U iterflow -d iterflow -tAc \
  "SELECT storage_key FROM sys_file WHERE id=$file_id")"
[[ "$storage_key" == uploads/* ]]

stage="database-only backup creation"
bash deploy/scripts/backup-database.sh "$TEMP_DIR/database-only"
jq -e '.objects_included == false and .storage_mode == "local"' "$TEMP_DIR/database-only/manifest.json"
(cd "$TEMP_DIR/database-only" && shasum -a 256 -c SHA256SUMS)
stage="backup creation"
bash deploy/scripts/backup.sh "$TEMP_DIR/backup"
stage="destructive test-data mutation"
"${COMPOSE[@]}" exec -T db psql -U iterflow -d iterflow -v ON_ERROR_STOP=1 -c \
  'CREATE TABLE phase83_restore_sentinel (id integer PRIMARY KEY)'
sentinel_before="$("${COMPOSE[@]}" exec -T db psql -U iterflow -d iterflow -tAc \
  "SELECT to_regclass('public.phase83_restore_sentinel') IS NOT NULL")"
[[ "$sentinel_before" == t ]]
"${COMPOSE[@]}" exec -T db psql -U iterflow -d iterflow -c \
  "UPDATE rd_feedback SET title='CORRUPTED_BY_RESTORE_DRILL' WHERE id=$feedback_id"
"${COMPOSE[@]}" run -T --rm --no-deps api python -c \
  'import sys; from app.services.storage.local import LocalFileStorage; LocalFileStorage("/app/data/uploads").delete(sys.argv[1])' \
  "$storage_key"

stage="backup restoration"
CONFIRM_RESTORE=YES bash deploy/scripts/restore.sh "$TEMP_DIR/backup"
stage="restored schema verification"
sentinel_after="$("${COMPOSE[@]}" exec -T db psql -U iterflow -d iterflow -tAc \
  "SELECT to_regclass('public.phase83_restore_sentinel') IS NULL")"
[[ "$sentinel_after" == t ]]
revision="$("${COMPOSE[@]}" exec -T db psql -U iterflow -d iterflow -tAc \
  'SELECT version_num FROM alembic_version')"
[[ "$revision" == 0004_integrity ]]
stage="restored administrator login"
restored_login="$(curl --fail --silent --show-error -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg u "$username" --arg p "$new_password" '{username:$u,password:$p}')" \
  "$BASE/auth/login")"
restored_token="$(jq -r '.access_token' <<< "$restored_login")"
stage="restored feedback verification"
restored_feedback="$(curl --fail --silent --show-error -H "Authorization: Bearer $restored_token" \
  "$BASE/feedbacks/$feedback_id")"
jq -e --arg t "$title" '.title == $t' <<< "$restored_feedback"
stage="restored attachment verification"
curl --fail --silent --show-error -H "Authorization: Bearer $restored_token" \
  "$BASE/feedbacks/$feedback_id/attachments/$file_id/download" \
  -o "$TEMP_DIR/restored.txt"
[[ "$(shasum -a 256 "$TEMP_DIR/attachment.txt" | awk '{print $1}')" == \
   "$(shasum -a 256 "$TEMP_DIR/restored.txt" | awk '{print $1}')" ]]
stage="restored readiness verification"
"${COMPOSE[@]}" exec -T api python -m app.cli.healthcheck
echo "Database, attachment and SHA256 restore drill passed"
