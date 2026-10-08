# START_HERE.md

# 开发 Agent 从这里开始

本次正式发布目标为 `v1.8.1`，Hotfix 外部独立终审 PASS，用户已授权 Final Release + Cloudflare Preview Resume。正式发布成立条件为新的 Release Branch / Final Master 六项 CI PASS、annotated v1.8.1 tag 与正式 GitHub Release；发布事实以最终 master commit、标签和 Release 为准，不提前记录 tag SHA。发布 base：`df9e1ba1a5ee1a4c763098d8e180250f409bedd3`；包、FastAPI、health、Frontend 与当前契约元数据同步 1.8.1，当前契约 `spec/openapi-v1.8.1.yaml`，API shape 不变。v1.8.0 及更早正式标签/Release/契约不可变；本轮只发布已审查的共享 PageHeader 平板响应式修复，随后将正式版本合入独立 Preview 并恢复验收，不部署 Production。证据见 `docs/v1.8.1-release-readiness.md`。


## 项目命名

本项目正式产品名确定为：

- **中文名：迭程**
- **英文名：IterFlow**
- **完整名称：迭程 IterFlow · 需求与版本协作管理系统**
- **核心含义：迭代 + 流程，覆盖 Feedback → Requirement → Version → Publish → Release 的完整协作链路。**

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
2. `README.md`
3. `docs/v1.8-baseline-audit.md` 与 `docs/v1.8-plan.md`
4. `docs/v1.7-baseline-audit.md`、`docs/v1.7-plan.md` 与 V1.7 发布证据（历史）
5. `TASKS.md` 与 `DEVELOPMENT.md`
6. `docs/需求与版本管理系统_独立部署版_V1.5_完整开发基线.pdf`
7. `spec/status-machines.md` 与当前 `spec/openapi-v1.8.1.yaml`；V1.8/V1.7/V1.6/V1.5契约冻结，历史发布快照以对应标签为准
8. 现有代码和测试

## 第一条指令

以下为 V1.8.0 开发与发布授权的历史记录，不代表本轮 V1.8.1 / Preview 授权边界。V1.7 已正式发布；V1.8 从 `e485efea0155c5b4194f563926a531d606c77349` 开始，C0/C1/C3/C4 已完成自主实施、复查与产品主线门禁；开发最终 master CI 37095500766 / attempt1 六项通过，外部独立终审 PASS；本轮 Final Release 只同步元数据/契约快照，其他候选DEFER，Preview/部署另行授权；不得把历史 V1.7 自主实施授权沿用为 V1.8 开发授权。Preview 是独立部署线，不作为产品开发基线。

## 唯一核心链路

`Feedback -> Requirement -> Version -> Publish -> Release`

## 三条绝对规则

- 不允许静默覆盖多人编辑：必须 revision + 409。
- Version 只关联 Requirement，不直接关联 Feedback 作为版本项。
- 不开发工时、Story Point、单需求预计开发时长。

## 可直接复制给开发 Agent

`DEVELOPMENT_AGENT_PROMPT.md` 是当前接手入口；V1.8 已完成已批准C0/C1/C3/C4，已获得 Final Release 授权，Preview/部署另行授权；禁止自动实施延期项，具体候选见 `docs/v1.8-plan.md`。V1.7 阶段范围与验收记录保留为历史依据。

## 当前开发增量（2026-10-08）

用户已授权受保护的接口文档入口，访问规则和部署验收见 `docs/api-documentation-access.md`。当前开发契约为 `spec/openapi-development.yaml`，已发布的 V1.8.1 及更早契约 / tag 保持不变。
