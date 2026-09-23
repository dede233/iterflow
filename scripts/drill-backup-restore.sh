#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
BASE="http://127.0.0.1:${WEB_PORT:-8080}/api/v1"
COMPOSE=(docker compose -f deploy/docker-compose.yml)
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf -- "$TEMP_DIR"' EXIT
initial_password="${INIT_ADMIN_PASSWORD:?CI administrator password is required}"
new_password="${ITERFLOW_BROWSER_NEW_PASSWORD:?CI new password is required}"
username="${INIT_ADMIN_USERNAME:?CI administrator username is required}"

login="$(curl --fail --silent -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg u "$username" --arg p "$initial_password" '{username:$u,password:$p}')" \
  "$BASE/auth/login")"
token="$(jq -r '.access_token' <<< "$login")"
change="$(curl --fail --silent -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $token" \
  -d "$(jq -nc --arg c "$initial_password" --arg n "$new_password" '{current_password:$c,new_password:$n}')" \
  "$BASE/auth/change-password")"
token="$(jq -r '.access_token' <<< "$change")"

title="restore-drill-$(date +%s)"
feedback="$(curl --fail --silent -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $token" \
  -d "$(jq -nc --arg t "$title" '{title:$t,feedback_type:"SYSTEM_ISSUE",description:"Local backup restore drill"}')" \
  "$BASE/feedbacks")"
feedback_id="$(jq -r '.id' <<< "$feedback")"
printf 'iterflow restore drill %s\n' "$title" > "$TEMP_DIR/attachment.txt"
attachment="$(curl --fail --silent -H "Authorization: Bearer $token" \
  -F "file=@$TEMP_DIR/attachment.txt;type=text/plain" \
  "$BASE/feedbacks/$feedback_id/attachments")"
file_id="$(jq -r '.file_id' <<< "$attachment")"
storage_key="$("${COMPOSE[@]}" exec -T db psql -U iterflow -d iterflow -tAc \
  "SELECT storage_key FROM sys_file WHERE id=$file_id")"
[[ "$storage_key" == objects/* ]]

bash deploy/scripts/backup.sh "$TEMP_DIR/backup"
"${COMPOSE[@]}" exec -T db psql -U iterflow -d iterflow -c \
  "UPDATE rd_feedback SET title='CORRUPTED_BY_RESTORE_DRILL' WHERE id=$feedback_id"
"${COMPOSE[@]}" run -T --rm --no-deps api python -c \
  'import sys; from app.services.storage.local import LocalFileStorage; LocalFileStorage("/app/data/uploads").delete(sys.argv[1])' \
  "$storage_key"

CONFIRM_RESTORE=YES bash deploy/scripts/restore.sh "$TEMP_DIR/backup"
restored_login="$(curl --fail --silent -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg u "$username" --arg p "$new_password" '{username:$u,password:$p}')" \
  "$BASE/auth/login")"
restored_token="$(jq -r '.access_token' <<< "$restored_login")"
restored_feedback="$(curl --fail --silent -H "Authorization: Bearer $restored_token" \
  "$BASE/feedbacks/$feedback_id")"
jq -e --arg t "$title" '.title == $t' <<< "$restored_feedback"
curl --fail --silent -H "Authorization: Bearer $restored_token" \
  "$BASE/feedbacks/$feedback_id/attachments/$file_id/download" \
  -o "$TEMP_DIR/restored.txt"
[[ "$(shasum -a 256 "$TEMP_DIR/attachment.txt" | awk '{print $1}')" == \
   "$(shasum -a 256 "$TEMP_DIR/restored.txt" | awk '{print $1}')" ]]
curl --fail --silent "http://127.0.0.1:${API_PORT:-8000}/ready" | jq -e '.status == "ok"'
echo "Database, attachment and SHA256 restore drill passed"
