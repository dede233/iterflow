# START_HERE.md

# 开发 Agent 从这里开始

这是迭程 IterFlow 当前 V1.7 入口。本次正式发布版本为`v1.7.0`，发布事实以最终master commit、annotated tag与GitHub Release为准；V1.7从正式v1.6.0解引用基线`f0aa8475ff081fc963cdd08045d23e383a3c594e`开始。`v1.5.0`与`v1.6.0`均不可变；正式发布包与运行时版本为1.7.0。当前范围/阶段见 `docs/v1.7-plan.md`、`TASKS.md`，自主执行证据见 `docs/v1.7-autonomous-execution-log.md`。


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
3. `docs/v1.7-baseline-audit.md`
4. `docs/v1.7-plan.md`
5. `TASKS.md` 与 `DEVELOPMENT.md`
6. `docs/需求与版本管理系统_独立部署版_V1.5_完整开发基线.pdf`
7. `spec/status-machines.md` 与当前 `spec/openapi-v1.7.yaml`；V1.6/V1.5契约冻结，历史发布快照以对应标签为准
8. 现有代码和测试

## 第一条指令

先核对 Git 冻结事实、基线审计和已批准范围。用户已授权 V1.7 Phase 0–4 自主实施、Fresh Self-Review、六项 CI、no-ff merge 与 docs closeout；每阶段 final master CI 通过后才进入下一阶段。硬停止条件见 AGENTS 第16节。Phase 0–4已完成，外部独立终审PASS，用户已授权v1.7.0 Final Release；完成后停止，Preview升级另行授权。

## 唯一核心链路

`Feedback -> Requirement -> Version -> Publish -> Release`

## 三条绝对规则

- 不允许静默覆盖多人编辑：必须 revision + 409。
- Version 只关联 Requirement，不直接关联 Feedback 作为版本项。
- 不开发工时、Story Point、单需求预计开发时长。

## 可直接复制给开发 Agent

`DEVELOPMENT_AGENT_PROMPT.md` 是当前 V1.7 开发 Agent 入口；具体阶段范围与验收以 `docs/v1.7-plan.md` 和 `TASKS.md` 为准。
