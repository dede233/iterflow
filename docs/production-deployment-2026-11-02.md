# 2026-11-02 正式上线执行记录

## 当前状态：正式上线完成，访问已恢复

用户已授权走正式上线流程，并选择“演练通过后立即短暂维护”。先前的 Mac 锁屏阻断已解除。2026-11-02 14:21:03 +08:00 开始维护，14:25:45 完成恢复后的稳定性复核，服务器 `deployed.json` 为 BUSINESS_REOPENED/PASS。

本次数据库迁移使用短暂维护暂停提交和编辑。进入维护到最终复核完成为 282.21 秒（4 分 42 秒），这是包含故障诊断及追加复核的维护时长上界，实际入口更早已恢复，不能当作精确停机秒数。测试环境、其他站点及 Redis 保持不变，未创建 tag/Release。

## 已核对的发布基线

- GitHub/Gitee master 均为 `a1c90dd9e19925f70428d9565fce3b8eb7d06f62`，本轮再次核对无漂移。
- master [CI 41390753028](https://github.com/dede233/iterflow/actions/runs/41390753028) 八项全部通过；不以分支 CI 替代。
- 冻结离线包源码 `2c503bfb216bcd61835de7a236a454ff8d6b0c5c`，与 master 的 backend、frontend/src、deploy/mysql57、spec 产品源码一致；其后为测试修复及文档。
- 包 SHA256：`4a2d5565973cae47137408095edd47af0524b8b2c016b440ffd07a7a5af991e0`。服务端已核验包与内部 SHA256SUMS，加载的 API/Web 镜像 config 与构建证据一致。
- 升级前正式基线为 `198f831d67e8b475975915b1824d711b949fb998`、`mysql57_0006`；升级后运行产物为 `2c503bf`、`mysql57_0010`，正式地址 `https://sx-kc.xyz:8443`，项目 `iterflow-mysql57`。
- 正式目录 `/opt/iterflow/releases/iterflow-reference-display-3fe3a42`。RDS MySQL 5.7.44，24 张表；现有迁移账号权限足够，本轮没有新增 GRANT。
- 本轮初查可用磁盘 22.24 GiB、MemAvailable 734720 kB；实际切换前再次检查。

## 在线备份与真实数据隔离演练

未停止正式服务，在线备份仅用于隔离演练；最终切换仍须停写后取得新的数据库及附件一致备份。真实备份仅保存在服务器，不下载到本机，不导入测试环境。

- 备份目录：`/opt/iterflow/backups/production-a1c90dd-online-rehearsal-20261102T051318Z`。
- `database.sql`：219683 bytes；SHA256 `2f79ad3112c50a08fcb6d5f5c438f29e18b0d31faa6cce6a9875dd00a8b26329`。
- `uploads.tar`：266240 bytes；SHA256 `02b38cfa40266e09f23fa1b34798ae8f7d378534f4c0cbf61ec34c8f1fe4efec`。
- 新建 internal Docker 网络和独立 MySQL/附件卷，无对外端口；隔离副本禁用 SMTP，不连接正式 Redis。演练数据库现已停止，卷及证据保留。
- 首次恢复附件因 Python `tarfile` 的 data filter 移除属主，导致应用无法读取原 0600 文件。只在隔离附件卷内修复恢复方式：先验证归档路径及文件类型，再保留原 UID/GID/mode 恢复；未修改正式附件或原备份。原始失败保留在服务端日志。
- 隔离迁移 **PASS，9.38 秒**，`mysql57_0006 → mysql57_0010`，24 → 30 张表、73 → 91 个触发器。
- 23 张原业务表原有列逐项兼容校验、1 个附件内容校验、历史人员/状态映射、revision 变化、旧完成记录、默认未验证邮箱和空通知队列检查全部通过。
- 原正式服务配置/容器及测试环境未改变。该演练结果不等同于实际正式迁移或上线后的验收。

## 候选配置与切换检查

候选配置先写入证据目录，维护期间才安装到正式目录。数据库连接、JWT、端口、附件及 TLS 挂载、Redis 配置保持一致。API 和新增 notification-worker 使用一致的正式配置。

Brevo 使用已授权的发信身份 `iterflow-emil@luqingyao.cc.cd`，正式链接为 `https://sx-kc.xyz:8443`。直接连接 465/SSL，TLS 1.3、SMTP 认证及 NOOP 通过，**本轮没有主动发送验证邮件，未证明正式邮箱实际收件**。候选先禁用 SMTP，迁移和应用健康检查通过后已启用 API/worker，正式不设置测试收件白名单。未创建新凭据或修改网络授权。Transactional usage and plan 刷新后显示 Free plan、298 emails left、0 paused emails，但截止日期仍显示 01/11/2026，故日期准确性存在边界，不将它解释为可靠的重置时间。测试继续保留原白名单。

仅针对 8443 的维护配置先通过独立 `nginx -t`，授权后才加载。保留 80/443 站点和 8444 测试入口。维护响应为 503、Retry-After 120、no-store；切换后已恢复原 8443 配置并核验摘要一致。

切换脚本顺序：核对基线及配置摘要 → 8443 维护 → API/Web 优雅停止 → 最终数据库/附件备份及双快照停写核验 → 迁移 → 数据兼容核验及 MySQL preflight → 迁移后备份 → API/Web 健康检查 → 启用邮件及 worker → 核对隔离和挂载 → 恢复正式入口 → 公网产物核验。

迁移开始前失败可恢复原配置及应用；迁移开始后失败保持维护并检查检查点，不自动 downgrade/restore。详细恢复边界见 [升级与回退清单](collaboration-workflow-upgrade.md)。恢复备份前必须停写并判断新产生数据，不能直接用旧镜像运行新 schema。

## 正式执行结果与故障处理

- 停写后最终备份：`/opt/iterflow/backups/production-a1c90dd-final-pre-20261102T062113Z`。备份前后只读快照一致。
- 正式迁移耗时 9.38 秒，正常执行 0007–0010，未执行 seed/stamp/create_all/restore；原数据和附件严格校验及 MySQL preflight 通过。
- 迁移后、开放业务前备份：`/opt/iterflow/backups/production-a1c90dd-post-migration-20261102T062158Z`。两份备份均有受保护的 manifest/hash，不用更早的在线演练备份替代最终恢复点。
- API/Web health/ready 通过；worker 运行。三者 RestartCount 均为 0、restart 为 unless-stopped，Docker 自启动 enabled；未为了证明恢复而再次重启正式服务或整台服务器。
- 首次脚本在恢复原 Nginx 配置并 reload 后立即进行公网探测，收到了 503 而退出。迁移及所有内网健康/配置/数据/隔离检查当时已通过；入口随后正常返回 200，表现符合 Nginx reload 异步交接窗口。保留 `cutover-failure.txt`，没有重新迁移或回退数据库。追加健康/日志/挂载及隔离检查、连续三次公网 200 和页面 SHA 一致后写入成功回执；不把首次失败抹去或描述为无异常。
- 复核期间未发现 API/Web/worker 的 ERROR、Traceback 或 worker failed；无重启。正式首页加载成功，原登录会话有效，统计显示 2 条反馈、8 条需求、3 个版本、1 条发布。
- 旧需求详情、原设计/开发人员、六阶段和收起/展开可读；多人验收文案正确。个人中心未绑定邮箱账号显示未验证、输入区及同排验证码操作；未修改用户偏好/邮箱或业务内容，未创建验收用户、虚构需求或发布。
- 浏览器错误/警告日志为空。完整写入主链验收依照既有 CI、包级隔离演练和测试环境证据，未在正式环境重复制造测试数据。用户需自行验证正式邮箱后才会收到进度邮件，不继承测试邮箱验证状态、不补发历史事件。
- 运维控制文件的旧预期 SHA 随当前正式版本更新并保留原文件/历史基线；本次追加正式升级记录，测试保留规则不变。

## 证据位置

- 服务器：`/opt/iterflow/upgrade-evidence/production-a1c90dd`，含 preflight、备份回执、迁移前后校验、rehearsal.json、candidate.json、cutover.py、deployed.json 及原始失败/追加复核日志。目录内运行配置受保护，不可公开或提交仓库。
- 本地：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-02/production-deployment-a1c90dd`，含操作脚本和检查截图，不含真实数据库备份或 SMTP 凭据。
- `deployed.json`、`cutover-checkpoint.json` 均为 BUSINESS_REOPENED/PASS；原始首次失败继续保留。
