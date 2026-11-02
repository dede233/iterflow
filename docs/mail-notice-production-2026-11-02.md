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

准备中。尚未执行本次正式迁移或切换；后续结果与失败证据据实追加。

## 恢复边界

维护前在线备份用于隔离演练；停写后另取数据库/附件一致备份。先迁移后配套更新服务，成功核验后恢复入口。迁移开始后失败不自动恢复或降级，保留检查点。0011 已有知晓记录时拒绝有损 downgrade，旧 API 的启动检查不接受新 schema；界面可先退兼容 Web，后端应前向修复或使用经验证兼容包，不手改 Alembic head。

## 首轮门禁与修复

分支 `6a6987b` 的 [CI 41424891154](https://github.com/dede233/iterflow/actions/runs/41424891154) browser_smoke 为 174 PASS / 21 FAIL。三个旧夹具（发布版本抽屉、确认人分配、阶段人员）未处理新增布局读取 `/me/mail-preferences`，所有失败均为 unexpected request 断言。补齐契约字段完整、SMTP 关闭的明确响应，保留 unexpected/error 及原业务断言；不跳过测试、不修改产品代码，新提交重新执行完整八项 CI。

正式只读预检与在线备份通过，剩余磁盘 21.53 GiB。在线演练备份 `/opt/iterflow/backups/mail-notice-production-96ba96e-online-rehearsal-20261102T100054Z` 仅保留在服务器。独立 internal 网络、独立数据库/附件卷中恢复后迁移 0010 → 0011 耗时 5.89 秒，29 张业务表原有字段、1 个附件及 91 个触发器均保留；MySQL preflight 通过。隔离副本禁用 SMTP、未连接正式 Redis，演练后已停止。正式与 TEST 容器、配置均未变。

## 分支通过与合并核对

首轮最终 7 PASS / 1 FAIL，仅 browser_smoke 失败，原日志保留。修复后分支 `0692ecd75e9d7a9e9964eb86f524b61a5d993428` 的 [CI 41426069207](https://github.com/dede233/iterflow/actions/runs/41426069207) 八项全部 PASS，browser_smoke 为 195 PASS。与 `96ba96e` 的产品源码（app、alembic、frontend/src、依赖、deploy、spec）无差异，仍使用用户已验收的同一产物。

同一 Agent 的复查（非独立审查）：知晓仅操作当前账号、revision/审计同事务、不会发邮件；追加迁移保留旧字段并保护知晓历史。部署脚本核对镜像/配置/挂载，先停 API/Web/worker 再备份，校验停写前后快照；公网上下线采用有界探测，避免把 Nginx reload 交接窗口误判为失败。迁移后异常保留维护，不自动恢复数据库。

合并前 GitHub、Gitee、本地 master 均仍为 `a1c90dd9e19925f70428d9565fce3b8eb7d06f62`，无漂移。使用既有 master 工作树 no-ff 合并；保留该工作树原有未跟踪 data 与历史证据。合并后须运行本提交自身八项 CI 并核对双远端相同 SHA，成功回执保存到本地交付目录及服务器 `gate.json`。正式切换仍待最终门禁。
