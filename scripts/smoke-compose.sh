#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ "${CONFIRM_EPHEMERAL_COMPOSE:-}" != "YES" ]]; then
  echo "This script destroys iterflow Compose volumes. Set CONFIRM_EPHEMERAL_COMPOSE=YES on a disposable runner." >&2
  exit 2
fi
COMPOSE=(docker compose -f deploy/docker-compose.yml)
cleanup() { "${COMPOSE[@]}" down -v --remove-orphans; }
if [[ "${KEEP_COMPOSE:-}" != "YES" ]]; then
  trap cleanup EXIT
fi
cleanup
"${COMPOSE[@]}" up -d --build
for service in db redis api web; do
  state="$("${COMPOSE[@]}" ps --format json "$service" | jq -r '.Health')"
  [[ "$state" == healthy ]] || { echo "$service is not healthy: $state" >&2; exit 1; }
done
for service in migrate seed; do
  state="$("${COMPOSE[@]}" ps --all --format json "$service" | jq -r '.State')"
  code="$("${COMPOSE[@]}" ps --all --format json "$service" | jq -r '.ExitCode')"
  [[ "$state" == exited && "$code" == 0 ]] || { echo "$service failed: $state/$code" >&2; exit 1; }
done
curl --fail --silent "http://127.0.0.1:${API_PORT:-8000}/health" | jq -e '.status == "ok"'
curl --fail --silent "http://127.0.0.1:${API_PORT:-8000}/ready" | jq -e '.status == "ok"'
curl --fail --silent "http://127.0.0.1:${WEB_PORT:-8080}/" > /dev/null
login="$(curl --fail --silent -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg u "$INIT_ADMIN_USERNAME" --arg p "$INIT_ADMIN_PASSWORD" '{username:$u,password:$p}')" \
  "http://127.0.0.1:${WEB_PORT:-8080}/api/v1/auth/login")"
token="$(jq -r '.access_token' <<< "$login")"
[[ -n "$token" && "$token" != null ]]
curl --fail --silent -H "Authorization: Bearer $token" \
  "http://127.0.0.1:${WEB_PORT:-8080}/api/v1/auth/me" | jq -e --arg u "$INIT_ADMIN_USERNAME" '.username == $u'
echo "Fresh Compose smoke passed"
