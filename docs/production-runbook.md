# 迭程 IterFlow 生产运维手册（Phase 8.3）

## 首次安装

要求 Docker Engine、Compose v2、可靠的 PostgreSQL/Redis 卷、备份存储与前置 HTTPS 代理。复制根目录 `.env.example` 为 `deploy/.env`（Compose 文件位于 `deploy/`，默认从其项目目录读取环境文件），权限设为仅部署用户可读。填写 `POSTGRES_PASSWORD`、Docker 网络内的 `DATABASE_URL`、`REDIS_URL`、至少 32 字节随机 `JWT_SECRET`、`INIT_ADMIN_USERNAME` 和 20 位以上随机 `INIT_ADMIN_PASSWORD`。生产设置 `APP_ENV=production`、实际 `ALLOWED_HOSTS`、`TRUST_PROXY_HEADERS=true`、`ENABLE_API_DOCS=false`、`BUILD_SHA` 为部署提交 SHA；同源部署可令 `CORS_ORIGINS` 为空。不可配置通配 Host 或带凭据的通配 CORS。配置 `WEB_BIND_HOST=127.0.0.1`，由 HTTPS 反向代理向外提供服务；**不得直接公开纯 HTTP 8080 端口**。本阶段不签发 TLS 证书。

执行 `docker compose -f deploy/docker-compose.yml up -d --build`。启动顺序为 `db healthy → migrate exit 0 → seed exit 0 → api healthy → web healthy`，迁移或初始化失败则 API 不启动。首次创建管理员后立即登录并按提示修改密码。此后可将 `INIT_ADMIN_PASSWORD` 留空：seed 仍修复系统角色、权限和关联，但不覆盖管理员已有密码。检查 `docker compose -f deploy/docker-compose.yml ps -a`、`curl http://127.0.0.1:8000/health`、`curl http://127.0.0.1:8000/ready`，并通过 Web 登录。

## 存储与网络

Local Storage 使用独立 `iterflow_uploads` 命名卷；数据库与 Redis 分别为 `iterflow_pgdata` 和 `iterflow_redisdata`。API 在普通 `iterflow` 用户下写入 `/app/data/uploads`。`STORAGE_DRIVER=s3` 时填写 bucket、区域与可选 endpoint；若显式填写 access key，secret key 必须配套。AWS IAM 默认凭据链无需显式密钥。S3 bucket 应由部署者预先创建，`/ready` 仅 `head_bucket`，绝不自动建桶。S3 模式下 `uploads` 卷虽然仍挂载但不用于持久对象数据。

Web、API、PostgreSQL、Redis 默认仅绑定本机回环地址。反向代理必须只把可信 `X-Real-IP`、`X-Forwarded-*` 头传给 API；若绕过代理直连 API，应关闭 `TRUST_PROXY_HEADERS`。Nginx 的 52 MiB body 上限容纳 50 MiB 附件与 multipart 开销。生产 JSON 运行日志写 stdout，可用 `docker compose -f deploy/docker-compose.yml logs api` 查看；按 `request_id` 关联业务审计。日志不得导出密码、Token 或存储密钥。

## 备份

Local Storage：在维护窗口短暂停写，执行 `bash deploy/scripts/backup.sh /absolute/new/backup-directory`。脚本先停止 Web/API，再备份 PostgreSQL 和 uploads，生成 `manifest.json` 与 `SHA256SUMS`，最后恢复服务。备份目录必须不存在且应位于受保护的独立介质；验证 `shasum -a 256 -c SHA256SUMS`，并做周期性恢复演练。Redis 只持有可重建的编辑提示等数据；RefreshSession 在 PostgreSQL，Redis 不作为业务持久备份。脚本会拒绝 S3 模式。

S3 模式：仍对 PostgreSQL 做一致性 `pg_dump`，但对象必须使用实际服务商的 Versioning、Snapshot、Replication 或 Provider Backup 机制；升级前验证对象恢复点与数据库备份时间一致。不要把 Local Storage 脚本误当通用 S3 备份。

## 恢复与回滚

恢复会覆盖当前数据库和 uploads，仅在维护窗口由授权运维执行。先保留现有环境额外备份，并核验目标备份文件、清单和校验和。运行 `CONFIRM_RESTORE=YES bash deploy/scripts/restore.sh /absolute/backup-directory`。脚本停止入口，恢复数据库、恢复附件、读取 `alembic_version`，再运行 migrate/seed 并检查 `/ready`。恢复完成还必须人工验证登录、反馈查询、业务附件下载及其 SHA256。脚本失败时保持服务停止，不要向用户开放不完整数据。

默认生产回滚不是 `alembic downgrade`。恢复升级前数据库备份和对应 uploads/S3 对象恢复点，切回前一个已验证 tag/image，重新启动并运行健康检查与浏览器 smoke。Phase 8.3 不新增 migration；未来若某版本声明支持无损 downgrade，需单独评估。

## 升级标准流程

1. 确认目标提交、tag、镜像与全部 CI 门禁通过；记录回滚版本。
2. 在维护窗口执行并验证数据库+对象备份，确认可恢复点。
3. 获取已审代码/镜像，设置 `BUILD_SHA` 为实际 Git SHA。
4. 执行 `docker compose -f deploy/docker-compose.yml up -d --build`，检查 migrate/seed 成功。
5. 验证 `/health`、`/ready`、Web、管理员登录和浏览器 smoke；核对 `/health.build_sha`。
6. 观察 JSON 日志、告警与业务附件访问，再结束维护窗口。

本地门禁：`bash scripts/release-check.sh local`；Docker 环境门禁：`bash scripts/release-check.sh docker`。破坏性 fresh-volume smoke 仅在一次性环境使用 `CONFIRM_EPHEMERAL_COMPOSE=YES bash scripts/smoke-compose.sh`，会删除当前 IterFlow Compose 命名卷。

## 故障定位

- `migrate` 失败：查看 `docker compose -f deploy/docker-compose.yml logs migrate`，核对数据库连接和 migration 链；不要跳过迁移直接启动 API。
- `seed` 失败：首次检查管理员用户名及 8–128 位密码；已有管理员可清除 bootstrap 密码。
- `/ready` 503：查看响应 `components`，分别排查 PostgreSQL、Redis、Local Storage 权限或 S3 bucket/凭据；S3 探针不会写入。
- Web 400 Host：核对 `ALLOWED_HOSTS` 与前置代理传递的 `Host`。
- 文件上传 413/超时：核对前置代理与内置 Nginx 的 52 MiB 限制及 120 秒超时。
- 静态资源旧版本：检查 `index.html` 的 `no-cache` 与 hash assets 的 immutable 缓存配置。
