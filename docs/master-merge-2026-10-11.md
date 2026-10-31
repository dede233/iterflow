# MySQL 5.7 与需求协作主分支合并记录

2026-10-11，用户在确认合并范围与门禁后明确要求“那就开始合并吧”，授权解除本轮“不合并、不 push master”限制。此次仅推进 Git 主线和文档；线上保留已部署源 `2b37509aff342f8989ed21f61721d76c980141cb`，不再次部署、迁移、seed、恢复或重置账号，不创建新的 tag/Release。

## 分支和合并事实

- 主仓库：`/Users/xiaweiyi/Developer/work/iterflow`。
- 实现目录：`/Users/xiaweiyi/Developer/worktrees/iterflow/mysql-57-adaptation`。
- 源分支：`codex/requirement-collaboration`，已验收源 HEAD `68aee01d3a0e529942372ccef0ac5dfb88e64825`。
- 合并前 master：`a38081af9097f691c8289e9301951a0360ea0af7`。执行前再次核实本地、GitHub 和 Gitee 三者相同，没有外部漂移。
- no-ff 合并提交：`3b4ec651edc8c056e92deee4bf41bbd66f48f932`；第一父提交为上述 master，第二父提交为上述源 HEAD。
- 合并保留 29 个分支提交，合并树与已验收源 HEAD 完全相同，无冲突。随后仅进行当前文档入口和本记录的收口。

通过实现目录内的临时独立 Git worktree 执行，主仓库原检出分支 `codex/local-workspace-layout`、实现目录原分支及其他工作目录不切换、不覆盖。测试日志、数据库/附件、凭据及未提交的恢复证据不参与合并。临时 worktree 在最终核验后清理。

## 门禁与范围

[分支 CI 38070615711](https://github.com/dede233/iterflow/actions/runs/38070615711) 对源 HEAD 八项全部成功：backend、frontend、browser_smoke、docker_smoke、backup_restore、s3、mysql57 (standard)、mysql57 (portable)。[结构化结果](evidence/master-merge/branch-ci.json) 记录确切 SHA 和各 job 结果。

原文档提交 `3ca2247` 的 CI 38070572913 被新的验收取代并主动取消：合并前检查发现历史测试日志尾部多一个空行，追加文档提交 `68aee01` 去除该空行，未改日志中的测试结论、未改业务代码。最终验收完整运行新 HEAD 的八项 CI，不将已取消的 run 视为通过。

MySQL 5.7 独立迁移/约束、PostgreSQL 保留路径、按阶段人员分配、可选 DESIGNING、本人开发确认与 DONE/发布门禁、CAS/RBAC/DataScope/事务审计通知、兼容查询、CI/离线包工具、接口与操作文档一并纳入主线。业务代码与线上已验证 `2b37509` 一致；其后的源分支提交仅为文档和日志空行整理。

Fresh Self-Review 核实 no-ff 父提交、树一致性、历史正式契约与 PostgreSQL 0001–0004 迁移未改、无新 tag、未提交运行数据/凭据，以及合并后只有文档收口差异。该复查由同一 Agent 执行，不称为独立审查。

## 远端与最终 master 验收

交付门禁要求 GitHub `origin/master`、Gitee `gitee/master` 与本地 master 的最终 SHA 一致，最终 master 的八项 CI 全部成功；分支 CI 不能替代 master CI。最终文档收口 commit 及其实际 Checks 结果见 [master 提交历史](https://github.com/dede233/iterflow/commits/master/) 与 [master CI](https://github.com/dede233/iterflow/actions/workflows/ci.yml?query=branch%3Amaster)。验收完成时另保存本地最终结果，记录确切 master SHA、run URL 和镜像核验结果。

此前的 [线上升级记录](collaboration-online-upgrade-2026-10-11.md) 及各阶段证据保留为发生时的历史事实。主线合并不产生新的正式发布版本，不改写历史标签和 Release；线上环境、原站点、账号、数据库和附件均保持本次 Git 操作前的状态。
