#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ "${CONFIRM_EPHEMERAL_COMPOSE:-}" != "YES" ]]; then
  echo "This script destroys iterflow Compose volumes. Set CONFIRM_EPHEMERAL_COMPOSE=YES on a disposable runner." >&2
  exit 2
fi
COMPOSE=(docker compose -f deploy/docker-compose.yml)
web_host="${ITERFLOW_WEB_HOST:-127.0.0.1}"
cleanup() { "${COMPOSE[@]}" down -v --remove-orphans; }
if [[ "${KEEP_COMPOSE:-}" != "YES" ]]; then
  trap cleanup EXIT
fi
cleanup
"${COMPOSE[@]}" up -d --build
for service in db redis api web; do
  state=""
  for attempt in {1..40}; do
    state="$("${COMPOSE[@]}" ps --format json "$service" | jq -r '.Health')"
    [[ "$state" == healthy ]] && break
    [[ "$state" == unhealthy ]] && break
    sleep 2
  done
  if [[ "$state" != healthy ]]; then
    echo "$service is not healthy: $state" >&2
    "${COMPOSE[@]}" logs --tail 80 "$service" >&2
    exit 1
  fi
done
for service in migrate seed; do
  state="$("${COMPOSE[@]}" ps --all --format json "$service" | jq -r '.State')"
  code="$("${COMPOSE[@]}" ps --all --format json "$service" | jq -r '.ExitCode')"
  [[ "$state" == exited && "$code" == 0 ]] || { echo "$service failed: $state/$code" >&2; exit 1; }
done
curl --fail --silent -H "Host: $web_host" "http://127.0.0.1:${API_PORT:-8000}/health" | jq -e '.status == "ok"'
curl --fail --silent -H "Host: $web_host" "http://127.0.0.1:${API_PORT:-8000}/ready" | jq -e '.status == "ok"'
invalid_host_status="$(curl --silent -o /dev/null -w '%{http_code}' -H 'Host: attacker.invalid' "http://127.0.0.1:${API_PORT:-8000}/health")"
[[ "$invalid_host_status" == 400 ]]
curl --fail --silent "http://$web_host:${WEB_PORT:-8080}/" > /dev/null
login="$(curl --fail --silent -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg u "$INIT_ADMIN_USERNAME" --arg p "$INIT_ADMIN_PASSWORD" '{username:$u,password:$p}')" \
  "http://$web_host:${WEB_PORT:-8080}/api/v1/auth/login")"
token="$(jq -r '.access_token' <<< "$login")"
[[ -n "$token" && "$token" != null ]]
curl --fail --silent -H "Authorization: Bearer $token" \
  "http://$web_host:${WEB_PORT:-8080}/api/v1/auth/me" | jq -e --arg u "$INIT_ADMIN_USERNAME" '.username == $u'

# This must traverse Web Nginx before the API writes its audit row.
proxy_status="$(curl --silent -o /dev/null -w '%{http_code}' \
  -H 'Content-Type: application/json' -H 'X-Real-IP: 203.0.113.10' \
  -H 'X-Request-ID: proxy-ip-smoke' \
  -d '{"username":"proxy-smoke-nonexistent","password":"invalid"}' \
  "http://$web_host:${WEB_PORT:-8080}/api/v1/auth/login")"
[[ "$proxy_status" == 401 ]]
audit_ip="$("${COMPOSE[@]}" exec -T db psql -U iterflow -d iterflow -tAc \
  "SELECT ip_address FROM sys_operation_log WHERE request_id='proxy-ip-smoke' ORDER BY id DESC LIMIT 1")"
[[ "$audit_ip" == 203.0.113.10 ]]
echo "Fresh Compose smoke passed"
