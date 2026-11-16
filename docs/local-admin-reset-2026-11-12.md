# 本机管理员恢复（2026-11-12）

用户明确授权将本机账号 `admin` 重置为其指定密码。仅操作本机数据库 `iterflow` 的 `iterflow_v150_local` schema，不涉及 TEST 或正式环境；密码只写入仓库外权限为 0600 的本机凭据文件，不记入版本控制。

## 原因及处理

本机 PostgreSQL / Redis 正常，但 API 启动检查发现数据库仍为 `0017_target_releases`，当前代码要求既有 `0018_alipay_targets`。因此先恢复本机服务兼容，再重置账号；没有新增产品迁移或修改启动检查规则。

1. 停止失败重启的本机 API 启动任务，备份专用 schema、原配置和旧凭据。
2. 在本任务临时 PostgreSQL 17 容器恢复备份，核对 33 张原数据表的完整行摘要，演练既有 0017 → 0018 迁移；迁移前后数据一致。
3. 再次核对本机基线未变，执行该迁移。仅扩展两张发布目标表的平台检查约束，33 张原数据表内容不变。
4. 在单个事务中锁定 ACTIVE 的 admin，使用现有 Argon2id 实现与 revision 比较更新密码，revision 4 → 5；撤销 17 个旧刷新会话，并追加不含密码的审计。保留账号、角色、邮箱和业务记录。
5. 原子更新仓库外凭据文件，恢复既有 API 启动任务；未修改根 `.env`，本机 SMTP 保持关闭。

旧刷新会话撤销不等同于立即吊销所有已签发的访问 JWT；后者仍遵循现有过期规则。没有为本次重置改变认证机制。

## 验证结果

- API `/health`、`/ready` 和 Web 均返回 200；真实浏览器使用指定凭据登录成功，保留已登录的本机工作台页面。
- 重置后、重新登录前，旧活动刷新会话为 0。变化仅限账号、刷新会话和操作日志三表，另 30 张表完整行摘要保持一致。
- 真实账号工作台、已有版本与需求、三个已发布目标及原发布时间正常展示；375px 页面无横向溢出，新建需求全屏尺寸为 375×812，关闭时未保存业务记录。浏览器控制台错误为 0。
- 已删除本任务临时演练容器和临时密码输入文件；保留备份及验证证据，原有 Docker 预览和本机 Web 服务未停止。
- 首轮保留校验脚本误将操作日志表写为 `sys_audit_log`，断言停止；核对实际模型为 `sys_operation_log` 后修正外部校验并通过，无额外数据库修改。

本次未修改产品源码，验证源码为 `8633cb310ca8cdb1cba51e8673880994f8727d40`。未推送、合并或部署，未连接 TEST / 正式数据库。未将本次浏览器冒烟验收计作完整 140 项 E2E 或远端八项 CI。

## 证据

目录：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-12/local-admin-reset/`，目录权限 0700，敏感备份权限 0600。

- `local-before.dump`：本机专用 schema 备份，SHA256 `714b8a297a638359100e23809b0c8e2cb5e727654eca1e0c41d20d3de1672857`。
- `backup-proof.json`、`migration-result.json`：恢复演练及真实本机迁移证明。
- `account-result.json`、`preservation-result.json`、`final-result.json`：重置、保留与最终 PASS 结果。
- `login-success.png`、`version-real-mobile.png`：实际登录及已有版本页面截图。

凭据文件：`/Users/xiaweiyi/Developer/deliverables/iterflow/local-access/本地登录信息.txt`。备份用于必要时人工核查与恢复，不自动回库或恢复旧会话；本次未执行降级。
