# 业务系统绑定开发与 TEST 部署（2026-11-05）

## 范围

用户授权按 [绑定方案](business-system-binding-audit-2026-11-05.md) 开发、测试并部署保留 TEST。分支 codex/business-system-bindings，不推送/合并/创建 tag 或 Release，正式 5401215/mysql57_0012 不变。

需求增加系统选择、名称展示、筛选及有效系统/模块归属校验；版本增加单一系统、创建必填、从需求继承、同系统候选、编辑/单个批量关联/迁移/集中提验/发布门禁。继续使用 RBAC/DataScope、revision CAS、原子事务与版本→需求锁序。启用系统选项只返回 id/name，不开放管理数据。反馈转新需求继承原系统/模块，归并已有需求策略不变。

PostgreSQL 0015_system_binding / MySQL mysql57_0013 仅追加可空版本 system_id、索引和外键；旧版本不回填，停用历史可读，未补齐时需人工处理。取消/已发布版本及已上线需求不能修改系统。迁移降级遇到非空绑定时拒绝丢失数据。

## 本地验证

只使用本任务新建的 PG、Redis、MySQL standard/portable 容器及新数据库；未读取仓库运行 .env。证据目录 /Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-05/business-system-bindings/。

- PostgreSQL 全量 670 PASS、1 项 S3 未配置跳过；新增真实绑定/并发/历史迁移 3 PASS。
- 前端 491 单测 PASS，类型检查及生产构建 PASS。
- 相关浏览器 53 项第二轮 51 PASS；2 项因 combobox 同名范围不明确失败，精确限定业务系统控件后 4 项新增浏览器全 PASS。其余 49 项已通过；桌面/375px 覆盖补齐与继承、必填、筛选及既有版本链。
- 契约/文档/架构/新绑定合计 34 PASS。Ruff、Mypy PASS。
- MySQL 首轮新增迁移回退发现 FK 依赖索引，调整为先删除 FK 再删除索引；业务回归各 63 PASS，迁移完整预检因 head 白名单未更新失败，已修正运行时预检并追加新列/FK检查。
- 扩展 MySQL 全量中，旧生命周期夹具缺系统（3 项）及旧迁移 head 断言已调整；portable 在重启持久性测试时官方 entrypoint 退出 139，保存失败容器/日志，同镜像同 mysqld 参数及原任务卷使用直接 mysqld 后复测，不降低重启/恢复门禁。
- MySQL standard 140 项全部通过（全量 132 PASS，修正后 5+4 项复测，含 1 项重复迁移）；portable 140 项全部通过（全量 135 PASS，4 项历史夹具复测及 1 项重启/备份恢复复测）。历史版本反射夹具保留当前 VARBINARY 类型处理；portable 重建后补回私有环境文件，镜像/参数/卷不变。
- 真实 Docker API/Web 镜像健康检查通过；首次登录/改密/反馈用例 PASS；完整受限多账号主链、并发冲突、独立验收、发布/通知及 375/390/768/1280/1440 五宽度页面回归 PASS（browser-playwright-141842.log）。旧 SELF 夹具补充系统；复测使用唯一显示名和当前版本发布记录断言，避免前次保留数据干扰。
- 8 组正常 API 绑定验收先在同一隔离 Docker 环境通过；部署数据证明程序对 MySQL 0012→0013 真实迁移 1 PASS。
- 应用冻结源码 676e9dd；后续仅测试夹具/记录修正，不改变镜像代码。所有首次失败保留，不把当前进程测试当作独立审查。
- 服务器首次预检在停服前因 BUILD_SHA 被误按 Web SHA 核对而停止。只读确认 TEST API/worker 仍 ab8bd07、Web 5401215；修正为核对 API SHA 后预检通过。原归档保留，修正包 SHA256 3184d101e35c94f0a196b6701fcd672f23ef31a74a11f5cbb3002dc4f5bdaad7。

## TEST 升级和回退边界

已于 2026-11-05 14:26:13（北京时间）完成部署。目标仅 https://sx-kc.xyz:8444，数据库 iterflow_acceptance 0012→0013。正常宝塔文件上传归档，网页终端仅短控制命令。先检查来源、残留任务、正式保护和空间；备份 TEST 数据/附件/配置，隔离恢复和迁移验证后再切换。原列全表（含会话/审计）、91 个触发器、函数、附件、SMTP/JWT 配置保留检查通过。

DDL 前失败仅在旧数据结构一致时恢复原 TEST 应用；DDL 开始后不自动降级、恢复数据库或盲目重跑迁移，保持停写并前向修复。正式环境不连接数据库、不停止或重启。在线测试使用合成账号通过正常 API，不改用户邮箱，不实际发布。

## 实际部署结果与在线验收

- TEST API/worker/Web 冻结源码 `676e9dd6b389d59c23a067e6f3223ab6b5d41934`；数据库 `mysql57_0013`。预检、备份、隔离恢复迁移、切换和验收后独立 verify 全 PASS。
- 主包 SHA256 `9cdf65653bf2eae67ce437cc281337891e7718fd87e1da5ccc8db92d049e4086`（117299200 字节），正常文件上传；控制器修正包仅修正预检基线核对，未改变冻结应用。
- 29 张表原列完整数据、会话、审计和附件切换保留。隔离演练禁用 SMTP；TEST API/worker 各自邮件配置指纹保持原值。没有恢复/降级真实数据库或自动回填历史系统。
- 正式容器/配置/公开入口指纹仍为原 `5401215`，未连接正式数据库；最终独立 verify 再次确认正式保护 PASS。
- 服务器证据：`/opt/iterflow/upgrade-evidence/system-binding-test-20261105/` 下 `preflight.json`、`backup.json`、`rehearsal.json`、`deployed.json`、`data-preserved-before-worker.json`、`verified.json`。备份位于 `/opt/iterflow/backups/system-binding-test-{pre,post-migration}-*`，具体目录以备份回执为准。
- 本地部署截图 `server-deployment-receipt.png`、`server-final-verify.png`；页面证据 `test-ui-desktop.png`、`test-ui-mobile.png`、`test-ui-legacy.png`，均在上述交付目录中。

在线以未绑定邮箱的既有合成账号 `ceshi002` 通过正常 HTTPS API 完成 6 组检查：精简系统选项、创建版本并原子关联、空系统需求显式补齐、按系统筛选、确认/集中提验/验收通过、发布检查系统项通过但其他未完成需求仍阻止发布。未实际发布、未改账号权限或邮箱。

在线限制：TEST 只有 1 个启用系统。初次检查在任何业务写入前停止并保留 `online-options-stop.json`；现有合成账号没有新增系统权限，未扩大权限或修改历史系统。跨系统关联/编辑拒绝和另一系统筛选在线未跑，已在隔离 PostgreSQL/MySQL 及本地 8 组 API 验收通过。在线结果 `online-acceptance.json` 明确记录此范围。

保留供用户验收：版本 [TEST-BIND-1105-063453](https://sx-kc.xyz:8444/#/versions/27)，需求 [REQ-20261105-0002](https://sx-kc.xyz:8444/#/requirements/33)（待发布）、[REQ-20261105-0003](https://sx-kc.xyz:8444/#/requirements/34)（待确认，已显式补齐系统）。桌面版本归属/同系统候选、旧版本未指定提示与全部候选禁选、375px 需求详情通过。旧数据保持原样，模块管理入口隐藏。

本任务本地测试资源已按名称/标签核对后清理，未清理既有 Preview 或保留 TEST。服务器本轮演练容器已停止，备份/证据保留。无推送、合并、tag/Release 或正式环境升级。等待用户 TEST 验收。

## 后续回退操作约束

当前已完成 DDL 且新增合成绑定数据，不可直接执行 Alembic downgrade 或恢复升级前数据库。优先前向修复；如必须恢复，应另行确认停写窗口、保存升级后增量并审核恢复方案。旧应用不执行新增系统门禁，因此不能把单纯换回旧镜像当作等价安全回退。原镜像、配置、升级前后备份与演练证据均保留，具体失败阶段由控制器记录，不自动破坏新数据。
