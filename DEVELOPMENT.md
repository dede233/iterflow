# DEVELOPMENT.md


## 项目命名

本项目正式产品名确定为：

- **中文名：迭程**
- **英文名：IterFlow**
- **完整名称：迭程 IterFlow · 需求与版本协作管理系统**
- **核心含义：迭代 + 流程，覆盖 Feedback → Requirement → Version → Release 的完整协作链路。**

建议统一使用以下工程命名：

```text
产品名：IterFlow
主仓库：iterflow
后端服务：iterflow-api
前端服务：iterflow-web
数据库：iterflow
PostgreSQL 服务：iterflow-db
Redis 服务：iterflow-redis
对象存储：本地默认使用 LocalFileStorage，生产可配置 S3Storage
```

对外页面与文档优先显示“迭程 IterFlow”；代码、仓库、容器和服务名统一使用小写英文 `iterflow` 前缀。

如后续需要调整品牌视觉，可修改 Logo、登录页标题和文案，但不要因此改变核心业务模型或接口契约。

## 1. 开发目标

本仓库用于实现“需求与版本管理系统”独立部署版 V1.5。

完成标准不是“代码已生成”，而是：

`docker compose up -d`

后可以通过浏览器实际完成：

`登录 -> 提交反馈 -> 转正式需求 -> 加入版本 -> 状态流转 -> 发布版本 -> 反馈显示已上线`

并支持 PC 与移动端核心操作。

## 2. 目录

```text
.
├── AGENTS.md
├── DEVELOPMENT.md
├── TASKS.md
├── README.md
├── docs/
├── spec/
├── backend/
├── frontend/
└── deploy/
```

### 规格
- `docs/`：V1.5 主文档 PDF/Word
- `spec/openapi-v1.5.yaml`：API 契约
- `spec/status-machines.md`：状态机

## 3. 本地环境

建议：
- ServBay（可直接提供 Python、PostgreSQL、Redis 与 Nginx/Caddy），或 Docker Engine / Docker Desktop
- Docker Compose v2（使用容器开发时）
- Python 3.12+
- Node.js 20+ 或 22+
- npm 10+
- PostgreSQL/Redis 可使用 ServBay 或 Docker
- 本地对象存储默认使用 LocalFileStorage，不要求启动 S3 服务

## 4. 环境变量

从根目录复制：

```bash
cp .env.example .env
```

生产/共享环境禁止继续使用示例密码。

重要变量至少包括：
- DATABASE_URL
- REDIS_URL
- JWT_SECRET
- JWT_ACCESS_TTL_MINUTES
- JWT_REFRESH_TTL_DAYS
- STORAGE_DRIVER
- LOCAL_STORAGE_PATH
- S3_ENDPOINT
- S3_ACCESS_KEY
- S3_SECRET_KEY
- S3_BUCKET
- S3_REGION
- INIT_ADMIN_USERNAME
- INIT_ADMIN_PASSWORD

本地开发使用 `STORAGE_DRIVER=local` 与 `LOCAL_STORAGE_PATH=./data/uploads`。相对路径以项目根目录解析；物理路径不作为业务主数据，数据库只保存 `storage_key` 等文件元数据。

切换到标准 S3 API 时设置 `STORAGE_DRIVER=s3` 以及 `S3_*` 变量。`S3Storage` 使用 boto3 标准 S3 API，不绑定特定厂商，可连接 SeaweedFS、RustFS、AWS S3 或其他 S3 Compatible Object Storage。

业务代码只依赖 `StorageService`，不得直接调用 boto3 或厂商 SDK。文件表保存 `original_name`、`storage_key`、`size`、`mime_type`、`sha256`、`storage_driver`、`created_at`、`created_by`，业务关系使用 `file_id`。

LocalFileStorage 的 `storage_key` 必须由系统生成；实现需拒绝绝对路径、`..` 和解析后逃逸存储根目录的路径。附件下载先经过 IterFlow 后端鉴权；S3 模式可以在鉴权后签发短时有效的 signed URL。

Docker Compose 另需 `POSTGRES_PASSWORD` 用于初始化 PostgreSQL；该变量不会传入 API。`.env.example` 中所有凭据均留空，启动前必须显式填写。Docker 内的 `DATABASE_URL` 需使用服务名 `db`。

## 5. 基础设施启动

```bash
docker compose -f deploy/docker-compose.yml up -d db redis
```

若 PostgreSQL 与 Redis 已由 ServBay 启动，可以跳过此步并在 `.env` 中填写本机连接地址。生产 Compose 包含 `db`、`redis`、一次性的 `migrate`/`seed`、`api` 与 `web`；S3 自托管服务不是强制依赖。

检查容器：

```bash
docker compose -f deploy/docker-compose.yml ps
```

## 6. Backend

进入：

```bash
cd backend
```

建议虚拟环境：

```bash
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

安装：

```bash
pip install -e ".[dev]"
```

Migration：

```bash
alembic upgrade head
```

初始化管理员和基础权限：

```bash
python -m app.cli.seed
```

启动：

```bash
uvicorn app.main:app --reload --port 8000
```

健康检查：

```text
GET http://localhost:8000/health
```

API 文档：

```text
http://localhost:8000/docs
```

健康检查：

```text
GET http://localhost:8000/health  # 仅进程存活
GET http://localhost:8000/ready   # PostgreSQL / Redis / 当前 Storage Driver 就绪
```

## 7. Frontend

```bash
cd frontend
npm install
npm run dev
```

构建：

```bash
npm run build
```

如果构建失败，不进入下一阶段。

## 8. 测试

Backend：

```bash
cd backend
pytest -q
```

代码检查：

```bash
ruff check app tests
```

可选类型检查：

```bash
mypy app
```

Frontend：

```bash
cd frontend
npm run build
```

如项目已补齐 Vitest：

```bash
npm run test
```

## 9. Docker 全量启动

配置根目录 `.env` 后一键启动：

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

最终应做到：
- Web 可访问
- API 健康
- DB migration 成功
- Redis 可用
- LocalFileStorage 可读写；配置 S3 时 S3Storage 可连接
- 登录可用
- 主链路可用

`migrate` 与 `seed` 自动执行，失败则 API 不启动。首次管理员密码仅首次创建时必需；已有管理员时可留空。生产 Web 默认只绑定回环地址，公网接入必须经 HTTPS 反向代理。详见 `docs/production-runbook.md`。

## 10. 数据库变更

所有 schema 修改必须生成 Alembic migration。

示例：

```bash
alembic revision --autogenerate -m "add xxx"
alembic upgrade head
```

提交 migration 前：
- 检查 upgrade
- 检查 downgrade
- 在空库验证
- 在已有测试数据的库验证

## 11. OpenAPI 变更

API 修改流程：

1. 更新 Backend schema/router/service，运行时 OpenAPI 是接口事实来源。
2. 执行 `cd backend && python scripts/sync_openapi.py`，同步两份静态 OpenAPI。
3. 执行 `cd frontend && npm run generate:api-types`，生成 TypeScript DTO。
4. 增加/更新测试，并执行 OpenAPI parity、`npm run check:api-types` 和构建门禁。

核心契约变化需要用户确认。

## 12. revision 并发开发规范

核心更新请求必须传 revision。

正确示例：

```sql
UPDATE rd_requirement
SET title = :title,
    revision = revision + 1,
    updated_at = NOW(),
    updated_by = :user_id
WHERE id = :id
  AND revision = :revision;
```

影响行数为 0：
- 查询当前对象
- 返回 409
- 前端显示冲突界面
- 不自动重试覆盖

反馈转需求、需求迁版和版本发布等跨表事务也必须先执行带 revision 条件的原子更新；禁止用“先读取 revision、再普通 ORM 赋值”替代条件更新。

## 12.1 状态终态规则

- `Version.RELEASED` 只能由 `POST /versions/{id}/publish` 成功发布事务产生。
- 普通 Version 状态接口禁止设置 `RELEASED`；`READY -> TESTING` 必须填写原因并审计。
- `Requirement.ONLINE` 只能由成功发布事务产生。
- `DONE -> DEVELOPING` 仅限所属 Version 尚未发布，必须填写原因并审计。
- V1.5 MVP 的 publish 不接收 result 参数，成功后固定写入 `Release.result = SUCCESS`。

## 13. Redis 编辑提示

建议键：

```text
edit_lock:requirement:{id}
```

值至少：
- user_id
- user_name
- started_at
- heartbeat_at

TTL 默认 600 秒。

仅用于协作提示，不影响业务写入权限。

## 14. 日志

每个请求应带 request_id。

业务审计和运行日志分离：
- 运行日志：应用运行、异常、性能
- 审计日志：用户业务操作前后值

禁止日志记录密码、Token、Secret。

## 15. Git/提交建议

每个阶段小步提交，例如：

```text
feat(auth): implement login and refresh token
feat(feedback): add feedback create/list/detail
feat(requirement): add optimistic locking
feat(version): add requirement assignment
feat(release): implement release transaction
fix(concurrency): return latest revision on conflict
```

不要把全部模块一次塞进一个不可审查提交。

## 16. Agent 阶段报告格式

每个 Task 阶段结束回复：

```text
阶段：
完成：
修改文件：
数据库 migration：
API 变化：
测试：
已验证场景：
未解决：
需要确认：
下一步：
```

若测试未通过，明确写“未完成”，不得标记 Done。
