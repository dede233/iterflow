# 迭程 IterFlow 上线准备与数据库回退 · 2026-11-28

本轮准备代码、制品和维护方案。正式 `8443` 的停写、迁移、授权变更、恢复及对外发送，均须在后续明确授权的维护窗口执行。保留 TEST `8444` 的服务、账号、数据库和附件继续独立。本文环境身份取自已有回执，执行前须重新核验。

## 冻结候选与环境基线

| 对象 | 证据与身份 |
| --- | --- |
| 正式最近一次切换 | 11 月 27 日上线源码 `8418c5cf14592d81121f6a4d7a4f3be1041930ed`，源码树 `8687e6062832515adc58a15aa2a3529847a60f34`，MySQL `mysql57_0027`，38 张表、119 个触发器、1 个例程。已保存旧发布镜像归档和同批库、附件及配置回执。未来本次切换以到场复核的这套正式应用和新取备份作为回退基线。 |
| TEST API 与通知 worker | 同用 `iterflow-api:mail-operations-test-1128`，从 `5a5490d87fdae0bd7c5b370d7207385eebf2ded0` 冻结，经典镜像 config ID `sha256:8347892416233acc2a58ce22df209ad51a073596efebd24a95c6230794ffe797`。原 API/Web 联合归档 SHA-256 `6673b5b09af6b926e20b7216c9bd5f4376d8a63263196a48123c42d07afe7fc9`，其中 Web 后续已加侧栏修正。 |
| TEST Web | `iterflow-web:sidebar-test-1128` 在邮件操作冻结树上叠加侧栏 CSS，树为 `2328b1d2cf72bf7a4cb88db9936694789d9fae52`，经典镜像 config ID `sha256:d199528de1798c6d5c88aacebc5f027fe6afadcfb9515b62dad8b911b4cdb876`。原 Web 归档 SHA-256 `b3a6fc9c9b54cae44e9aabf83b9d6c5f9887406ceafe1706f0b494cd5f1907d7`，11 月 28 日公开首页回执 SHA-256 `cb0706acb95b7d17fea8243b5d312e4b253375e1d7faf1c96a8b4bbebfe718df`。 |
| TEST 数据库 | 11 月 28 日邮件操作及侧栏更新的既有基线为 `mysql57_0029`，39 张表。候选继承已经进入 TEST 的抄送、软删除与制作撤回迁移。邮件投递记录、详情、手动重发及侧栏更新复用既有库结构。 |

TEST 两张镜像的 `org.opencontainers.image.revision` 均记录 Git 基点 `8418c5cf14592d81121f6a4d7a4f3be1041930ed`，用 `io.iterflow.source-tree`、源码归档、分平台 manifest/config 及逐层摘要确认实际版本。上线包须绑定待发布提交及实际八项 CI，对照两份冻结制品的运行源码、迁移、契约和静态文件，记录新增差异及相应验收。两环境须分别核验容器、端口、数据库身份、存储、代理、配置及遗留上传/构建/维护任务。产物经普通文件上传或核验主机密钥的 SSH/SFTP 传送，宝塔网页终端仅运行短控制命令。

本地证据索引位于 `2026-11-27/rd-creator-production-release/README.md` 及同目录 `transport-receipt.json`（交付根目录 `/Users/xiaweiyi/Developer/deliverables/iterflow`），`/private/tmp/iterflow-mailops-build-1128/artifact-manifest.json`、`/private/tmp/iterflow-sidebar-build-1128/build-result.json` 和 `/private/tmp/iterflow-sidebar-control-1128/public-after.json`。现有服务端回执目录为 `/opt/iterflow/upgrade-evidence/rd-creator-production-1127`、`/opt/iterflow/upgrade-evidence/mailops-test-1128/retry-r3` 和 `/opt/iterflow/upgrade-evidence/sidebar-test-1128`。应在执行准备阶段归档所用本地临时证据和镜像清单。

## 迁移与权限

| 步骤 | MySQL 5.7 | PostgreSQL | 结构及数据预期 |
| --- | --- | --- | --- |
| 起点 | `mysql57_0027` | `0029_ops_role_defaults` | 保留既有两类运营制作权限、系统及自定义角色、用户授权和历史审计。 |
| 抄送 | `mysql57_0028` | `0030_ad_production_cc` | 新增 `ops_ad_production_cc_user`，联合主键 `(ad_production_id, user_id)`，两条 `ON DELETE RESTRICT` 外键分别指向制作记录与账号，另有 `ix_ad_production_cc_user_id`。旧记录抄送名单为空。MySQL 新增 INSERT、UPDATE、DELETE 三个 `BEFORE` 触发器，强制会话外键和唯一检查启用。 |
| 软删除与撤回 | `mysql57_0029` | `0031_production_version_deletion` | `rd_version`、`ops_ad_production` 各增加可空 `deleted_at`、`deleted_by`、`delete_reason`，删除人外键指向 `sys_user(id)`，旧行三列均为空。MySQL 使用 `DATETIME(6)` 保存 UTC，PG 使用带时区字段。MySQL 替换制作表 INSERT/UPDATE 状态触发器，PG 替换 `ad_production_status`、`ck_ad_production_kind_workflow` 两个 CHECK，允许 `WITHDRAWN` 并保留种类与处理结果约束。已有版本号全局唯一、关系、附件、审计和历史均继续保留。 |

以 11 月 27 日记录的正式结构为起点，预期迁移后为 39 张表、122 个触发器、1 个例程。其中新增的三个触发器计入增量，制作表替换的两个触发器保持原名及数量。核对对象定义、外键动作、索引、触发器 `DEFINER` 和行摘要，并保留不相关的登记函数及写保护。应用门禁仍负责对象范围、权限、状态、历史前置条件、理由、CAS 及审计。PG 对照需测试相同业务规则和保留边界。 [抄送迁移](../backend/alembic/ad_production_cc_v1.py) · [删除与撤回迁移](../backend/alembic/production_version_deletion_v1.py) · [业务状态机](../spec/status-machines.md)

正式已存在数据库使用候选固定 API 镜像和已有独立迁移身份执行 `python -m app.cli.migrate`。MySQL 路线使用 `alembic-mysql.ini`，依序走 `0028`、`0029`。PG 隔离演练使用 `alembic.ini`。匹配实际目标库、服务器身份、Oracle MySQL 5.7 版本和会话配置，检查 `utf8mb4_bin`、InnoDB、UTC、严格 SQL、外键/唯一检查、binlog 条件、DDL 锁、磁盘和连接余量。DBA 核验迁移身份在目标库执行 `CREATE`、`ALTER`、`INDEX`、`REFERENCES`、`TRIGGER`、所需 DML 和元数据读取的权限，保留触发器定义者及其必要权限。用迁移身份核验完整 schema，再用实际 API、worker 的运行身份检查就绪。 [迁移入口](../backend/app/cli/migrate.py) · [MySQL 预检](../backend/app/core/mysql_preflight.py)

本批运行库授权增量只涉及 `ops_ad_production_cc_user` 的 `SELECT, INSERT, DELETE`，后两项用于增删对应抄送关系。运行身份继续用原有 `rd_version`、`ops_ad_production` 和通知、审计表权限。DBA 应先核对两服务实际身份及 `SHOW GRANTS`，按已授权维护范围在新表存在后补齐缺失的表级权限。禁止新增 `UPDATE`（抄送表）、整库授权、DDL、触发器管理或 `GRANT OPTION` 给运行身份。发现既有授权超出模板时如实记录，并按当前授权处理。已有库使用连续升级，严禁 `seed`、`stamp head`、直接建模建表或重写已发布历史。 [MySQL 手册](../deploy/mysql57/README.md) · [运行授权模板](../deploy/mysql57/runtime-grants.sql)

## 备份、隔离演练与切换门禁

1. **准备与演练。** 确认正式目标和 TEST 防护后，取得一份可证明一致的正式数据库与附件恢复点，并保存现用 API、worker、Web 镜像及配置。用新建独立数据库、附件存储、Redis、网络和入口恢复，隔绝真实 SMTP、企业微信、公共入口及生产写连接。演练要求旧正式镜像加 `0027` 基线可读，候选严格执行 `0027 → 0028 → 0029` 后可用，旧正式 API 的 MySQL 就绪预检拒绝 `0029`。既有保留 TEST 不作为恢复目标。MySQL standard/portable 两种配置、PG 迁移、空新语义降级再升级及有受保护数据时拒绝降级均须在隔离环境验证。用同一冻结候选验证真实主链、两类制作、CC 增删及移除后旧链接拒绝、删除与撤回、权限/CAS、工单/公告与附件读取，以及邮件重发和租约副作用。
2. **停写与最后备份。** 关闭正式业务写入口，停 API、通知 worker、其他定时器/直连写入者及在途事务，记录 SMTP/企业微信发送与租约边界。保存 `0027` SQL、附件归档（本地存储）或对应的可验证引用和对象恢复点（S3）、旧镜像归档、Compose、每服务环境配置、TLS、代理、启动与恢复配置、授权及触发器元数据。记录库身份、Alembic、容量及 UTC 时间，校验文件完整性和 SHA-256，受保护异地留存。库备份包含例程、触发器、完整数据和二进制字段，附件清单记录路径/键、大小、摘要与必要元数据。任一备份失败、期间出现写入、身份或校验有差异时禁止切换。日志及回执不公开 SMTP、JWT、数据库或对象存储密钥。
3. **核对迁移前后。** 在业务写入及 worker 均暂停的窗口，比较最终备份和迁移后的全部现有表行数与按主键稳定序列化的全行摘要。只允许 `alembic_version` 的目标值、预期追加 schema 和经证实的物理对象定义差异。旧业务列、原有关系、角色/账号/会话、公告/已读、审计、站内通知、投递队列和附件元数据须保持一致。新抄送表应为空，旧行新增删除字段应为空。逐一校验附件文件/对象及配置指纹，验证约束、例程、触发器、授权和实际运行身份。记录备份路径、运行日志、镜像身份、结构差异、摘要及两环境保护结果。
4. **受控恢复。** 保持外部写入口和 worker 关闭，先启 API 并核对 `/health`、`/ready` 及登录门禁，随后启动 Web 并校验入口、关键静态文件和已授权的只读业务数据。核对 TEST 身份、入口和基线后，经授权恢复正式访问及通知 worker，记录各自开始时间和投递状态。正式验收以读取与健康检查为主，写入型验收使用隔离环境或按明确批准的范围执行。正式解冻后监测错误率、数据库拒绝、通知异常及两环境入口，并保留上线后恢复点。

隔离演练及切换前必须以实际候选 SHA 核验 `backend`、`frontend`、`docker_smoke`、`s3`、`browser_smoke`、`backup_restore` 和 `mysql57` standard/portable 八项，另核对 TEST 验收、镜像内容同源、空间、备份和授权。记录首次失败、修正及重跑依据。缺少任一必需证据时保持现有正式版本。 [CI 定义](../.github/workflows/ci.yml) · [当前工作流](agent-workflow.md)

## 分阶段回退

| 阶段 | 可执行条件与处置 |
| --- | --- |
| 尚未执行第一条 DDL | 退出维护前复核库仍为 `0027`、结构和数据指纹、原镜像/配置及原入口。若仅做了暂存、停服务或代理切换，用受保护备份中的原配置和原镜像恢复正式；核对运行身份及通知恢复时点。出现未知写入或状态漂移则先保留现场。 |
| DDL 已开始，任一步失败或结果未知 | 保持停写，隔离 worker 和外发，保留失败备份、日志以及实际 `alembic_version`、表、列、FK、触发器、`DEFINER` 和授权证据。MySQL DDL 可隐式提交，特别是制作触发器 DROP 与 CREATE 之间；同一版本号可以对应部分完成的结构。禁止启动旧应用、执行盲目重试、`stamp`、自动降级或整库恢复。DBA 以实际结构在隔离副本重建失败状态，验证有证据的前向修复，经明确授权后继续。 |
| 完成 `0029`，尚未对外开放且无切换后写入或发送 | 优先修复应用或切到已演练且明确兼容 `0029` 的整套应用。旧正式 API/worker 的就绪门禁要求 `0027`。确需恢复旧库时，必须有切换前已验证的一致备份、停写期间无增量和外发的证据、恢复演练及独立授权。保留当前现场副本，库、附件、应用、配置与权限一同对齐，再复验数据和入口。 |
| 开放后或存在新语义/投递 | 先按影响范围停止新增写入和 worker，保留现状备份、业务增量及投递证据。已有抄送、软删除、撤回、已发或已排队重发时，保留 `0029` 及原语义，走兼容应用回退或前向修复。灾难恢复必须取得专项授权，先确认数据损失点、可重放业务增量、附件一致性、审计和外发对账。任何降级或恢复均不得删除或改写真实历史以满足旧应用。 |

降级演练只在隔离停写库执行。`0029` 在版本或制作任一删除字段非空，或制作存在 `WITHDRAWN` 时拒绝降级。`0028` 在抄送表存在任意关系时拒绝降级。跨两步降级即使第二步拒绝，MySQL 也可能已经提交第一步并改变结构；在任何 DDL 前一次性检查两个版本的保护条件，并检查删除、撤回、抄送审计和通知。现有 CC 表为空也可能存在已移除抄送人及其历史通知。PG 当前降级函数在读取保护条件前加排他表锁，仍按停写窗口演练并保留备份。 [软删除降级验证](../backend/tests/soft_deletion_migration_acceptance.py) · [抄送降级验证](../backend/tests/ad_production_cc_acceptance.py)

## 邮件、抄送与既有通知

- 制作抄送加入、状态变化和撤回会在原业务事务中写站内通知。撤回通知接收人和当前抄送人，单次按人去重；移除后停止该记录的抄送提醒并收回仅由抄送产生的阅读权限。软删除隐藏相关通知入口并保留原行、已读与审计。恢复应核对现有抄送、相关通知和附件访问状态，保留历史。 [制作通知](../backend/app/services/ad_production_notifications.py) · [通知可见性](../backend/app/services/notification_service.py)
- 邮件投递记录与重发使用现有事件、投递行及审计。手动重发仅限启用的内置 `SUPER_ADMIN`，当前状态须为 `SENT` 或 `FAILED`，仍校验原事件权限、验证状态、收件地址和偏好。重发复用同一投递行、重新排队并记录 `DELIVERY_RESEND`。当前 worker 按重发审计生成相应 `Message-ID`，普通发送及旧接口已排队重试保持原策略。回退 worker 若不理解该历史，可能产生不同 Message-ID 或重复交付，故必须先核对兼容性。 [重发服务](../backend/app/services/mail_delivery_monitor_service.py) · [投递服务](../backend/app/services/delivery_service.py)
- 维护前后按投递 ID、状态、次数、租约、审计及可取得的 SMTP/企业微信回执对账。`SENDING` 或 `UNCERTAIN` 可能已经交给外部系统，暂停 worker、恢复数据库或撤销应用均无法撤回已交付消息。避免人为重置状态、批量重发、删除队列或删除审计。出现无法对账的在途投递时保留凭证并处理其状态后再开放相应发送，已有的 SITE 通知及 SMTP/JWT 逐服务配置按现场核对保留。
