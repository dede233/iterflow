# IterFlow V1.6 开发 Agent 入口

产品：**迭程 IterFlow · 需求与版本协作管理系统**。已发布稳定版为不可变的 `v1.5.0`；当前 V1.6 开发 master 为 `f43f76145961b54d279cf3c85dd4afeb3e0e2d3f`。V1.6 的定位是协作体验与信息可见性增强，核心领域规则继续冻结。

## 进入开发前的阅读顺序

1. `AGENTS.md`
2. `START_HERE.md`
3. `docs/v1.6-baseline-audit.md`
4. `docs/v1.6-plan.md`
5. `TASKS.md`
6. `DEVELOPMENT.md`
7. `spec/status-machines.md`
8. 当前 V1.6 开发契约：Phase 0 读取工作树中的 `spec/openapi-v1.5.yaml`；首次 V1.6 API 修改时创建并改用 `spec/openapi-v1.6.yaml`。正式 V1.5 历史契约以 `v1.5.0` 标签为准。
9. 当前代码和测试

不要重新执行 V1.5 Phase 0，也不要把旧 `TASKS.md` 的 checkbox 当作实现事实。以当前代码、接口、测试和 CI 为准。当前 master 已有 UI Redesign、System Catalog、System Permission closeout、Responsive 适配和 Playwright stability 修复；不要重新实现这些基线能力。

## 阶段执行规则

只执行用户当前明确授权的 V1.6 Phase。若没有明确授权，先阅读当前 `TASKS.md` 和最近阶段报告，核对现状，不自行跨 Phase 或自动开始 Phase 1。

每个 Phase 使用独立分支，按“实现 → 运行 → 测试 → 修复 → 阶段报告 → 独立终审”的顺序推进；终审后再决定是否合并。禁止自动 merge master。报告应列出修改文件、接口与 migration 变化、测试结果、未解决问题和下一步建议。

继续遵守 `AGENTS.md`：Feedback → Requirement → Version → Publish → Release 主链、集中状态机、Publish 事务、Release 记录语义、revision CAS、RBAC/DataScope 和 Hash Router 均不得因阶段计划擅自改变。新增 API 先确定契约，再同步实现、类型与 parity 测试。
