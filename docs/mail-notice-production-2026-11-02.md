# 邮件通知引导：正式上线记录

用户确认测试验收没有问题，要求准备上线正式环境。本轮沿用已有上线流程及短暂维护偏好，所有门禁通过后切换；不创建 tag/Release，不自动降级或恢复数据库。

## 冻结范围与门禁

- 产品源码：`96ba96ef81f96a533e9bc912100651d368a6945f`，TEST 8444 已部署并经用户验收。
- 初始分支：`codex/requirement-summary-no-progress`，`912dc45`；工作区干净。
- 初始 GitHub/Gitee master：均为 `a1c90dd9e19925f70428d9565fce3b8eb7d06f62`，没有漂移。合并前须再次核对。
- 已知正式基线：源码 `2c503bf`、schema `mysql57_0010`；实际执行前重新读取。
- 目标：配套 API/worker/Web 使用 TEST 已验证产物，MySQL 追加 `mysql57_0011`；仅新增可空账号知晓时间，不复制 TEST 账号、邮箱验证或知晓状态。
- 八项门禁：backend、frontend、docker_smoke、s3、browser_smoke、backup_restore、mysql57 standard、mysql57 portable；分支和最终 master 分别通过。

## 执行状态

已完成。2026-11-02 北京时间 18:31:40–18:33:26 短暂维护，耗时 105.64 秒；正式运行源码 `96ba96e`，schema `mysql57_0011`。18:33:54 上线后核验 PASS，服务恢复正常访问。

## 恢复边界

维护前在线备份用于隔离演练；停写后另取数据库/附件一致备份。先迁移后配套更新服务，成功核验后恢复入口。迁移开始后失败不自动恢复或降级，保留检查点。0011 已有知晓记录时拒绝有损 downgrade，旧 API 的启动检查不接受新 schema；界面可先退兼容 Web，后端应前向修复或使用经验证兼容包，不手改 Alembic head。

## 首轮门禁与修复

分支 `6a6987b` 的 [CI 41424891154](https://github.com/dede233/iterflow/actions/runs/41424891154) browser_smoke 为 174 PASS / 21 FAIL。三个旧夹具（发布版本抽屉、确认人分配、阶段人员）未处理新增布局读取 `/me/mail-preferences`，所有失败均为 unexpected request 断言。补齐契约字段完整、SMTP 关闭的明确响应，保留 unexpected/error 及原业务断言；不跳过测试、不修改产品代码，新提交重新执行完整八项 CI。

正式只读预检与在线备份通过，剩余磁盘 21.53 GiB。在线演练备份 `/opt/iterflow/backups/mail-notice-production-96ba96e-online-rehearsal-20261102T100054Z` 仅保留在服务器。独立 internal 网络、独立数据库/附件卷中恢复后迁移 0010 → 0011 耗时 5.89 秒，29 张业务表原有字段、1 个附件及 91 个触发器均保留；MySQL preflight 通过。隔离副本禁用 SMTP、未连接正式 Redis，演练后已停止。正式与 TEST 容器、配置均未变。

## 分支通过与合并核对

首轮最终 7 PASS / 1 FAIL，仅 browser_smoke 失败，原日志保留。修复后分支 `0692ecd75e9d7a9e9964eb86f524b61a5d993428` 的 [CI 41426069207](https://github.com/dede233/iterflow/actions/runs/41426069207) 八项全部 PASS，browser_smoke 为 195 PASS。与 `96ba96e` 的产品源码（app、alembic、frontend/src、依赖、deploy、spec）无差异，仍使用用户已验收的同一产物。

同一 Agent 的复查（非独立审查）：知晓仅操作当前账号、revision/审计同事务、不会发邮件；追加迁移保留旧字段并保护知晓历史。部署脚本核对镜像/配置/挂载，先停 API/Web/worker 再备份，校验停写前后快照；公网上下线采用有界探测，避免把 Nginx reload 交接窗口误判为失败。迁移后异常保留维护，不自动恢复数据库。

合并前 GitHub、Gitee、本地 master 均仍为 `a1c90dd9e19925f70428d9565fce3b8eb7d06f62`，无漂移。使用既有 master 工作树 no-ff 合并；保留该工作树原有未跟踪 data 与历史证据。最终 master `5f5d74e054775288b19e02487ca0af4769d858a4` 的 [CI 41427400140](https://github.com/dede233/iterflow/actions/runs/41427400140) 八项全部 PASS；GitHub/Gitee 均为该 SHA，正式切换前再次核对一致。成功回执保存在本地交付目录及服务器 `gate.json`。

## 正式切换与验收

仅对 8443 设置维护入口并停止 Web/API/worker；停写后获取最终数据库与附件备份，复查快照未变化。追加迁移耗时 6.06 秒；29 张业务表原有字段与行、1 个附件、91 个触发器完全保留，新增知晓列均为 NULL，MySQL preflight PASS。未执行 seed、stamp、真实恢复或业务状态流转。

配套 API/worker/Web 复用 TEST 已验收镜像，镜像身份、挂载、重启策略均符合预期；API health/ready 和 Web healthy，三个服务均运行且 restart_count 为 0。恢复原 8443 Nginx 配置后公网返回 200 且 index hash 与冻结产物一致；随后连续三次公网探测成功。启动以来日志未出现 ERROR、Traceback 或 worker failed。

正式 SMTP、发件人 `iterflow-emil@luqingyao.cc.cd`、8443 邮件链接、JWT/数据库配置和附件挂载保持原值；未复制 TEST 配置或用户数据。TEST 容器、配置及 Redis 均未变化，保留标记仍有效；其他站点未改。控制脚本正式基线已登记为 `96ba96e`，旧基线保存到历史及本次证据目录。

浏览器只读验收：既有登录会话正常，首页仍为 2 条反馈、8 条需求、3 个版本、1 次发布；个人中心显示原通知邮箱已验证，验证输入区保持隐藏。当前账号按规则没有弹窗，浏览器无 warning/error；未更改其邮件偏好或知晓状态。弹出及跨设备知晓写入沿用 TEST 验收和本次 195 项浏览器 CI 证据，未在正式环境创建测试账号或重放写入流程。

## 备份、证据与回退

- 停写后、迁移前最终备份：`/opt/iterflow/backups/mail-notice-production-96ba96e-final-pre-20261102T103151Z`。
- 迁移后备份：`/opt/iterflow/backups/mail-notice-production-96ba96e-post-migration-20261102T103233Z`。
- 数据库 SQL SHA-256：升级前 `2699b0ed2e3d56aa4ef20ba92e81a6c83f95d5b007e7a23f1ced10c6d2e19729`；升级后 `85bad9e12f1dfc1f6457f0356048c3949c5b946b5ea86e61c39c322fbc9da6eb`。
- 附件归档两次 SHA-256 相同：`194de6d80302711b66d8cdef07f738d268046ac65e1b7b76a81fb22387c6230c`。
- 服务器证据：`/opt/iterflow/upgrade-evidence/mail-notice-production-96ba96e`，包括 `gate.json`、演练、升级检查点、`deployed.json`、数据保留快照、备份清单、原配置及保护日志。完整备份与配置仅留服务器。
- 本地交付：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-02/mail-notice-production-96ba96e`，含受控脚本、CI 记录、演练截图和正式页面截图 `production-profile.png`。

若上线后出现问题，先阻断相关写入并保留新数据及日志；按上文兼容边界前向修复或回退兼容 Web。不要直接切回旧 API、降级 0011 或覆盖真实数据库。本次没有触发服务器回退，没有创建 tag/Release。上线结果文档单独在工作分支提交，不改变已通过八项 CI 的 master。

## 操作异常记录

切换前 Safari 当前标签页发生变化，操作时未充分核对目标，将一条部署命令误发到用户另一个 ChatGPT 会话。内容仅为部署脚本路径、源码及 CI 校验元数据，不含密码、密钥或业务数据。已立即向用户说明；服务器只读检查确认旧版本 `2c503bf` 仍运行，切换检查点尚不存在，误发命令未在服务器执行。随后切回宝塔，并对每条命令增加窗口、终端 URL、输入焦点检查，使用单行粘贴后再次核对才提交。未编辑或删除无关会话。
