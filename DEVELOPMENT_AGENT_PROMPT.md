# IterFlow 开发 Agent 接手入口

当前正式发布目标为 `v1.8.0`，用户已授权 Final Release；正式发布成立条件为 Final Master CI PASS + annotated v1.8.0 tag + 正式 GitHub Release；发布事实以三者和最终 master commit 为准，不提前记录 tag object SHA。发布 base 为 `d9e107f83a97229ab879987c1abe1c351afcad3b`，包/runtime版本同步1.8.0，当前契约 `spec/openapi-v1.8.yaml`。C0/C1/C3/C4实现与内外部审查PASS，其他候选DEFER；Preview 79fa39d3611c166c992d5cbdf8d6c3757506ee46保持不变。验收见 `docs/v1.8-release-readiness.md`，范围与执行见Plan/log/TASKS；本轮不开发新功能，不部署。下文V1.7段落为历史开发与发布授权，不自动沿用。

历史正式发布版本为v1.7.0，发布事实以最终master commit、annotated tag与GitHub Release为准。V1.7开发基线为`f0aa8475ff081fc963cdd08045d23e383a3c594e`；Phase 0–4开发期间版本为1.6.0，本次正式发布元数据同步为1.7.0。V1.6文档和标签保留为不可变历史发布证据。

## 阅读顺序

1. AGENTS.md 与 START_HERE.md
2. docs/v1.8-baseline-audit.md、docs/v1.8-plan.md、docs/v1.8-release-readiness.md（V1.7文档保留历史）
3. TASKS.md、DEVELOPMENT.md、docs/v1.8-autonomous-execution-log.md
4. spec/status-machines.md 与当前spec/openapi-v1.8.yaml（V1.7/V1.6/V1.5契约冻结）
5. 代码、测试和当前 Git/CI 事实

## V1.7 历史授权范围

仅五个正式阶段：Phase 0 Scope Freeze；Phase 1 C1/C3/C8/C9 evidence-first；Phase 2 C2 Release 右开日期查询；Phase 3 C6 focus/visibility 刷新（30s cooldown，无 polling）；Phase 4 Regression & Release Readiness。C4 删除、C5 TEAM、C7 trusted IP 延期。

用户已授权逐阶段自主推进；每阶段使用独立分支，Implementation Pass → 本地门禁 → Fresh Self-Review → branch 六项 CI → 核验 master 基线 → no-ff merge/parents 验证 → docs-only closeout → final master 六项 CI。全通过才继续，不伪称外部独立终审。Fresh Review 重新读取完整 diff、源码、契约、权限、DataScope、测试与 CI，最多三轮 Fix Loop，不降低门禁。

主链 Feedback → Requirement → Version → Publish → Release、集中状态机、原子 Publish、record-only Release、revision CAS、RBAC/DataScope、Hash Router 继续冻结。迁移、新权限/核心实体、TEAM、状态机/Publish 变化、超范围安全问题或 master 外部漂移立即停止。明确外部基础设施错误允许同 HEAD 只重跑失败 job 一次，保留首次失败证据，再失败停止。

Phase 0–4已完成RELEASE READY，外部独立终审PASS。本次已授权v1.7.0 Final Release：只同步版本/当前发布文档，完整门禁后no-ff merge、annotated tag和正式GitHub Release；完成后停止。部署、Preview升级与生产破坏性操作不在本次授权。
