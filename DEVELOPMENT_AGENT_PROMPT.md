# IterFlow V1.7 开发 Agent 入口

正式稳定版为 v1.6.0，V1.7 基线为 `f0aa8475ff081fc963cdd08045d23e383a3c594e`。开发期间 backend/frontend 包与运行时版本保持 1.6.0。V1.6 文档和标签保留为历史发布证据。

## 阅读顺序

1. AGENTS.md 与 START_HERE.md
2. docs/v1.7-baseline-audit.md、docs/v1.7-plan.md
3. TASKS.md、DEVELOPMENT.md、docs/v1.7-autonomous-execution-log.md
4. spec/status-machines.md 与当前契约（Phase 0 为 V1.6；Phase 1 建立并切换 V1.7）
5. 代码、测试和当前 Git/CI 事实

## 授权范围

仅五个正式阶段：Phase 0 Scope Freeze；Phase 1 C1/C3/C8/C9 evidence-first；Phase 2 C2 Release 右开日期查询；Phase 3 C6 focus/visibility 刷新（30s cooldown，无 polling）；Phase 4 Regression & Release Readiness。C4 删除、C5 TEAM、C7 trusted IP 延期。

用户已授权逐阶段自主推进；每阶段使用独立分支，Implementation Pass → 本地门禁 → Fresh Self-Review → branch 六项 CI → 核验 master 基线 → no-ff merge/parents 验证 → docs-only closeout → final master 六项 CI。全通过才继续，不伪称外部独立终审。Fresh Review 重新读取完整 diff、源码、契约、权限、DataScope、测试与 CI，最多三轮 Fix Loop，不降低门禁。

主链 Feedback → Requirement → Version → Publish → Release、集中状态机、原子 Publish、record-only Release、revision CAS、RBAC/DataScope、Hash Router 继续冻结。迁移、新权限/核心实体、TEAM、状态机/Publish 变化、超范围安全问题或 master 外部漂移立即停止。明确外部基础设施错误允许同 HEAD 只重跑失败 job 一次，保留首次失败证据，再失败停止。

最终停止在 RELEASE READY，等待用户回来发布；禁止修改版本至1.7.0、tag/GitHub Release、部署、Preview升级或生产破坏性操作。
