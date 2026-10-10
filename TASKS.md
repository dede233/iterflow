# IterFlow Tasks

## 当前开发文档

2026-10-10 本地协作开发快照的文档入口：[用户操作手册](docs/user-manual.md)、[接口集成指南](docs/api-guide.md)、[全员开发确认与验收](docs/development-completion.md)。当前契约为 `spec/openapi-development.yaml`；按阶段分工、可选设计、需求完成与发布全员确认门禁属于未发布增量，不因文档同步而表示已部署线上。已发布历史契约和下述发布证据保持不变。

当前追加[全员开发完成发布门禁](docs/development-completion.md)，该文档包含操作与验收；前述阶段记录保留为历史证据。

## 2026-10-10 需求开发、设计协作（本地）

后续用户确认设计可按需跳过，追加 DESIGNING 与阶段分配；当前增量见 `docs/requirement-design-stage.md`，线上未升级。

用户确认保留一名总负责人，可绑定多名开发、多名设计；本轮仅本地实现与验收，范围见 `docs/requirement-collaboration.md`。以下增量不改变历史发布范围记录。

- [x] 开发契约、分工关联、两类基础角色及双数据库追加迁移。
- [x] revision CAS、SELF/RBAC、事务审计和定向站内通知。
- [x] 需求详情分配界面与 PC/Tablet/Mobile 验收。
- [x] 真实 MySQL 5.7、PostgreSQL 回归、迁移和独立备份恢复。
- [x] Fresh Self-Review 与操作说明。
- [ ] Branch CI、外部审查、新部署包及线上升级（未执行）。

> 本次正式发布目标为 `v1.8.1`，Hotfix 外部独立终审 PASS，用户已授权 Final Release + Cloudflare Preview Resume。正式发布成立条件为新的 Release Branch / Final Master 六项 CI PASS、annotated v1.8.1 tag 与正式 GitHub Release；发布事实以最终 master commit、标签和 Release 为准，不提前记录 tag SHA。发布 base：`df9e1ba1a5ee1a4c763098d8e180250f409bedd3`；包、FastAPI、health、Frontend 与当前契约元数据同步 1.8.1，当前契约 `spec/openapi-v1.8.1.yaml`，API shape 不变。v1.8.0 及更早正式标签/Release/契约不可变；本轮只发布已审查的共享 PageHeader 平板响应式修复，随后将正式版本合入独立 Preview 并恢复验收，不部署 Production。证据见 `docs/v1.8.1-release-readiness.md`。

## V1.8 — Version Workspace & Main-Chain Productivity

- [x] Phase 0：正式V1.7基线审计与产品范围冻结；原始分析保留。
- [x] Phase 0：Scope branch六项CI、no-ff merge与final master六项CI。
- [x] Phase 1 — Query Context & Main-Chain Traceability：C4白名单query/安全return_to与C3授权lookup/关系导航。
- [x] Phase 2 — Scoped Relationship Selection：C1分页/搜索/竞态/权限降级/提交前revision。
- [x] Phase 3 — Version Worklist Productivity：C0可见清单筛选、优先级、统计与安全阻塞导航。
- [x] Phase 4 — Regression & Release Readiness：本地门禁、Fresh Self-Review、product branch/master CI与docs-only收口/final CI。

以下为 V1.8.0 阶段收口的历史事实。C2、C5–C16本版DEFER；scroll持久化/全局缓存不做。无新permission/migration/entity、TEAM、状态机或Publish变化。开发阶段版本曾保持1.7.0；本次发布授权同步1.8.0，并仅在final master CI后创建annotated tag/Release；不更新Preview或生产。正式开发 base：`cf9a2fbcd4f045c8dfbc34030b1a3449faa19e8f`。验收见 `docs/v1.8-release-readiness.md`，执行证据见 `docs/v1.8-autonomous-execution-log.md`；同一Agent复查不称外部独立终审。

## V1.7 历史开发清单

以下保留 V1.7 开发、发布准备时的基线与授权记录；其中 Preview SHA 是当时冻结值，不代表当前部署线。V1.7 已正式发布，历史授权不自动延续到 V1.8。

> 正式发布基线：v1.6.0 / `f0aa8475ff081fc963cdd08045d23e383a3c594e`。V1.7 已获用户自主开发授权；正式范围见 `docs/v1.7-plan.md`，事实与执行证据见 baseline audit / autonomous execution log。Phase 0–4开发版本为1.6.0；外部独立终审PASS，现已授权v1.7.0 Final Release并同步包/运行时元数据。Preview保持`33d36d78ab4bedf48835d124f295f1ca8c352eae`，不参与本次发布。V1.6 清单以其正式标签快照为历史依据。

## Phase 0 — Baseline Audit & Scope Freeze

- [x] 核对发布 Git/CI 事实，完成代码/契约/测试审计。
- [x] 冻结 C0/C1/C2/C3/C6/C8/C9；C4删除/C5/C7延期；日期右开、通知focus/visibility方案确定。
- [x] 主链补齐Publish、修正DUPLICATE文字、切换入口文档与清单，保留V1.6历史证据。
- [x] Fresh Self-Review与branch CI通过，no-ff merge/parents核验及docs closeout完成。
- [x] Final master CI通过（37002731061，attempt1六项success，实际HEAD见执行日志）。

## Phase 1 — Product Consistency & Correctness

- [x] C1 package.json → Vite define → UI，开发版本仍1.6.0。
- [x] C3 Feedback literal substring/case-insensitive/trim；建立V1.7契约并切换types/parity，冻结V1.6。
- [x] C8 refresh失败Hash安全回跳，不改变Router mode。
- [x] C9先写Feedback list/Audit list/detail deterministic race tests，仅修已复现页面。
- [x] 本地门禁、Fresh Self-Review、branch六项CI与合并/文档收口完成。
- [x] Final master六项CI（37005356072，attempt1六项success）。

## Phase 2 — Release Query Productivity

- [x] C2 offset-aware `released_from <= released_at < released_before`，允许单边，反向/空区间422。
- [x] version_id/rd.release.view/Version DataScope继续AND，契约、types、分页total一致。
- [x] 本地日期整天→下一日00:00 exclusive，五视口DatePicker/Popper回归。
- [x] 本地门禁、Fresh Self-Review（Fix Loop 1）、branch六项CI与合并/文档收口。
- [x] Final master六项CI（37007834004，attempt1六项success）。

## Phase 3 — Notification Freshness

- [x] focus + hidden→visible刷新未读数；30秒cooldown，无polling。
- [x] logout/account switch/旧响应/focus storm/read-all race回归。
- [x] 本地门禁、Fresh Self-Review（Fix Loop 1）、branch六项CI与合并/文档收口。
- [x] Final master六项CI（37010208267，attempt1六项success）。

## Phase 4 — Regression & Release Readiness

- [x] 完整主链、Publish原子回滚、CAS/40910、RBAC/SELF/ALL、附件、通知、Presence/Conflict/Release/Dashboard与批准候选回归。
- [x] Backend full/PG-only/Ruff/format/Mypy/compileall/Alembic/parity/dev-prod audit/production lock。
- [x] Frontend Vitest/types/build/bundle/npm audits/Playwright与375/390/768/1280/1440。
- [x] 验收文档、Fresh Self-Review、branch六项CI、合并与docs closeout。
- [x] Final master六项CI（37011793000，attempt1六项success），FINAL CLOSED / RELEASE READY。

## 冻结非范围

TEAM、废弃权限删除、trusted IP实现、新migration/permission/entity、状态机/Publish改造、Release回滚、工时/Story Point、独立Mobile、WebSocket/SSE/broker、额外Release搜索、正式发布或Preview部署。
