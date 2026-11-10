# 2026-11-05 正式升级执行记录

## 授权与当前状态

用户授权本批正式上线，并明确选择“演练通过后立即短暂维护”。正式上线后再准备下一版本：检查业务系统与反馈/需求/版本的绑定，业务系统内的模块入口先隐藏。本批不创建 tag/Release；下一版本不随本批上线。

**正式升级及上线后复核 PASS。** 正式 API/worker/Web 为冻结源码 `5401215`，数据库 `mysql57_0012`。维护北京时间 13:11:38–13:13:34，共 116.47 秒；实际迁移 6.45 秒。用户明确允许演练期间短暂停止 TEST；TEST 已于正式维护前恢复，暂停前后 SQL 与附件摘要一致，容器身份、挂载和配置保留。

## Git 与 CI

- 合并前 local/GitHub/Gitee master 均为 `5f5d74e054775288b19e02487ca0af4769d858a4`，无漂移。
- 冻结候选 `5401215b845dfd09a2dd916fab9dfc37b2707b03`；[候选八项 CI](https://github.com/dede233/iterflow/actions/runs/41965077311) 全部 success。
- no-ff 合并 master 为 `564916b26605863550064342e72291922a3e211b`，完整 tree 与冻结候选一致。
- [master 八项 CI](https://github.com/dede233/iterflow/actions/runs/41968069982) 全部 success：backend、frontend、docker_smoke、s3、browser_smoke、backup_restore、mysql57 (standard)、mysql57 (portable)。
- GitHub/Gitee master 均已同步 `564916b26605863550064342e72291922a3e211b`。正式切换前再次读取双远端，仍一致；本工作记录未包含在冻结产品中。

## TEST 最终候选验收

仅将 Web 更新为 `iterflow-web:release-5401215-test`，源码 `5401215`；API/worker 仍为 `ab8bd07`，数据库仍为 `mysql57_0012`，没有执行数据库命令或迁移。preflight/prepare/deploy/verify 全部 PASS，保留配置、附件挂载及正式保护基线。

合成账号只读验收五项 PASS：两张需求图片及大图预览、详情编号保留且无复制按钮、移动详情、摘要编号无复制按钮、移动摘要。正常登录之外没有业务写操作。

TEST 首页 SHA256：`6de008049443447852f98cefdc7312965ce81fb39ef34e45c42237a5fb8b1a4e`。

## 正式制品与控制器

生产 API 与 TEST 最终 Web 均为冻结源码 `5401215`，API 与 worker 共用 `iterflow-api:release-5401215`。包通过宝塔正常文件上传，终端只执行短控制命令；未使用 Base64/数据块/长脚本传输。

- 主包 `production-5401215.tar`：93,788,160 字节，SHA256 `9071c9b9d207ddfd7fdf3c861adbfdb0262258688a8d7a6147c2dc48d3239485`。
- 门禁包 `production-gates.tar`：SHA256 `61d643c52499e72d83fa3a57ed404ca43b4cb956e782e4024cacd05d331711a8`。
- 服务器证据目录 `/opt/iterflow/upgrade-evidence/production-5401215`，主包及门禁包摘要匹配。
- stage PASS：amd64、源码标签、镜像 config/rootfs 身份、API 文件哈希及依赖检查通过；正式和 TEST 基线未变。
- 本地控制器验证：18 项数据/结构/触发器/迁移保护测试、8 项维护前门禁和 DDL 前后失败恢复边界测试通过。TEST Web 控制器 16 项离线检查通过。

本地制品和门禁证据：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-05/production-5401215/`。SQL、密钥、完整配置和生产附件不写入仓库。

## 阻塞与执行异常

1. TEST 首次 prepare 以相对路径调用，残留任务检测误识别自身而 STOPPED；尚未开始备份/切换。确认无残留后改为绝对路径执行，prepare 及后续阶段 PASS。保留服务器 `failure-prepare-20261105T043313Z-3009401.txt`。
2. API 本地包装脚本在完成镜像和证明后读取了错误的 `web_image` 键，出现 KeyError；修正为 `api_image` 后核对归档/身份，服务器 stage PASS。产品内容未改变。
3. 控制器测试最初的三个失败来自模拟环境未提供 API/WEB 常量，修正夹具后 8 项通过；没有修改生产失败处置规则。
4. 正式 `precheck.py` 在演练可用内存条件停止：要求 >850000 KiB，实际约 687 MiB；无可停止的遗留演练容器。取得用户明确授权后暂停 TEST，可用内存约 1065 MiB。重跑迁移权限、请求体大小、身份和运行环境检查全部 PASS，原失败证据保留。维护阶段只有串行 helper，采用独立资源预算；仅在演练 PASS、TEST 恢复 PASS、克隆容器全停止后启用，演练门禁保持原值。
5. 服务器 `cp` 别名会提示覆盖，首次未替换 ops.py；改用明确的 `/bin/cp` 安装已校验的 r2 控制器，无产品或数据影响。一次外部 `/api/health` 探测误用不存在的路径返回 404；服务实际通过容器内 `/health` 和 `/ready` 验证。

## 演练、恢复和正式切换

- 正常上传 `resume-r2.tar`，SHA256 `9cbb96f067927ce813cb3e60f4d15fc1eacf15b379d2436736010e742efb093b`。运行环境比较仅允许 BUILD_SHA 变化；正式迁移权限、图片请求体限制及原基线预检通过。
- 在线备份 `/opt/iterflow/backups/production-5401215-online-rehearsal-20261105T050532Z`，旧镜像、配置另行留存。克隆仅在内部隔离网络运行，SMTP 禁用。
- 演练 `mysql57_0011 → mysql57_0012` 为 6.34 秒。29 张旧业务表全部原列数据、1 个附件和 91 个触发器保留，迁移允许的字段/索引变化与新服务启动验证 PASS。触发器摘要 `e1d9b8877a9194a43a672f0397874002d41fa3578dd2c19313fecc31ff0f01a6`。克隆容器停止，证据保留。
- TEST 先恢复 DB/Redis，SQL 摘要及附件内容相同后恢复 API/Web/worker；13:11:09 恢复 PASS，原容器身份/挂载/环境保留，8444 页面返回正常。正式在演练期间未变。
- 正式维护入口返回 503/Retry-After，停止写服务后重新获取一致备份及前后稳定快照，然后执行迁移。29 张旧表数据（含账号/会话）、触发器、附件与迁移结构差异均 PASS；未创建测试业务数据、未清理异常空需求。
- 新 API、Web、worker 按顺序启动，源码及镜像身份一致、健康正常、重启数均 0；邮件/JWT/挂载/重启策略保留，TEST 与正式 Redis 保持不变。恢复原 Nginx 入口后成功开放访问。
- 13:14:33 上线后复核 PASS：三次公开首页检查、容器健康、启动日志无 ERROR/Traceback、完整配置及 TEST 保护检查通过。Safari 正式登录页只读验证通过；未进行正式业务写验收或额外邮件发送。
- `closeout-baseline.py` PASS：保留旧基线历史，将 TEST 恢复控制器正式保护基线更新至 `5401215`，没有重启服务器/宝塔或修改其他站点。

## 备份与回退边界

- 停写最终备份：`/opt/iterflow/backups/production-5401215-final-pre-20261105T051151Z`；SQL 413680 字节，SHA256 `6fb4079dc83b9e3d7d76f533963026b33a6358b79241b261aef2ab97493315d6`。
- 迁移后备份：`/opt/iterflow/backups/production-5401215-post-migration-20261105T051240Z`；SQL 414166 字节，SHA256 `9b8cc68d5c249eb844fefbe21c50c28bf45d6b952db01223a46ba62715733c29`。
- 两份附件包均 266240 字节，SHA256 `8d342c881f2f5fbf8e5bdd0b3031128be650a6894322876120a01bb36d0ed057`。
- 本次没有回退、降级或真实数据库恢复。0012 已取消单人确认约束并增加软删除/描述格式字段，不能直接把旧 96ba96e 应用作为无损回退方案。优先前向修复；恢复旧数据库需新的明确授权，并评估上线后新增数据，不能直接覆盖。
- 升级范围及完整回退门禁见 [上线准备](production-preparation-2026-11-05.md)。服务器成功证据为 `deployed.json`（含 verification）、`rehearsal.json`、`test-restored.json`、`closeout.log`。下一版本在独立分支准备，不包含在本次正式制品中。
