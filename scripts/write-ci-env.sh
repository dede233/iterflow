#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ci_host="iterflow.example.test"
if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
  printf '127.0.0.1 %s\n' "$ci_host" | sudo tee -a /etc/hosts > /dev/null
fi
db_password="$(openssl rand -hex 24)"
jwt_secret="$(openssl rand -hex 48)"
admin_password="$(openssl rand -hex 24)"
new_password="$(openssl rand -hex 24)"
for secret in "$db_password" "$jwt_secret" "$admin_password" "$new_password"; do
  echo "::add-mask::$secret"
done
{
  printf 'POSTGRES_PASSWORD=%s\n' "$db_password"
  printf 'DATABASE_URL=postgresql+psycopg://iterflow:%s@db:5432/iterflow\n' "$db_password"
  printf 'REDIS_URL=redis://redis:6379/0\n'
  printf 'JWT_SECRET=%s\n' "$jwt_secret"
  printf 'APP_ENV=production\nCORS_ORIGINS=\nALLOWED_HOSTS=%s\n' "$ci_host"
  printf 'TRUST_PROXY_HEADERS=true\nENABLE_API_DOCS=false\nSTORAGE_DRIVER=local\n'
  printf 'INIT_ADMIN_USERNAME=ci-admin\nINIT_ADMIN_PASSWORD=%s\n' "$admin_password"
  printf 'BUILD_SHA=%s\n' "$(git rev-parse HEAD)"
} > deploy/.env
chmod 600 deploy/.env
if [[ -n "${GITHUB_ENV:-}" ]]; then
  {
    printf 'INIT_ADMIN_USERNAME=ci-admin\n'
    printf 'INIT_ADMIN_PASSWORD=%s\n' "$admin_password"
    printf 'ITERFLOW_BROWSER_NEW_PASSWORD=%s\n' "$new_password"
    printf 'BUILD_SHA=%s\n' "$(git rev-parse HEAD)"
    printf 'ITERFLOW_WEB_HOST=%s\n' "$ci_host"
    printf 'ITERFLOW_WEB_URL=http://%s:8080\n' "$ci_host"
  } >> "$GITHUB_ENV"
fi
