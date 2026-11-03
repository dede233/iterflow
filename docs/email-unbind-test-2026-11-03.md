# 通知邮箱取消绑定

2026-11-03 用户授权实现、测试并部署保留 TEST 环境，正式环境不变。本轮不推送、合并或发布。

## 确定行为

- 个人中心“邮件通知”提供“取消绑定”及明确确认窗口，有当前邮箱或待验证地址时可操作。
- 仅操作登录账号，提交邮件设置 revision；在同一事务清空用户邮箱、已验证地址／时间、待验证地址及验证码挑战，递增用户和邮件设置 revision 并记录 `EMAIL_UNBOUND` 审计。旧 revision 返回 409；最新 revision 重复解绑不重复修改或审计。
- 保留邮件偏好、账号“我已知晓”、站内通知和历史投递记录。保留发验证码的限流时间，防止解绑绕过发送频率限制。
- 发送前重新检查绑定，排队中的旧验证码和进度邮件跳过；邮件发送与解绑通过账号锁串行，解绑成功后不能再开始向旧地址投递。已经发出的邮件无法撤回。
- 可以重新绑定，但必须重新验证；不补发旧进度邮件。
- 无 schema 迁移，保留 PostgreSQL 与 MySQL 5.7 路径及发布契约。只更新开发契约。

## 实现和本地验证

完成接口 `POST /me/email-unbind`、邮件设置服务、投递与解绑的账号锁顺序及个人中心确认窗口。仅当前账号可调用，无新增角色或权限。前端成功后清空输入并刷新个人资料；409 保留确认窗口并提供“刷新设置”，刷新后仍需再次明确确认，不自动重放。

修改文件涵盖 `spec/openapi-development.yaml`、生成类型和接口文档标签；后端 `api/v1/mail.py`、`schemas/mail.py`、`mail_preferences_service.py`、`delivery_service.py`；前端 `MailPreferences.vue` 及配套前后端、浏览器测试。没有修改实体、迁移、历史发布快照或业务主链。

本地实际结果：

| 检查 | 结果 |
| --- | --- |
| 全套前端单测 | 399 PASS |
| TypeScript/Vite 构建、生成类型一致性和 bundle 预算 | PASS，最大 JS 296.8 KiB |
| 浏览器 | 18 PASS，覆盖 375/768/1440px 解绑确认、取消、pending-only、成功后刷新、跨会话旧 revision 冲突、错误保留，以及个人中心和邮件引导回归 |
| PostgreSQL | 23 PASS，另追加事务回滚 1 PASS，共 24 项；使用本任务新建容器与临时 schema |
| MySQL 5.7 | 21 PASS，另追加事务回滚 1 PASS，共 22 项；使用本任务新建 portable 容器与逐用例临时数据库 |
| 契约及接口文档 | 20 PASS，已发布 v1.8.1 契约校验值保持不变 |
| Ruff / Python 类型 | 全部 PASS，108 个应用文件无类型问题 |

双数据库新用例各七种场景：普通账号权限与跨账号隔离、保留 OFF、只取消待验证地址、同 revision 双请求单赢家、审计失败整体回滚、排队验证码／进度邮件跳过而站内通知保留、SMTP 进行中时解绑等待该发送结束。还验证最新 revision 重复解绑幂等、旧验证码失效、知晓跨会话保留、保留验证码限流、同地址重新绑定不能补发旧进度邮件。SMTP 使用隔离测试桩，不发送真实邮件。

首次失败与修正记录：

- 官方 MySQL 5.7 amd64 镜像在本机临时初始化阶段发生 segmentation fault，21 项均为连接前置失败；保留日志，换用项目已具备的兼容客户端镜像创建独立 portable 容器，确认 TCP ready 后 21 项全通过，没有连接任何现有数据库。
- 新接口文档的 revision 中文标签遗漏导致 1 个文档门禁失败，已补充“修订号”并重新生成标签，20 项全通过。
- 追加回滚用例最初预期未处理异常，但项目中间件按既有规则转换为 HTTP 500；调整为断言 500 并检查两个表均回滚，双库各 1 项通过。
- 首次根目录 mypy 未读取 backend 配置、另一次 pytest 缺少 scripts 路径，均为命令入口问题；按 backend 配置及正确 PYTHONPATH 重跑通过。首轮输出均保留，未删除检查或放宽规则。

同一 Agent 复查（非独立审查）：确认 user → preference 加锁顺序与发送一致，解绑不反向锁投递行，不删除历史记录；最新 revision 幂等、错误事务回滚和账号切换不套用旧响应均有覆盖。阶段无剩余失败、无规格冲突，继续 TEST 部署。

本地证据位于 `/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-03/email-unbind/`。

## TEST 部署记录

冻结源码 `f879eaa17700dfcfe455f09974e606e41dd1de04`；部署包 557,258 字节，SHA256 `8e1883c8faec3a796f30e2bfd7ad8ac8a5ff764debc09db9a78d83c8c4a679c9`。通过宝塔普通文件上传，校验后离线复用已有镜像构建，仅更新保留 TEST API、worker 和 Web。终端只执行不超过 500 字符的单行控制命令，完整输出写受保护文件，不通过终端传输文件或长载荷。

首次切换未通过：新 API/Web 启动后、恢复 worker 前，全库快照相等断言失败。脚本自动恢复原 TEST 三个应用及 `images.env`，没有恢复或迁移数据库；原应用健康。首次日志、备份、`failure.txt` 保留于服务器 `/opt/iterflow/upgrade-evidence/email-unbind-f879eaa/`。

只读核对首先发现只有 `sys_refresh_session` 变化，业务表、schema 与附件一致。会话记录显示账号 7 于 `2026-11-03T04:41:38Z` 正常刷新，原因 `REFRESHED`；与测试页自动恢复连接相符。主动退出该浏览器会话后，于 `04:47:54Z` 另产生对应 `LOGOUT` 会话变更和退出审计，这是诊断时新增的预期变化。诊断脚本原先仅允许会话表变化，因此在退出后再次诊断时断言失败；随后只读列出表名、认证原因和退出审计确认范围，未读取或输出 token/JTI。一个只读诊断命令参数入口错误也已保留日志。

退出测试页后，使用同一冻结源码和产物，在独立 `retry1/` 证据目录重新核查原应用及正式环境保护基线，再取新备份重试。保留全库所有表（包括会话和审计）的快照相等检查，没有排除变动表、放宽数据门禁或覆盖首次证据。

`retry1` 全库一致性检查通过，但于测试代理重载失败，应用再次自动回退成功。只读检查 systemd 日志与既有 `autorecovery.py`：`prepare_nginx()` 要求全部测试容器 Running，包括 worker；部署脚本却将代理重载安排在 worker 启动前。这是本次部署控制顺序错误，并非应用功能失败。保留 `retry1-deploy.log` 与恢复脚本错误回执，未修改恢复脚本或 systemd。

`retry2` 控制文件只调整这两步顺序：全库相等 → 启动新 worker → 重载 TEST 代理。原始脚本 SHA256、精确替换次数和断言数量核验通过；应用源码、250 个产物文件和所有保护检查保持一致。控制文件通过普通文件上传，SHA256 `4a4b2163fc140ecf43be84717e9539b2f875ff8dc406a8136f031de847962519`，使用新 `retry2/` 证据目录。

终端重连插曲：修正文件上传、第三次切换尚未执行时，网页终端持续空白；刷新及只读 `date -u` 没有命令回显，未据此假定命令成功。请求用户手动恢复 root 提示符，未修改、重启或升级宝塔。`2026-11-03T05:11:39Z` 本机 HTTPS 只读核验 TEST / 正式均 200，TEST 已恢复旧 Web `d0c5700762fd1419352e2e5b9c5d0e6a815701738143e4187acd702251d580dd`，正式保持 `69c02cd420cef46f7d11141992b1fc2161ad1d88be04d245c37b46e2f25a3e9a`。当时尚未进行在线解绑或创建验证挑战。用户随后手动恢复 root 提示符，修正脚本在服务器再次核验哈希一致，继续执行 `retry2`。

## 最终部署与在线验收：PASS

`retry2` 于 `2026-11-03T05:20:38Z`（北京时间 13:20:38）成功，控制流程耗时 48.75 秒（不是精确中断测量）。TEST API/worker 使用 `iterflow-api:email-unbind-f879eaa`，Web 使用 `iterflow-web:email-unbind-f879eaa`，源码均为上述冻结 SHA。

- 升级前 TEST 数据与附件备份：`/opt/iterflow/backups/mail-notice-test-email-unbind-pre-20261103T051957Z`，校验值见服务器 `retry2/deployed.json`。
- 切换前后 29 张表和附件快照完全相等；在恢复 worker 前完成检查，schema 保持 `mysql57_0011`。没有执行 migration、数据库恢复、DB/Redis 重启或清理卷。
- API/Web healthy、worker Running、镜像内容和标签、挂载、重启策略及配置保护基线通过。功能验收后 worker 已恢复，`retry2-final.log` 明确返回 `FINAL_VERIFY_PASS`。
- TEST 页面返回 200，index SHA256 `525086c421f1f6e95be4b37b6251a786b13206ab875af9c25eea87113f43b972`；正式页面返回 200 且保持原 index 校验值。正式容器、配置和 TEST DB/Redis 基线不变，现有 SMTP 配置保留。

通过正常 HTTPS API 和桌面/375px 页面，以已有合成账号 `ceshi008`（ID 9）实际验证：

1. 无登录返回 401、无效 revision 与附带其他 user_id 返回 422；已解绑的最新 revision 重复请求幂等。
2. 仅暂停 TEST worker，再为该合成账号排队验证邮件，避免真实发送；页面显示待验证地址和取消绑定入口。
3. “暂不取消”后保持原设置，再明确确认解绑；输入、待验证地址清空，显示成功状态，取消绑定按钮消失。
4. 独立登录会话读到相同结果，用户及设置 revision 各递增 1；旧 revision 409，旧挑战确认 409，重复解绑不再递增；邮件偏好与账号知晓记录保留。
5. 解绑后通过正常需求接口新建验收需求 `REQ-20261103-0005`（ID 22）并确认，恢复 TEST worker。通知 API 查到 2 条站内通知（ID 436、438）。
6. 只读 SQL 核验：`VERIFY_EMAIL`、`CREATED`、`CONFIRM` 共 3 条 EMAIL 均为 `SKIPPED / PREFERENCE_OR_EMAIL_CHANGED`；2 条 SITE 均 `SENT`；`EMAIL_UNBOUND` 审计恰好 1 条。

线上实际执行的是“仅待验证地址”的解绑；已验证地址的原子清空、并发 SMTP 和事务回滚由双数据库及浏览器隔离用例覆盖。没有解除原账号 `ceshi006` 的邮箱；完成后已恢复该账号浏览器会话，确认邮箱仍已验证、重新验证表单保持隐藏、新解绑入口可见，并验证放弃确认不改变绑定。

没有剩余失败或规格冲突；本轮未推送、合并、创建 tag/Release，也未部署或修改正式数据库。用户可在 TEST 个人中心 → 邮件通知验收。

## 回退与证据

本次不涉及 schema 改动，应用回退应保留当前 TEST 数据：先停 worker，再使用 `retry2/images.env.before` 恢复 TEST `images.env`，只重建 API、Web、worker 到原镜像（API/worker `mail-notice-96ba96e`，Web `workflow-entry-ba5d46e`）；三者运行且健康条件满足后再重载 `iterflow-test-nginx`。不可先重载代理，也不可为应用回退恢复数据库、删除卷或操作正式项目。前两次失败实际完成了此类应用回退且没有数据库恢复。

服务器原始证据：`/opt/iterflow/upgrade-evidence/email-unbind-f879eaa/`，首次、`retry1/`、`retry2/` 和日志分别保留；本机完整输出与页面截图位于前述 deliverables 目录。仓库收录无凭据摘要及页面证据：[验收摘要](evidence/email-unbind-20261103/verification-summary.json)、[已绑定入口](evidence/email-unbind-20261103/online-bound-entry.jpg)、[解绑成功](evidence/email-unbind-20261103/online-success-desktop.jpg)。摘要中的服务器回执字段由实际 UI 输出整理，原始凭据与数据库备份未复制入仓库。
