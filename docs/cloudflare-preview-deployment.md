# IterFlow Cloudflare Preview

This runbook operates the independent `phase/cloudflare-preview` branch for online demonstration, trial use, and public acceptance at `https://iterflow.luqingyao.cc.cd`.

- Preview application version: **v1.8.1**.
- Released commit: `206bf0dab358917940722e1e846d8b80de3f8221` (annotated tag `v1.8.1`, tag object `38c230817fe89be86c1cc7ca431e3ebf1324e4b0`).
- Preview branch: `phase/cloudflare-preview`.
- Authorized UI v2 master baseline: `a8c58607a254c0c16e1610efc45b0e5174d9fc7c`; master CI [37742872679](https://github.com/dede233/iterflow/actions/runs/37742872679) passed all six jobs.
- Preview branch includes the reviewed UI v2 changes and additional deployment-only configuration. Application version remains **1.8.1**; this upgrade does not create or move a release/tag.
- Current authorized product baseline: `a38081af9097f691c8289e9301951a0360ea0af7`, fixing Chinese response field names and nested schema display in the protected documentation. Master CI [37875410338](https://github.com/dede233/iterflow/actions/runs/37875410338) passed all six jobs. The earlier UI v2 and initial documentation baselines remain historical upgrade references.

The Preview includes released V1.8 functionality and the existing V1.7/V1.6 functionality from the reviewed release tag. For later upgrades, merge the reviewed release tag (or separately authorized master baseline) into `phase/cloudflare-preview`, retain the deployment configuration, verify CI, and then deploy. Develop product features on their own branches, not directly on the Preview branch. Do not merge Preview deployment configuration back into master.

## Historical initial deployment

The Preview was originally created from historical base `f6a20b82b432543de4cadb2309813f376a77eaa6`. It initially included only V1.6 Phase 0 planning, synchronized from the then-common master `5c44ab849ff798ac19fdfafce558b7dbcc4452a0` by commit `6e800d8028f1827cc3ca35c4695a91de489a15ee`. At that time Phase 1 had not begun. The initial online Preview HEAD before the v1.6.0 upgrade was `fa999d91b3271535b46ec681408ce7f64cda8bac`. These are historical deployment facts, not the current application baseline.

## Historical V1.6.0 Preview upgrade

The V1.6.0 upgrade retained the initial Preview deployment configuration and merged released commit `f0aa8475ff081fc963cdd08045d23e383a3c594e` (annotated tag `v1.6.0`). Its final Preview HEAD was `33d36d78ab4bedf48835d124f295f1ca8c352eae`; this is the pre-V1.7 upgrade baseline and rollback code reference, not the current application version. Both the initial deployment history above and the released V1.6/V1.5 tags remain immutable.

## Historical V1.7.0 Preview upgrade

The V1.7.0 upgrade merged released commit `e485efea0155c5b4194f563926a531d606c77349` through Preview merge `ff3eb7c39b9e60a2f7157f4e777766064ce24495`. Its final Preview HEAD was `79fa39d3611c166c992d5cbdf8d6c3757506ee46`. This is the pre-V1.8 upgrade rollback code reference, not the current application baseline. Code rollback alone does not authorize restoring or replacing trial data.

## Historical V1.8.0 Preview upgrade and V1.8.1 resume

The V1.8.0 Preview upgrade merged released commit `df9e1ba1a5ee1a4c763098d8e180250f409bedd3` through Preview merge `df685f42b538bceb51ab5bf4715ea9c0716b8b51`; its final runbook / deployed HEAD was `c77850b83ee96874df46fd12bbe6e291d2caeacb`. Acceptance correctly reached **HARD STOP** because the formal V1.8.0 shared PageHeader overflowed at 768px. Infrastructure was healthy and the Preview branch did not patch product code.

The externally reviewed fix is now formally released as **v1.8.1**, after release branch CI `37216956699` and final master CI `37217382411`, both attempt 1 / six jobs success. Preview merge `28dc66305b26de6c31e6a89a7a2cf5a5c73a9ab5` has parents `c77850b83ee96874df46fd12bbe6e291d2caeacb` and `206bf0dab358917940722e1e846d8b80de3f8221`. Product code equals v1.8.1 and the existing infrastructure patch is unchanged. The original product defect is resolved by the formal patch; public acceptance remains **PENDING** until the new Preview CI, pre-hotfix backup and real upgrade pass and the 768px defect is verified first.

Retain `/Users/xiaweiyi/Developer/backups/iterflow-preview-pre-v1.8.0-20261003-1330` and test feedback `FB-20261003-0001 / ID 10`. Before this upgrade, take an additional `preview-pre-v1.8.1-hotfix-<timestamp>` backup with the Preview env/override and the currently running build `c77850b`; verify SHA256SUMS. After upgrade, accept Feedback Detail at 768px first (scrollWidth ≤769, readable heading, visible actions and close-dialog cancellation), then the full 375/390/768/1280/1440 matrix on Feedback/Requirement/Version. Resume C0/C1/C3/C4, old attachment public SHA256, authorized new attachment round-trip, V1.7 compatibility and security checks. Restart only api/web/cloudflared and take a separate post-v1.8.1 backup after persistence checks. Never restore real Preview, delete its volumes or deploy Production during this task.

## Authorized UI v2 Preview upgrade (2026-10-08)

The user authorized merging `refactor/ui-v2` into master and updating the existing Cloudflare Preview. The reviewed source is `a274226c189bbae8a187d80f3e853ef447b077fa` (branch CI [37740729231](https://github.com/dede233/iterflow/actions/runs/37740729231), six jobs success). Master merge `a8c58607a254c0c16e1610efc45b0e5174d9fc7c` passed a fresh six-job CI. Preview merge `79d09eaf04c9d06eebf8284ce7dc922d14ea67e7` retains the old Preview `72fd16ed06862daff473e100cf689e19223201da` and the authorized master as parents. Backend, frontend and contract trees equal master; deployment scripts/configuration and Preview CI additions are unchanged.

This upgrade includes UI v2 styling and fixes for Feedback/Requirement/Version drawers: selected IDs load correctly, returning closes the drawer, full-screen navigation retains applied list context, and successful writes refresh the filtered list. There are no backend, schema, migration, permission or contract changes.

Deployment gates remain: new Preview six-job CI, a separate verified pre-upgrade backup using the **currently running `BUILD_SHA=72fd16e`**, rebuild with the final checked-out Preview SHA, public original-password login and detail-drawer acceptance, existing data and attachment hash checks, api/web/cloudflared restart persistence, and a separate verified post-upgrade backup. Keep the original administrator password and all Preview volumes. Do not restore real data, deploy Production, or change historical tags. At the time this runbook update is committed, Preview CI and live upgrade acceptance are pending; record actual deployment evidence outside the repository alongside the backups.

## Authorized protected documentation upgrade (2026-10-08)

The user authorized a documentation entry for administrators and development leads on the existing Preview. Feature commit `66f0057774ea873b6d01b785ea13cec5c052b5fc` passed branch CI [37768077532](https://github.com/dede233/iterflow/actions/runs/37768077532); master merge `e77d8d93f80f6c4e08823c878c70c1457e6d94b3` passed a fresh six-job CI. Preview merge `3f1ac85770b5330171cdb08b9593876f478cc6f6` retains the previously deployed `886ddf60f001943fc353f035460900c189c984cc` and authorized master as parents. Backend, frontend and contract trees equal master; infrastructure and CI patches are unchanged.

Desktop entry: System Settings → API Documentation; mobile entry: Profile → API Documentation; page `/#/admin/api-docs`. Authenticated `GET /api/v1/docs/openapi` checks the current enabled system role `SUPER_ADMIN` or `DEVELOPMENT_LEAD` on every read, responds with private/no-store Chinese runtime documentation and records an audit entry. The working contract is `spec/openapi-development.yaml`, adding only the documentation route and optional AuthMe eligibility field. No migration, permission, business workflow or formal version changes are introduced. Keep production public documentation disabled and `ENABLE_API_DOCS=false`; the existing `/api/` proxy already serves this endpoint.

Before upgrade, require final Preview six-job CI and a separate checksum-verified backup with the **currently running `BUILD_SHA=886ddf6`**. Deploy images using final checked-out Preview SHA while retaining all trial accounts, original passwords and volumes. Verify public original-password login, desktop/mobile documentation/search/download, anonymous denial, existing detail pages, business data and six existing attachment hashes. Restart only api/web/cloudflared, repeat persistence checks and take a separate checksum-verified post-upgrade backup. No real restore, Production deployment, historical tag change or new Release is authorized. At this runbook commit, Preview CI and live deployment remain pending; record actual outcomes outside the repository beside the backups.

## Authorized documentation field fix (2026-10-09)

The user reported missing Chinese response field names in the protected documentation. Feature commit `63ad771f76aed3c08e44d8f0c057b7d668aa3f2a` passed branch CI [37874946384](https://github.com/dede233/iterflow/actions/runs/37874946384); master `a38081af9097f691c8289e9301951a0360ea0af7` passed a fresh six-job CI. Preview merge `725a6a93397f3c64a611c9e5a5fb7e3b543e52ab` has the previously deployed `ad02735379f40273401b5427f92a0d7bf958a7d9` and authorized master as parents. Product trees equal master; infrastructure and CI additions are unchanged.

The working contract adds Chinese titles to 397 model fields, and the sync/bundle/protected-read pipeline retains schema title/description annotations without changing runtime field names, types, references, required flags or enum values. The page displays both field names and Chinese names, and supports paginated items, arrays and nullable referenced objects with bounded nested expansion. Existing role checks, public documentation blocking, core API shape, version metadata, permissions and migrations remain unchanged. Historical released contracts are immutable.

Require final Preview six-job CI, a separate verified pre-fix backup using **currently running `BUILD_SHA=ad02735`**, deployment using final Preview HEAD, original-password public login and Chinese field/child-field acceptance at desktop/mobile widths, existing business/account/attachment checks, api/web/cloudflared restart persistence, and a separate verified post-fix backup. Do not alter trial roles for smoke, restore real data, delete volumes, operate Production or create/move a Release/Tag. This runbook commit records CI/live deployment as pending; actual results belong in the independent backup evidence directory.

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

From a device outside the Docker host, confirm valid HTTPS, the login page, Hash Router navigation, and same-origin `/api/` calls. On initial installation only, change the administrator first-use password. During upgrades, retain the existing password and verify administrator login, Home, Feedback, Requirement, Version, Release Detail, Notification, Profile, and authorized Audit pages. Verify Editing Presence, Revision Conflict UX, notification badge/read-all, list filters, and Dashboard Activity. Submit a trial Feedback; upload/download an allowed file; compare its downloaded SHA256 with the uploaded file; verify an unauthorized account cannot download it. Repeat key pages at 375px and 1440px. Verify that host public interfaces do not expose 5432, 6379, 8000, 8080, or the four diagnostic ports; the only public entry must be Cloudflare HTTPS 443. Restart the Compose services and check both public health endpoints and retained trial data.

## V1.8 deployment smoke

The released V1.8 product tree is the only source for Backend, Frontend and OpenAPI. Merge the released commit with `--no-ff`, verify both old Preview and release ancestors, and compare the Preview infrastructure patch before and after the merge. The Preview branch CI must include the merged Cloudflare Compose validation and all six jobs. Preserve the first failure evidence; only a proven transient infrastructure failure permits one failed-job rerun at the same HEAD.

Public acceptance supplements the released CI:

- C4 URL query / return context: apply a real list filter, reload, open detail and return, then use browser back/forward. The URL and renewed API request must retain the applied context. In a disposable session, reject external `return_to` and fall back to the internal list; never corrupt the real administrator session.
- C3 main-chain navigation: follow an accessible Feedback → Requirement → Version → Release relationship and verify metadata and targets. Admin public smoke proves positive paths; SELF/ALL negative visibility remains backed by the released real API/CI tests when no existing restricted trial account is available. Do not alter existing roles to manufacture evidence.
- C1 scoped selectors: open Feedback-to-Requirement, Requirement-to-Version, Version-add-Requirement and Requirement-move-Version selectors. Check paging/search, no results, cancel/clear and mobile layout. At least one safe write on explicitly new Preview test data must submit the latest revision and pass the server CAS/authorization checks. Do not mutate existing trial relationships for smoke.
- C0 Version worklist: verify visible-scope progress, pending/blocked summary, state/keyword/priority filtering and reset, plus the visibility/real server publish-authority explanation. A safe existing READY test version may run publish/check to verify Chinese blockers; do not publish an existing trial version merely for acceptance.
- Check Home, Feedback, Requirement, Version, Release, Notification, Profile and authorized Audit pages, desktop version `V1.8.1`, same-origin API requests and Hash Router. Keep mobile AuthShell footer hiding as designed.
- Repeat selectors, worklists, filters and details at 375/390/768/1280/1440px; record actual public UI evidence (375px and 1440px screenshots recommended), including no unintended horizontal overflow.
- Before upgrade, record existing trial object IDs/relationships and an existing attachment SHA256; verify migration `0004_integrity` and a separate checksummed pre-upgrade backup outside the repository. After upgrade, verify old data and the old hash, upload/download a new small test attachment with matching SHA256 and prove unauthenticated download still fails.
- After public acceptance, restart only api/web/cloudflared, recheck public health/readiness, original-password login, old data and old attachment SHA256, then create a different checksummed post-upgrade backup outside the repository. Do not execute restore against actual Preview volumes.

## V1.7 deployment smoke (historical / compatibility regression)

The released V1.7 CI proves full feature correctness. Public deployment smoke additionally verifies:

- The historical V1.7 AuthShell version was `ITERFLOW / V1.7.0`; the current V1.8.1 upgrade must display `ITERFLOW / V1.8.1` at 768px and 1440px. Mobile footer hiding remains expected.
- Feedback keyword `%`, `_`, and backslash are literal substrings (sample at least two); permissions, DataScope and pagination continue to apply. This is a compatibility change from SQL wildcard semantics.
- Release local date range is start inclusive and includes the whole selected end day by sending `released_before` as next local day 00:00 exclusive; combines with existing `version_id`.
- Notification badge refreshes on focus / hidden-to-visible with a shared 30-second attempt cooldown; short repeated focus must not create a request storm. No polling/WebSocket/SSE is introduced. Use two disposable sessions and a real notification-producing business action.
- Hash authentication failure in a disposable session retains the internal route and query through login; external redirect is rejected. Never alter the real administrator token for smoke.
- Quickly changing Feedback/Audit filters and opening/closing Audit detail must not restore stale results or reopen a closed dialog. Deterministic races remain covered by released CI.

Before upgrading, verify the existing administrator password, capture existing record IDs and an attachment SHA256, and take a checksummed backup. After CI passes, rebuild with the final Preview short SHA while retaining `iterflow-preview_pgdata`, `iterflow-preview_redisdata`, and `iterflow-preview_uploads`. Verify revision `0004_integrity`, local/public health and readiness, original-password login, old/new attachment hashes, and all V1.6 smoke pages. Restart only api/web/cloudflared, repeat persistence checks and take a separate post-upgrade backup. Do not execute destructive restore against the actual Preview.

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
