# 迭程 IterFlow · 需求与版本协作管理系统

已发布稳定版本是不可变的 `v1.5.0`（`a7e60e39893f162dd49b03d40f5ca975abd5d42d`）。当前 master `f43f76145961b54d279cf3c85dd4afeb3e0e2d3f` 是 Post-V1.5 / V1.6 开发基线，不是新的正式发布版。V1.6 现阶段仅冻结规划，见 [基线审计](docs/v1.6-baseline-audit.md)、[V1.6 计划](docs/v1.6-plan.md) 和 [执行清单](TASKS.md)。

独立部署的研发协作系统，主链路为：

`Feedback -> Requirement -> Version -> Release`


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

## 本版目标

- Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic
- PostgreSQL + Redis + S3 Compatible Object Storage
- JWT Access/Refresh Token + RBAC
- Feedback / Requirement / Version / Release / Notification / System 配置
- `revision` 乐观锁 + Redis 编辑提示，避免多人编辑静默覆盖
- Vue 3 + TypeScript + Element Plus，PC/平板/手机响应式
- Docker Compose 本地/一期部署基线

## 目录

- `backend/`: API、领域服务、数据模型、迁移、测试
- `frontend/`: Vue 3 Web 端，PC + Mobile 自适应
- `deploy/`: Docker Compose 与 Nginx 入口
- `spec/`: OpenAPI、状态机与接口说明

## 生产 Compose 一键启动

1. `cp .env.example deploy/.env`，填写数据库密码、JWT 密钥、允许的 Host 与首次管理员密码。
2. 在可信的 HTTPS 反向代理后运行 `docker compose -f deploy/docker-compose.yml up -d --build`。
3. Compose 自动等待数据库、执行 migration 与 seed，再启动 API 和 Web。无需手工进入容器初始化。

Web 默认仅绑定 `127.0.0.1:8080`。**不得将纯 HTTP 端口直接暴露公网**；TLS 由前置代理或负载均衡器提供。完整部署、备份与回滚见 [生产运维手册](docs/production-runbook.md)。

本地非容器开发仍可按 [DEVELOPMENT.md](DEVELOPMENT.md) 分别启动后端与前端。

> V1.5 是已发布的历史稳定基线。V1.6 继续不包含工时、Story Point 或单需求预计时长功能。

本地开发默认设置 `STORAGE_DRIVER=local`，文件保存在 `LOCAL_STORAGE_PATH=./data/uploads`。需要接入 SeaweedFS、RustFS、AWS S3 或其他 S3 Compatible Object Storage 时改用 `STORAGE_DRIVER=s3`。

健康端点：`/health` 只用于 liveness；`/ready` 实际检查 PostgreSQL、Redis 与当前配置的 Storage Driver。

## 初始化管理员与权限

首次启动需通过 `INIT_ADMIN_PASSWORD` 指定 8–128 位随机密码（建议 20 位以上），首次登录强制改密。管理员已存在后可从环境中移除该密码；重复 seed 不会重置现有密码。

## 开发 Agent 开工入口

如果由开发 Agent 接手，请先阅读：

1. `AGENTS.md`
2. `START_HERE.md`
3. `docs/v1.6-baseline-audit.md` 与 `docs/v1.6-plan.md`
4. `TASKS.md` 与 `DEVELOPMENT.md`

V1.5 主文档和标签是正式版本的历史依据；V1.0–V1.4 仅为更早历史方案。当前开发任务按 V1.6 规划推进，核心业务规则仍受 `AGENTS.md` 和 V1.5 规格约束。
