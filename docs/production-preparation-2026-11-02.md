# 2026-11-02 正式上线准备执行记录

## 授权与冻结基线

用户授权完成上线准备、将最新修改部署到保留测试环境验收、跑完八项 CI，通过后确认 master 无漂移再合并并同步 GitHub/Gitee；更新升级和回退文档。正式部署、正式数据库 migration/GRANT/restore/写入、tag/Release 不在本轮范围。

- 源分支：`codex/requirement-summary-no-progress`，本轮开始 `9faad46`（包含最新通知邮箱输入区隐藏）。
- GitHub master：`6fb84100be208e8faaa7fe7b7dd4b4533ad7efa5`。
- Gitee master：`10f6bfa6410c7836d7d43e402a175d56ad9577c7`；已知落后，不覆盖未知提交。合并前重新读取并核验祖先关系，使用非强推同步。
- 正式环境只读基线：`198f831d67e8b475975915b1824d711b949fb998`，`mysql57_0006`，health/ready 正常。测试 API/worker 为 `cd1f7ee`，schema `mysql57_0010`，Web 为 `1923a22`。

## 本轮准备内容

- 将最新邮箱标签/输入框与验证码行一同按“重新验证”展开，保留未验证直接展示及成功收起逻辑。
- [升级与回退操作清单](collaboration-workflow-upgrade.md) 修正实际双数据库迁移编号、多人验收规则、RDS 权限、维护窗口、API/Web/worker 配套、正式邮件站点及分阶段恢复边界。
- 同步 MySQL 包说明的 head、运行表权限数量和 worker 启动说明；不改历史迁移或正式数据。
- 本轮 CI 必须包含 backend、frontend、docker_smoke、s3、browser_smoke、backup_restore、mysql57 standard/portable 八项，不以旧 SHA 的结果替代最终提交。

## 待执行记录

此处将在各项实际完成后追加证据。尚未完成的门禁不视为通过。

## 正式执行边界

本轮完成后，仍需在正式部署授权及维护窗口内重新核对正式 SHA/schema、容量与 RDS 权限，取得一致的正式数据库/附件备份，并在隔离副本演练实际正式数据，再实施迁移和启用正式 SMTP。本轮不备份或复制正式业务内容，不将测试数据/账号/邮箱验证状态迁入正式。正式数据迁移耗时、最新 Brevo 额度与正式实际收件不能用 CI 或测试数据结果代替。
