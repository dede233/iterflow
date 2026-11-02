# 2026-11-02 人员选择及多人验收测试部署

用户明确授权部署测试环境，正式环境不动。已完成，测试入口：https://sx-kc.xyz:8444 。部署源码 `cd1f7ee24b933b0adafb1b9513cfa033194deae7`（包含 `bc6f9b2` 功能与 MySQL preflight 修复）。没有推送、合并、tag/Release 或正式部署；本轮未运行远端 CI。

## 部署与数据保留

- TEST project：`iterflow-acceptance-20261012-753ebd`；数据库 `iterflow_acceptance`。
- API／worker：`iterflow-api:multi-accept-cd1f7ee`；Web：`iterflow-web:multi-accept-cd1f7ee`。先校验原镜像 config、层摘要和源码标签，再基于已加载镜像构建补丁层；无依赖变更、无网络构建。以非 root 容器读取源码并校验 SHA-256。
- 停止测试 Web、worker 和 API 写入，完整备份数据库与附件；在新建无外部端口、内部网络、关闭 SMTP 的 MySQL 副本恢复，逐表内容摘要和附件摘要一致。
- 隔离旧版本到新版本 CLI 迁移与 preflight 通过后，实际 TEST 升级 `mysql57_0009 → mysql57_0010`。29 张非 Alembic 表的行数／内容摘要及 1 个附件逐一保留（仅忽略预期改变的生成列 `single_actor_role`），未清空、重建、补种数据或重置账号。
- 迁移后、恢复写入前再次完整备份。API／Web health 和 API ready 通过，worker 运行，挂载和重启策略保持；HTTPS 8444 返回 200。完成时间 2026-11-02 11:47:18 +08:00。
- 正式容器 ID／镜像／启动时间／挂载／重启策略及正式站点配置哈希与部署前相同。测试数据库／Redis 容器未替换，SMTP／运行与迁移配置、Compose 和自动恢复文件哈希保持。

备份（服务端，每份含 database.sql、uploads.tar、摘要 manifest）：

- `/opt/iterflow/backups/collaboration-test-multi-accept-pre-20261102T033334Z`
- `/opt/iterflow/backups/collaboration-test-multi-accept-post-migration-20261102T034646Z`

服务端完整证据：`/opt/iterflow/upgrade-evidence/multi-accept-bc6f9b2`，包含 before／migration-after、rehearsal、fixed-image-manifest、deployed、closeout 和原始失败日志。本地证据：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-02/multi-accept-deployment-bc6f9b2`。

## 部署后实际验收

新建专用需求 `REQ-20261102-0001`（ID 17），没有编辑既有业务记录、没有关联版本或执行发布。

1. 既有产品账号创建需求并指定既有研发负责人确认。浏览器以确认人提交，成功进入待开发后自动打开“安排设计、开发与验收人员”；无需再次点卡片入口。
2. 浏览器选择开发甲为开发人员、开发甲／乙为两名验收人；保存成功、卡片回显多人、原确认人保留，状态保持待开发。
3. HTTPS API 以开发甲进入开发中、提交验收；以验收乙单独通过，状态变为待发布（DONE）。
4. 验收甲使用验收前 revision 再提交返回 409；流程记录只有一条 STATUS_DONE，实际操作者为乙，快照包含两名验收人。
5. 刷新页面确认待发布和两名验收人显示，浏览器恢复原产品测试账号。

结果：[部署摘要](evidence/multiple-acceptance-deployment/deployment.json)、[真实流程结果](evidence/multiple-acceptance-deployment/live-flow-result.json)。浏览器截图保存在本地证据目录：live-auto-assignment.png、live-multiple-acceptors.png、live-acceptance-complete.png。

## 修复、验证边界和限制

- 首次隔离恢复因初始化临时 MySQL socket 已可用、TCP 未就绪而失败，改为认证 TCP SELECT 1。实际测试库此时未迁移。
- 隔离 CLI 演练暴露应用 preflight 仍只接受 0009；修复后本地新建 MySQL standard／portable 各 17 PASS，含部署 CLI、重复迁移、历史数据、多人验收、发布主链和 preflight，Ruff／mypy／diff check 通过。此前完整开发回归详见执行记录，本轮修复后未重跑全量 PostgreSQL／前端测试。
- 本地初次 MySQL 容器启动 exit 139，相关失败日志保留；重建／重新启动并确认 TCP 就绪后通过。
- 补丁镜像第一次复制源码继承 0600，非 root 校验拦截 PermissionError；仅将无密钥源码改为 0644 后重建并验证，保留失败记录。
- 浏览器首次等待使用了错误弹窗标题，定位实际标题后确认自动弹窗已存在；没有重发业务确认。部署中尚未恢复服务时的探测出现 502／超时，最终 health 和真实流程通过。
- 邮件配置保持，worker 恢复；本轮不把邮件投递／收件箱验收计入结果。
- 已存在多名有效验收人，不能直接降级至旧单人约束；本次没有执行实际 TEST restore 或 downgrade。隔离演练容器已停止，备份保留。正式环境全程未改动。
