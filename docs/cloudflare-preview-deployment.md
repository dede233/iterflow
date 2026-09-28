# IterFlow Initial Online Preview

This runbook deploys the V1.5 baseline on the independent `phase/cloudflare-preview` branch. It is an online trial, not the production release. The branch starts at `f6a20b82b432543de4cadb2309813f376a77eaa6`; do not merge the V1.6 planning branch into it.

## Architecture and prerequisites

```text
Internet HTTPS :443 → Cloudflare DNS/edge → remotely managed Tunnel
  → cloudflared (Docker network) → web:8080 (Nginx)
      /          → Vue 3 Hash Router
      /api/*     → api:8000 (FastAPI)
      /health    → api:8000/health
      /ready     → api:8000/ready
  api → db (PostgreSQL), redis, uploads (LocalFileStorage)
```

Use a Docker Engine host with Compose v2, outbound connectivity to Cloudflare, this branch checked out, and a Cloudflare account managing the `luqingyao.cc.cd` zone. Keep this host and its Docker volumes available during the trial. No inbound router port forwarding is needed. [Cloudflare's tunnel setup](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/) documents the current Dashboard flow; check its certificate requirements if the hostname is nested below a different zone.

The stack uses project `iterflow-preview`, containers prefixed `iterflow-preview`, and separate named volumes `iterflow-preview_pgdata`, `iterflow-preview_redisdata`, and `iterflow-preview_uploads`. PostgreSQL, Redis, API, and Web diagnostic ports bind only to `127.0.0.1` at 55432, 56379, 18000, and 18080 respectively. The tunnel has no published port. Do not expose these ports through a host firewall, router, or another proxy. Preview pins `cloudflared` to HTTP/2 over outbound TCP port 7844 because this host's QUIC/UDP connections to Cloudflare time out; allow that egress in the host network and firewall.

## Cloudflare Dashboard

1. Go to **Networking → Tunnels → Create a tunnel**. Create a **remotely managed** tunnel named `iterflow-preview` and choose Docker. Keep its token private.
2. On that tunnel's **Routes** tab, add a **Published application** with hostname `iterflow.luqingyao.cc.cd` and service URL `http://web:8080`. Use HTTP to the Docker origin; public TLS terminates at Cloudflare. Do not create a public A record to the Docker host.
3. Confirm Cloudflare creates/routes the tunnel DNS entry and serves a valid HTTPS certificate for the hostname. Do not use a TryCloudflare quick tunnel for the final address.

The Dashboard or account administrator must perform these steps. A tunnel token permits a connector to join this tunnel, so treat it as a secret; [Cloudflare documents token rotation](https://developers.cloudflare.com/tunnel/reference/tunnel-tokens/).

## Environment and first start

From the repository root on the Docker host:

```bash
cp deploy/.env.preview.example deploy/.env.preview
chmod 600 deploy/.env.preview
```

Fill the blank `POSTGRES_PASSWORD`, `DATABASE_URL`, `JWT_SECRET`, `INIT_ADMIN_PASSWORD`, and `CLOUDFLARE_TUNNEL_TOKEN` values in `deploy/.env.preview`. Use a random database password, a JWT secret of at least 32 random bytes, and a random administrator password of at least 20 characters. Set `DATABASE_URL` to a PostgreSQL URL using `db:5432`, database/user `iterflow`, and that database password. Percent-encode password characters that are special in a URL. Never commit or paste this file, the token, or rendered `docker compose config` output. After the administrator logs in and changes the first-use password, clear `INIT_ADMIN_PASSWORD` in this file; seed will not reset an existing administrator password.

Keep `ALLOWED_HOSTS=iterflow.luqingyao.cc.cd`, `CORS_ORIGINS=` (empty), `APP_ENV=production`, `ENABLE_API_DOCS=false`, `STORAGE_DRIVER=local`, and `WEB_BIND_HOST=127.0.0.1`. `TRUST_PROXY_HEADERS=true` is safe here only because the Preview Nginx configuration replaces client-supplied `X-Real-IP` with its direct peer address. See the client IP limitation below.

**The one startup command** (also used after updating the checked-out preview branch):

```bash
BUILD_SHA="$(git rev-parse --short HEAD)" docker compose --env-file deploy/.env.preview -f deploy/docker-compose.yml -f deploy/docker-compose.cloudflare.yml --profile cloudflare up -d --build
```

Startup gates are `db healthy → migrate completed → seed completed → api healthy → web healthy → cloudflared`. Do not bypass migration, seed, or health checks. The Docker daemon must start automatically after host reboot for the `unless-stopped` services to recover.

## Operate, upgrade, and stop

Before each upgrade, take and verify a backup below, check CI, and then pull only `phase/cloudflare-preview` on the host. Run the startup command again; `BUILD_SHA` tags images with the checked-out commit. Inspect status and recent logs without printing environment/config values:

```bash
docker compose --env-file deploy/.env.preview -f deploy/docker-compose.yml -f deploy/docker-compose.cloudflare.yml --profile cloudflare ps -a
docker compose --env-file deploy/.env.preview -f deploy/docker-compose.yml -f deploy/docker-compose.cloudflare.yml --profile cloudflare logs --tail=100 db migrate seed api web cloudflared
```

Stop the Preview while retaining all named volumes:

```bash
docker compose --env-file deploy/.env.preview -f deploy/docker-compose.yml -f deploy/docker-compose.cloudflare.yml --profile cloudflare down
```

Never use `down -v` against trial data. To take the public site permanently offline, first disable/delete the published application route and tunnel in Cloudflare Dashboard, then stop the Compose stack and remove its DNS route after confirming it is no longer needed.

## Health and acceptance

Validate the merged Compose model without displaying secrets:

```bash
docker compose --env-file deploy/.env.preview -f deploy/docker-compose.yml -f deploy/docker-compose.cloudflare.yml --profile cloudflare config --quiet
```

Check local diagnostic entry points and then **check the public URL separately**:

```bash
curl --fail --silent --show-error -H 'Host: iterflow.luqingyao.cc.cd' http://127.0.0.1:18000/health
curl --fail --silent --show-error -H 'Host: iterflow.luqingyao.cc.cd' http://127.0.0.1:18000/ready
curl --fail --silent --show-error https://iterflow.luqingyao.cc.cd/health
curl --fail --silent --show-error https://iterflow.luqingyao.cc.cd/ready
```

From a device outside the Docker host, confirm valid HTTPS, the login page, Hash Router navigation, and same-origin `/api/` calls. Log in as the preview administrator, change the first-use password, then inspect Home, Feedback, Requirement, Version, Notification, and Profile. Submit a trial Feedback; upload/download an allowed file; compare its downloaded SHA256 with the uploaded file; verify an unauthorized account cannot download it. Repeat key pages at 375px and 1440px. Verify that host public interfaces do not expose 5432, 6379, 8000, 8080, or the four diagnostic ports; the only public entry must be Cloudflare HTTPS 443. Restart the Compose services and check both public health endpoints and retained trial data.

## Backup and restore

The existing LocalFileStorage backup and restore scripts accept optional Compose selection variables. Run from the repository root. Backups stop Web/API briefly, include PostgreSQL and uploads, and create `SHA256SUMS`; store them outside the repository on protected media.

```bash
ITERFLOW_COMPOSE_ENV_FILE=deploy/.env.preview ITERFLOW_COMPOSE_OVERRIDE=deploy/docker-compose.cloudflare.yml bash deploy/scripts/backup.sh /absolute/new/preview-backup-directory
(cd /absolute/new/preview-backup-directory && shasum -a 256 -c SHA256SUMS)
```

Restore is destructive: take a fresh backup first, verify the target archive/checksums, then run during a maintenance window. It replaces this Preview project's database and uploads, not the development volumes. Confirm login and file SHA256 after restoration.

```bash
CONFIRM_RESTORE=YES ITERFLOW_COMPOSE_ENV_FILE=deploy/.env.preview ITERFLOW_COMPOSE_OVERRIDE=deploy/docker-compose.cloudflare.yml bash deploy/scripts/restore.sh /absolute/existing/preview-backup-directory
```

Never point the restore script at the ordinary `iterflow` project by omitting the Preview selection variables.

## Token rotation and troubleshooting

In Cloudflare Dashboard, open this tunnel, refresh the token, replace only `CLOUDFLARE_TUNNEL_TOKEN` in the protected env file, and recreate the connector with the startup command. Expect a short outage with one connector; schedule rotation accordingly. Do not put the token on a command line or in logs. `cloudflared` reads it through `TUNNEL_TOKEN` environment variable, as in [Cloudflare's container guidance](https://developers.cloudflare.com/tunnel/guides/kubernetes/).

- Tunnel down: confirm `web` is healthy, `cloudflared` logs show a connection, outbound TCP traffic to Cloudflare on port 7844 works, and the Published application targets `http://web:8080`.
- 502 at the edge: check the tunnel route/service URL and `web` health; the connector and Web must share this Compose network.
- 400 Host: verify exact `ALLOWED_HOSTS` and the published hostname. Keep CORS empty for the same-origin Web/API path.
- `/ready` fails: inspect API, PostgreSQL, Redis, and LocalFileStorage readiness; migration and seed must complete.
- Upload 413/timeout: inspect Cloudflare plan limits and the Nginx 52 MiB request-body limit.
- Audit client IP: the safe Preview proxy configuration ignores `CF-Connecting-IP`, incoming `X-Forwarded-For`, and incoming `X-Real-IP`, then sets `X-Real-IP` to the direct connector address. Audit therefore records the `cloudflared` container IP, not the real browser IP. Do not enable forwarded client IP without a separately verified, restricted trusted-proxy chain.
