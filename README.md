# 需求与版本管理系统 V1.5 - 完整开发基线

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
MinIO 服务：iterflow-minio
```

对外页面与文档优先显示“迭程 IterFlow”；代码、仓库、容器和服务名统一使用小写英文 `iterflow` 前缀。

如后续需要调整品牌视觉，可修改 Logo、登录页标题和文案，但不要因此改变核心业务模型或接口契约。

## 本版目标

- Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic
- PostgreSQL + Redis + MinIO/S3
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

## 启动顺序

1. `cp .env.example .env` 并修改密码/密钥。
2. `docker compose -f deploy/docker-compose.yml up -d db redis minio`
3. 在 backend 安装依赖并执行 `alembic upgrade head`
4. 启动 FastAPI：`uvicorn app.main:app --reload --port 8000`
5. 启动前端：`npm install && npm run dev`

> V1.5 是工程基线，不包含工时、Story Point 或单需求预计时长功能。

## 初始化管理员与权限

执行 migration 后：`python -m app.cli.seed`。生产环境务必通过 `INIT_ADMIN_PASSWORD` 指定随机初始密码，首次登录强制改密。

## 开发 Agent 开工入口

如果由开发 Agent 接手，请先阅读：

1. `START_HERE.md`
2. `AGENTS.md`
3. `TASKS.md`
4. `DEVELOPMENT.md`

V1.5 为当前唯一有效开发基线；V1.0–V1.4 仅为历史方案。
