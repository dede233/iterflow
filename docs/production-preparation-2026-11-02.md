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

## 测试部署与最新界面验收

2026-11-02 12:37:39 +08:00，将候选 `2c503bfb216bcd61835de7a236a454ff8d6b0c5c` 的 Web 更新到 8444，镜像 `iterflow-web:production-prep-2c503bf`，config `sha256:04a13616c45a69de4662893bd59e06cf83cafad5b11b65d3a6e30b74041ef91e`。公网 index SHA256 为 `c6fcf16000bb02c91207360f4d326fe32023321ff4d606051328cb514db6fd78`，与构建产物一致。

- 仅修改 TEST WEB_IMAGE；API/worker 仍为 cd1f7ee，与候选后端源码无差异。API/Web healthy、ready 和 worker 运行通过，正式容器/配置及测试其他容器、运行/迁移/邮件配置摘要保持一致。
- 既有已验证账号：通知邮箱标签/输入框、验证码行和发送按钮初始均不存在；点击重新验证后一同显示；刷新后收起，PASS。
- 375px 输入外框和发送按钮同一行，均 44px 高，无横向溢出，PASS。未点击发送或修改偏好，不发送真实邮件。
- 服务端证据 `/opt/iterflow/upgrade-evidence/production-prep-2c503bf`；本地证据 `/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-02/production-prep-deployment-2c503bf`，含脚本、manifest、服务器回执截图、页面截图和 live-ui-result.json。

## 首轮 CI 发现与修复

候选 2c503bf 的 [CI 41389217401](https://github.com/dede233/iterflow/actions/runs/41389217401) 中 backup_restore 失败：恢复库实际已为 `0012_multiple_acceptance`，但演练脚本硬编码旧 `0011_notification_delivery`。修复为从已运行镜像读取 Alembic 唯一 head，备份前确认实际版本等于该 head，恢复后同时核对备份版本和 head；不放宽门禁、不跳过恢复或用重跑掩盖真实失败。`bash -n` 与 diff check PASS，新提交重新运行完整八项 CI。其余首轮结果及最终结果随后记录。

本地离线包构建首次被系统旧 Python 的 extractall(filter=...) 不支持拦截；改用已安装 Python 3.12，保留失败日志。后续 Docker 构建出现外部包 DNS 问题，处理与最终产物验证结果另记；不能将构建中视为已交付。
