# IterFlow 开发 Agent 接手入口

本次正式发布目标为 `v1.8.1`，Hotfix 外部独立终审 PASS，用户已授权 Final Release + Cloudflare Preview Resume。正式发布成立条件为新的 Release Branch / Final Master 六项 CI PASS、annotated v1.8.1 tag 与正式 GitHub Release；发布事实以最终 master commit、标签和 Release 为准，不提前记录 tag SHA。发布 base：`df9e1ba1a5ee1a4c763098d8e180250f409bedd3`；包、FastAPI、health、Frontend 与当前契约元数据同步 1.8.1，当前契约 `spec/openapi-v1.8.1.yaml`，API shape 不变。v1.8.0 及更早正式标签/Release/契约不可变；本轮只发布已审查的共享 PageHeader 平板响应式修复，随后将正式版本合入独立 Preview 并恢复验收，不部署 Production。证据见 `docs/v1.8.1-release-readiness.md`。

历史正式发布版本为v1.7.0，发布事实以最终master commit、annotated tag与GitHub Release为准。V1.7开发基线为`f0aa8475ff081fc963cdd08045d23e383a3c594e`；Phase 0–4开发期间版本为1.6.0，本次正式发布元数据同步为1.7.0。V1.6文档和标签保留为不可变历史发布证据。

## 阅读顺序

1. AGENTS.md 与 START_HERE.md
2. docs/v1.8-baseline-audit.md、docs/v1.8-plan.md、docs/v1.8-release-readiness.md（V1.7文档保留历史）
3. TASKS.md、DEVELOPMENT.md、docs/v1.8-autonomous-execution-log.md
4. spec/status-machines.md 与当前spec/openapi-v1.8.1.yaml（V1.8/V1.7/V1.6/V1.5契约冻结）
5. 代码、测试和当前 Git/CI 事实

## V1.7 历史授权范围

仅五个正式阶段：Phase 0 Scope Freeze；Phase 1 C1/C3/C8/C9 evidence-first；Phase 2 C2 Release 右开日期查询；Phase 3 C6 focus/visibility 刷新（30s cooldown，无 polling）；Phase 4 Regression & Release Readiness。C4 删除、C5 TEAM、C7 trusted IP 延期。

用户已授权逐阶段自主推进；每阶段使用独立分支，Implementation Pass → 本地门禁 → Fresh Self-Review → branch 六项 CI → 核验 master 基线 → no-ff merge/parents 验证 → docs-only closeout → final master 六项 CI。全通过才继续，不伪称外部独立终审。Fresh Review 重新读取完整 diff、源码、契约、权限、DataScope、测试与 CI，最多三轮 Fix Loop，不降低门禁。

主链 Feedback → Requirement → Version → Publish → Release、集中状态机、原子 Publish、record-only Release、revision CAS、RBAC/DataScope、Hash Router 继续冻结。迁移、新权限/核心实体、TEAM、状态机/Publish 变化、超范围安全问题或 master 外部漂移立即停止。明确外部基础设施错误允许同 HEAD 只重跑失败 job 一次，保留首次失败证据，再失败停止。

Phase 0–4已完成RELEASE READY，外部独立终审PASS。本次已授权v1.7.0 Final Release：只同步版本/当前发布文档，完整门禁后no-ff merge、annotated tag和正式GitHub Release；完成后停止。部署、Preview升级与生产破坏性操作不在本次授权。
