# 给开发 Agent 的首轮指令

你现在接手“需求与版本管理系统”实际开发。

当前仓库已经提供 V1.5 产品、技术与工程基线。V1.5 是唯一有效开发基线，V1.0–V1.4 仅为历史方案。

请严格按以下顺序工作：

1. 阅读 `START_HERE.md`
2. 阅读 `AGENTS.md`
3. 阅读 `TASKS.md`
4. 阅读 `DEVELOPMENT.md`
5. 阅读 `docs/需求与版本管理系统_独立部署版_V1.5_完整开发基线.pdf`
6. 阅读 `spec/openapi-v1.5.yaml`
7. 阅读 `spec/status-machines.md`
8. 检查现有代码

不要立即重构，不要重新搭建另一套技术架构，不要一次性生成大量未经验证的代码。

首先只完成 `TASKS.md` 的 Phase 0。

首轮回复必须给出：

1. 当前工程结构检查结果
2. Backend 是否可安装/导入/启动
3. Frontend 是否可安装/构建
4. Docker Compose 是否可解析和启动基础设施
5. Alembic migration 当前情况
6. 发现的缺失实现
7. 发现的占位实现
8. 发现的 Bug
9. 文档 / OpenAPI / 代码之间的冲突
10. 计划修改或新增的文件清单
11. Phase 1 的实施顺序

在 Phase 0 报告完成之前，不进入大规模功能编码。


## 项目命名约束

正式项目名为 **迭程 IterFlow**，完整名称为 **迭程 IterFlow · 需求与版本协作管理系统**。

开发时统一使用：
- 仓库：`iterflow`
- 后端：`iterflow-api`
- 前端：`iterflow-web`
- 数据库：`iterflow`
- 基础设施前缀：`iterflow-`

现有代码若仍保留历史占位名称，可在不破坏功能的前提下逐步迁移；不要为了改名一次性做无关的大规模重构。


技术栈必须保持：

- Vue 3 + TypeScript + Vite + Element Plus
- Python 3.12+ + FastAPI + SQLAlchemy 2 + Alembic
- PostgreSQL
- Redis
- MinIO / S3
- Docker Compose

核心链路必须保持：

`Feedback -> Requirement -> Version -> Release`

多人编辑必须实现：

`revision 乐观锁 + Redis 编辑提示 + HTTP 409 + 审计日志`

禁止：
- Feedback 直接作为 Version 项
- 工时
- Story Point
- 单需求预计开发时长
- 静默覆盖多人编辑
- 只做前端按钮隐藏而不做后端权限
- 擅自替换主技术栈

每完成一个 Phase 必须：

`实现 -> 运行 -> 测试 -> 修复 -> 阶段报告 -> 再进入下一 Phase`

最终目标：

`docker compose up -d --build`

后能够实际完成：

`登录 -> 提交反馈 -> 反馈转需求 -> 需求加入版本 -> 状态流转 -> 发布版本 -> Requirement 上线 -> Feedback 上线 -> 站内通知 -> 审计可追踪`

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
