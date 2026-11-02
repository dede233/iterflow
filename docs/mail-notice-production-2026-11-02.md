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
