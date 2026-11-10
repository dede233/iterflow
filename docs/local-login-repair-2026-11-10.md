# 本地登录恢复及发布覆盖验收（2026-11-10）

## 授权与范围

用户要求修复本地登录 500、确认正常登录并验证发布目标改动，随后明确授权重置本地 admin、密码存入本机凭据文件。仅处理本机 ServBay PostgreSQL / Redis、专用 `iterflow_v150_local` schema 和当前源码的 API / Web；没有连接或修改 TEST / 正式环境，没有推送、合并、tag 或 Release。

## 原因与修复

- 最初登录 500 的日志证据为 PostgreSQL `127.0.0.1:5433` 连接拒绝；ServBay PostgreSQL 17、Redis 7 均未运行，已通过 ServBay 服务控制恢复。
- 本机 schema 仍为 `0004_integrity`，API 是长时间未重启的旧进程。当前源码需要 `0017_target_releases`；启动脚本原先还把 `0004_integrity` 写死为允许版本。
- 保留根 `.env`，停止本机 API 后备份 schema、配置、启动脚本及附件；在独立 PostgreSQL 17 容器恢复并演练既有迁移，再仅升级本机专用 schema 至 `0017_target_releases`，重新启动本机 API。没有新增迁移、seed、数据库恢复或降级。
- `tools/local-start.py` 改为读取当前 PostgreSQL Alembic head；保留 schema 检查，增加回环地址限制、连接超时和显式升级提示。本地 SMTP 固定关闭，不随启动自动迁移。
- 原 admin 密码已被更改，初始化配置不再有效。按用户授权重置 admin，使用现有 Argon2id 哈希，revision +1，原子撤销 12 条活动 refresh 会话并写入本机恢复审计；账号、角色和业务数据保留。
- 随机新密码仅保存到仓库外 `/Users/xiaweiyi/Developer/deliverables/iterflow/local-access/本地登录信息.txt`，父目录 `0700`、文件 `0600`。本文及仓库不记录密码、令牌或密钥。

## 数据保留与异常记录

交付证据目录：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-10/local-login-repair`，仅本机用户可访问。

- `local-before.dump` SHA256：`2198bb6d1491b1b454f14aa0e8462e800170a948a6183ea5c4d510785ec8c4b2`。
- 21 张原业务表的原行/原列按主键与隔离演练后的结果比较，附件内容哈希一致；已有版本 1 保持不变。
- 首次比较 STOP：角色 3 / 4 的 `updated_at` 与演练不同。核对既有 `0008_version_role_permissions` 的冻结 helper，确认为执行时间写入；仅放行这两个字段的时间差，并核对 revision 增量及同时间迁移审计，其他原列严格一致。DDL 已成功，不重跑迁移或回库。
- 上述验证断言失败后的 shell 后续命令仍启动了 API；本轮记录该控制顺序问题。随后先完成只读保留证明，才执行账号恢复和合成业务验收。
- 最终保留复核首次 STOP 于正常登录更新的 `sys_user.last_login_at`；核对 AuthService 后把该正常登录字段列入预期变更。其余授权变更限于 admin 密码/revision/更新信息及旧活动会话撤销；旧会话行和完整旧审计仍保留。
- 仅新增两组清晰命名的本机合成系统、需求、版本和目标记录，供用户查看。没有清空旧数据或导入线上数据。

## 实际验证

| 检查 | 结果 |
| --- | --- |
| 备份恢复、隔离迁移、本机迁移和原数据/附件保留 | PASS |
| 启动检查：当前 head、拒绝远端、拒绝错误 schema、拒绝旧 revision、实际本机依赖 | 5 PASS |
| 正常 API 登录、当前账号、refresh、logout | HTTP 200 |
| logout 后重复 refresh | HTTP 401，符合预期 |
| 真实浏览器输入新密码并进入首页 | PASS |
| 1440px：发布时记录小程序 A，发布后多选补记 PC B / 小程序 C | PASS |
| 375px：不选目标正常发布，发布后多选补记全部 3 个目标 | PASS |
| 补记前后原 Release 完全一致、每版本仍仅 1 条 Release，需求已上线 | PASS |
| 已记录目标禁用重复选择、目标记录数量、页面无横向溢出及截图复查 | PASS |
| API health / ready、Web | HTTP 200 |
| 启动脚本 Ruff / 格式、前端 TypeScript、Git diff 检查 | PASS |

真实浏览器用例 `Real target publishing: optional coverage and later multiple target records`，一次运行覆盖两种宽度和小程序 / PC 混合目标。相关测试补充了不选择目标直接发布场景。原本机版本 1 未变；合成版本 2 / 3 保留在本地。

证据包含 `backup-proof.json`、`migration-result.json`、`account-recovery-result.json`、`browser.log`、`real-browser/` 截图和 `final-result.json`；凭据和原始数据快照仅位于受限的本机目录。

## 使用与回退边界

- 地址：<http://127.0.0.1:5173>，账号 `admin`，密码见本机凭据文件。
- 合成版本：`/#/versions/2`（发布时勾选）、`/#/versions/3`（上线后补记）。
- ServBay PostgreSQL / Redis 和本机 API / Web 保留运行；仅清理本任务临时演练容器。已有 Preview 容器不变。
- 本机 schema 已前向升级，不直接运行旧源码、降级迁移或覆盖当前数据库。原始备份只供另建隔离恢复核验；本机保留数据的回退须单独制定方案。
- 没有执行远端八项 CI；本轮为本机环境恢复与聚焦验收，线上状态未重新核查。
