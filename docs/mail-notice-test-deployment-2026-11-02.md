# 邮件通知引导：测试环境部署

用户明确要求将本次引导弹窗部署到保留测试环境，验证弹出条件和“我已知晓”跨设备效果，先不动正式环境。2026-11-02 17:39:36（UTC+8）完成 TEST 切换，17:46:43 完成 9 项在线检查；本补丁没有推送、合并、远端 CI、tag/Release 或正式部署。

## 运行结果

| 项目 | 结果 |
| --- | --- |
| 测试入口 | https://sx-kc.xyz:8444 |
| 冻结源码 | `96ba96ef81f96a533e9bc912100651d368a6945f` |
| API / worker | `iterflow-api:mail-notice-96ba96e` |
| Web | `iterflow-web:mail-notice-96ba96e` |
| 测试 schema | `mysql57_0010` → `mysql57_0011` |
| 正式基线 | `2c503bf` / `mysql57_0010`，本轮未修改 |

源码由 Git 归档冻结，锁文件/后端依赖与既有运行基线一致；本地 TypeScript/Vite 构建通过。服务端基于已有已核验 amd64 镜像离线构建，使用 `--network none --pull=false`，核对源码文件哈希、镜像 revision 标签及前端 index 哈希。未下载或替换依赖。

归档 `mail-notice-96ba96e.tar.gz` 为 578732 字节，SHA-256 为 `fb4c8bf5dda1c49955ec081a4fb791683409f26c794885d43be699a0db6fabb2`。Web index SHA-256 为 `69c02cd420cef46f7d11141992b1fc2161ad1d88be04d245c37b46e2f25a3e9a`。

## 备份、隔离演练与切换

仅暂停/更新 TEST 应用服务，TEST 切换期间短暂不可用。数据库和 Redis 容器没有重建，现有账号、数据卷、附件及 Brevo 配置保留。备份包含数据库及附件，SQL 包含表和触发器，文件哈希存于各备份目录的 `manifest.json`。

- 升级前：`/opt/iterflow/backups/mail-notice-test-pre-20261102T093809Z`。
- 迁移后：`/opt/iterflow/backups/mail-notice-test-post-migration-20261102T093904Z`。
- 演练使用新建内部网络和无公开端口的临时 MySQL，恢复 TEST 备份后迁移；演练完成已停止该临时实例，没有恢复覆盖 TEST 或正式数据库。
- 演练和实际迁移前后比对全部 29 张业务表的原有字段哈希、附件哈希及 91 个触发器数量；结果一致。迁移只增加可空知晓时间列，迁移后原记录全部尚未知晓。
- API、worker、Web 健康状态及 API health/ready 构建 SHA 通过；仅重载 `iterflow-test-nginx`，公网 TEST 页面 200 且 index 哈希匹配。
- 前后检查正式 API/Web/worker/Redis 的容器 ID、镜像、启动时间、挂载及重启策略，以及正式 vhost 配置哈希；均未变。TEST 邮件配置、Compose 和恢复配置哈希也未变。

首次在短暂 TEST 停服窗口内访问页面超时；服务恢复后重新导航成功。归档解包打印系统 tar 安全过滤提示，不影响哈希核验、构建或迁移。本次没有产品测试失败或部署重试修复。

## 在线验收

使用既有 TEST 登录辅助函数，通过正常 HTTPS API 登录和操作；未创建账号、重设密码、直改知晓字段或发送验证码。仅 `ceshi008` 记录本次知晓，供验证跨会话持久化；其他测试账号没有被批量标记。

9 项全部 PASS：

1. 未验证且允许邮件的账号满足提示资格；已验证账号的状态保留。
2. 知晓成功、revision 加一，邮箱、待验证地址、验证状态、邮件偏好均保持原值。
3. 同账号另一份预先登录的独立会话立即读取到已知晓。
4. 旧会话使用旧 revision 提交返回 409。
5. 最新 revision 重复知晓幂等，响应及 revision 不再变化。
6. 同账号第三次全新登录仍读取到已知晓。
7. `ceshi012` 与 `ceshi006` 的邮件设置和知晓状态未受影响。
8. 操作前后通知事件、投递记录及附件哈希未变，没有生成邮件投递。
9. 正式容器及受保护配置与部署前快照一致。

真实 Chrome 页面使用现有 `ceshi006` 会话验证：通知中心没有弹窗，个人中心显示邮箱已验证，验证码区域保持收起；浏览器捕获的 error 日志为 0。用户的已验证邮箱及知晓状态没有被修改。首页另外观察到部分历史动态显示“未知操作（CONFIRM / PARTICIPANTS_CHANGE / RECIPIENTS_CHANGE）”；该文案问题不阻断本次邮件引导验收，未在本次部署中扩大产品修改范围。

上述跨设备检查采用三个独立 API 登录会话，未冒称在三台实体设备上操作。未绑定/待验证文案、关闭后刷新、OFF/SMTP 停用等 UI 分支已有部署前浏览器测试，本轮没有通过改动真实 TEST 邮件配置来重复模拟这些条件。用户手机与电脑上的最终交互验收待用户完成。

手动验收建议：选择尚未验证邮箱、邮件偏好非 OFF、尚未点过知晓的测试账号，在首页查看弹窗；点击“我已知晓”，再用另一浏览器或设备登录同一账号，应不再提示。另一个已打开页面可刷新后确认结果（不是实时广播关闭）。已验证账号不会弹窗。`ceshi008` 已用于知晓验收，不适合再测首次弹出；不提供清空知晓历史的后门。

## 证据与回退边界

服务端证据：`/opt/iterflow/upgrade-evidence/mail-notice-96ba96e/`，包含 `prepared.json`、`images.json`、`preserved.json`、`before.json`、`rehearsal.json`、`migration-after.json`、`deployed.json`、`acceptance.json`、脚本和保护日志。测试控制文件仅追加 `mail_notice_deployment` 记录，保留其他状态与正式基线。

本地包、构建日志、验收脚本及截图：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-02/mail-notice-test-96ba96e/`。截图包括 `deployment-pass.png`、`acceptance-pass.png`、`verified-account.png`。

目前已存在真实 TEST 知晓记录，新增迁移拒绝有损 downgrade。若需回退界面，可回退兼容 Web 并保留 schema；旧 API/worker 的启动检查不接受 0011，不能直接切回旧后端。应前向修复或使用经过验证的兼容包，不手改 Alembic head、不自动恢复备份、不清空知晓记录。正式环境的升级与回退仍另行授权。
