# IterFlow V1.6 Development Tasks

> 当前开发基线：master `f43f76145961b54d279cf3c85dd4afeb3e0e2d3f`。已发布稳定版 `v1.5.0` 不变。事实盘点见 `docs/v1.6-baseline-audit.md`，产品边界与验收见 `docs/v1.6-plan.md`。本清单只记录 V1.6 增量，不能替代代码与 CI 证据。

## V1.6 Baseline — Already Completed

- 核心链 Feedback → Requirement → Version → Publish → Release、revision CAS、后端 RBAC/DataScope、审计、文件存储与 Docker 部署基线。
- 完整 UI Redesign、八个现有设计组件、桌面侧栏、移动底部导航、375/390/768/1280/1440 响应式验收。
- 正式 Hash Router `createWebHashHistory(import.meta.env.BASE_URL)` 与 `/#/...` 路由。
- System/Module 管理、`sys.system.view/manage` 权限语义、CAS、审计中文展示。
- Feedback/Requirement Detail Grid 对齐修复：双列详情页的侧栏卡片与主卡片顶部对齐。
- Editing 后端 start/heartbeat/end 与 Redis presence 基础；需求详情已有**部分**前端调用，完整会话语义仍是 Phase 1。
- Playwright Audit DatePicker flake 修复；master 六项 CI（backend/frontend/docker_smoke/s3/browser_smoke/backup_restore）通过。

## Phase 0 — Baseline & Docs（当前，只有文档）

- [x] 核对 master、`v1.5.0`、后续提交及工作区基线。
- [x] 按代码、测试、接口、CI 盘点现有能力和缺口，记录规划稿与代码差异。
- [x] 冻结核心领域、状态机、Hash Router、V1.6 产品范围与非范围。
- [x] 新增 `docs/v1.6-baseline-audit.md`、`docs/v1.6-plan.md` 并校准入口文档。
- [ ] 独立终审通过后，由单独授权决定是否合并规划分支；本阶段不合并。

## Phase 1 — Editing Presence（P0）

- [ ] 梳理 Feedback/Requirement/Version 的实际编辑入口与退出边界；修正需求详情当前“仅打开详情就 start”的行为。
- [ ] 编辑开始时 start，编辑期间 heartbeat，关闭 Dialog/离页时 end；展示已有编辑者的姓名与提示。
- [ ] 验证双用户、刷新/网络失败、TTL 到期、无权限与 DataScope；Presence 不阻断写入。

## Phase 2 — Revision Conflict UX（P0）

- [ ] 逐个写接口核对 409 的 `current_revision`、更新时间/更新人及可安全展示的最新摘要；契约先行。
- [ ] 冲突界面展示服务器版本，提供重新加载与关闭后人工处理；必要时保留本地输入供复制。
- [ ] 验证双用户旧 revision 返回 409；不自动重试覆盖，不提供强制覆盖。

## Phase 3 — Notification V2（P1）

- [ ] 先确定 OpenAPI，再实现当前用户的未读计数与全部已读接口，并测试所有权隔离。
- [ ] 桌面导航、移动底部导航添加 badge，通知中心显示总数与全部已读。
- [ ] 保留先 mark read 后 navigation，处理历史通知与权限拦截。

## Phase 4 — Release Detail（P1）

- [ ] 实现只读 `/releases/:id`，以 `rd.release.view` 及现有数据范围校验为门禁，显示发布元数据与备注。
- [ ] 只有 `rd.version.view` 时提供版本链接；有 Release ID 的通知进入详情，无 ID 的进入列表。
- [ ] 不增加 Release 编辑、删除或状态迁移。

## Phase 5 — List Productivity（P1）

- [ ] Requirement 按编号/标题、status、priority、source、current_version_id、owner_id 筛选。
- [ ] Version 按版本号/名称、status、计划发布日期范围、owner_id 筛选。
- [ ] Release 前端先接入已有 `version_id` 筛选；评估日期范围成本。
- [ ] 新查询后端强制 DataScope；桌面筛选栏与移动筛选抽屉均覆盖测试。

## Phase 6 — Dashboard Activity（P2，可延期）

- [ ] 评估复用 OperationLog/Audit 的权限与对象级 DataScope，明确可见性证明。
- [ ] 若可安全实现，最多呈现 10–20 条相关活动；否则延期且不得绕过权限。

## Phase 7 — Regression & Release Readiness

- [ ] 回归完整主链、事务与状态机、revision 冲突、权限/数据范围及通知隔离。
- [ ] 通过后端全量与 PostgreSQL-only、Ruff/format/Mypy/compileall、Alembic check、OpenAPI parity。
- [ ] 通过前端 Vitest/API 类型/build/bundle、现有 Hash Router Playwright 与五视口验收。
- [ ] 通过六项 CI，检查首次运行结果及 flake；独立终审后再规划 1.6.0 版本号与发布标签。

## 冻结的非范围

TEAM DataScope、工时/Story Point/预计时长/报表、Release 回滚工作流与状态机、新核心实体、WebSocket 平台、微服务、独立移动 App、Feedback 直接加入 Version、AI 决定业务状态。任何阶段均不得改变当前核心链或发布事务。
