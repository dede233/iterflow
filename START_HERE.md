# START_HERE.md

# 开发 Agent 从这里开始

这是迭程 IterFlow 当前接手入口。正式发布版本为 `v1.7.0`，解引用到 `e485efea0155c5b4194f563926a531d606c77349`；包与运行时版本为 1.7.0。`v1.5.0`、`v1.6.0`、`v1.7.0` 均不可变。当前任务仅为 V1.8 文档审计与候选规划，见 `docs/v1.8-baseline-audit.md`、`docs/v1.8-plan.md` 和 `TASKS.md`；所有候选待产品决策，尚未授权功能开发。V1.7 计划与自主执行日志保留为历史证据。


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
7. `spec/status-machines.md` 与当前 `spec/openapi-v1.7.yaml`；V1.6/V1.5契约冻结，历史发布快照以对应标签为准
8. 现有代码和测试

## 第一条指令

先核对 Git 冻结事实与实际代码。V1.7 已正式发布；V1.8 从 `e485efea0155c5b4194f563926a531d606c77349` 开始，本轮仅允许 docs-only 基线审计和需求规划。候选全部为 `PENDING PRODUCT DECISION`，Phase 1 未启动；不得把历史 V1.7 自主实施授权沿用为 V1.8 开发授权。Preview 是独立部署线，不作为产品开发基线。

## 唯一核心链路

`Feedback -> Requirement -> Version -> Publish -> Release`

## 三条绝对规则

- 不允许静默覆盖多人编辑：必须 revision + 409。
- Version 只关联 Requirement，不直接关联 Feedback 作为版本项。
- 不开发工时、Story Point、单需求预计开发时长。

## 可直接复制给开发 Agent

`DEVELOPMENT_AGENT_PROMPT.md` 是当前接手入口；V1.8 只做规划，具体候选见 `docs/v1.8-plan.md`。V1.7 阶段范围与验收记录保留为历史依据。
