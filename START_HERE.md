# START_HERE.md

# 开发 Agent 从这里开始

这是“需求与版本管理系统”V1.5 的实际开发开工包。


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
对象存储：本地默认 LocalFileStorage，生产可配置 S3Storage
```

对外页面与文档优先显示“迭程 IterFlow”；代码、仓库、容器和服务名统一使用小写英文 `iterflow` 前缀。

如后续需要调整品牌视觉，可修改 Logo、登录页标题和文案，但不要因此改变核心业务模型或接口契约。

## 第一次进入仓库必须按此顺序阅读

1. `AGENTS.md`
2. `TASKS.md`
3. `DEVELOPMENT.md`
4. `docs/需求与版本管理系统_独立部署版_V1.5_完整开发基线.pdf`
5. `spec/openapi-v1.5.yaml`
6. `spec/status-machines.md`
7. 现有代码

## 第一条指令

不要立即重构或大面积写代码。

先完成 `TASKS.md` 的 **Phase 0 — 工程体检与启动基线**，然后汇报：

1. 当前工程能否启动
2. 缺失实现
3. 占位实现
4. 发现的 Bug
5. 规格冲突
6. 数据库 migration 情况
7. 前端 build 情况
8. Docker 情况
9. 计划修改/新增文件
10. Phase 1 的具体实施顺序

确认后再进入实际功能开发。

## 唯一核心链路

`Feedback -> Requirement -> Version -> Release`

## 三条绝对规则

- 不允许静默覆盖多人编辑：必须 revision + 409。
- Version 只关联 Requirement，不直接关联 Feedback 作为版本项。
- 不开发工时、Story Point、单需求预计开发时长。

## 可直接复制给开发 Agent

完整首轮指令已放在 `DEVELOPMENT_AGENT_PROMPT.md`。
