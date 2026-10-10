# MySQL 5.7 全局 OFF/OFF 本地适配增量

用户于 2026-10-10 授权先在本地适配不修改 RDS 的 `innodb_large_prefix`、
`innodb_strict_mode` 全局参数。此次不操作应用服务器或远程数据库。
原交付包仍是历史测试产物，不能直接用于 OFF/OFF；本增量必须重新验证及构建。

分支 `codex/mysql-57-adaptation`，工作目录
`/Users/xiaweiyi/Developer/worktrees/iterflow/mysql-57-adaptation`；master 基线
`a38081af9097f691c8289e9301951a0360ea0af7`。没有合并/push master、创建 tag/Release 或改写历史。

本增量主要修改文件：

| 范围 | 文件 |
| --- | --- |
| 连接与类型 | backend/app/core/database.py、db_types.py、mysql_preflight.py；models/entities.py；cli/migrate.py |
| 迁移与数据库保护 | backend/alembic/mysql_file_keys.py；mysql_versions/mysql57_0001.py、mysql57_0002_portable_file_keys.py |
| 实测 | backend/tests_mysql57/test_acceptance.py；tools/mysql57-portable/；run-mysql-tests.py；smoke-mysql-package.py |
| CI 与部署 | .github/workflows/ci.yml；deploy/mysql57/README.md、compose.yml、runtime-grants.sql |
| 记录 | docs/evidence/mysql57-portable/、本报告、原交付记录的历史范围提示、.gitignore |

完整修改清单以 `git diff --name-status a38081af9097f691c8289e9301951a0360ea0af7 HEAD`
为准；该命令同时包含原始 MySQL 适配。已发布 PG 迁移、当前/历史契约与 frontend/src 不变。

## 实现

- 所有 API、迁移、seed、应用预检连接设置 SESSION innodb_strict_mode=ON，同时保持严格
  SQL mode、UTC、READ COMMITTED、foreign_key_checks=1、unique_checks=1。
  不执行 SET GLOBAL。无法启用会话严格模式或会话配置不正确时预检失败。
- 新增 `mysql57_0002` 正式迁移。未发布的 MySQL 0001 初始化入口在 large_prefix=OFF 时
  直接建立完整替代约束，避免先创建超限索引；原显式 DDL 快照保留。
  已有本地 ON 版 0001 可停写后通过 0002 升级，原完整唯一索引在一次 ALTER 内被等价约束替换。
  已发布 PostgreSQL 迁移、契约、tag、Release 不改变；不 create_all/stamp。
- 文件键仍接受原 500 字符、最多 2000 UTF-8 字节，并保留大小写、尾空格和完整键的唯一语义。
  物理 VARBINARY(2004) 多出的 4 字节仅供数据库 guard 检出超长输入，不能成为合法键。
  复查已复现空 SQL mode 的原始 SQL 在触发器前截断 501 个四字节字符的问题；现由 guard 拒绝。
- 内部索引表 `iterflow_file_key_node` 将完整二进制键按 512 字节分段；
  UNIQUE(parent_id, segment) 的长度为 520 字节，小于 767 字节限制。
  根节点表示合法的空键；有确定路径后以文件 `storage_key_leaf_id UNIQUE + FK` 约束唯一文件。
  不使用哈希、不对完整键做前缀唯一性判断。不同完整键可以共享任意前缀。
- BEFORE INSERT/UPDATE 触发器在原文件值域 guard 后调用 DEFINER 登记函数，
  强制派生 leaf，拒绝直接修改 leaf。函数用原生唯一索引、事务行锁与 current read 登记节点，
  对过期 REPEATABLE READ 快照仍有效。节点及文件写入属于同一 InnoDB 事务，无内部 commit。
- 节点的 parent/segment/id 不可变、禁止 DELETE、拒绝关闭外键或唯一检查后 INSERT/UPDATE。
  删除文件释放对应文件唯一性，登记节点保留可复用；新增空间消耗最多 4 节点/历史长键，
  当前应用生成的短 ASCII 键一般 1 节点。它是内部物理索引，不是新增业务实体或 API。
- 迁移后的结构为 21 业务表 + 1 内部登记表 + Alembic 表，68 个 guard/派生触发器和 1 个函数。
  推荐运行账号只拥有业务表 DML、Alembic/登记表 SELECT，无登记表写权限或函数 EXECUTE。
  实测运行账号上传由 DEFINER 写入登记表。用户已接受远程继续使用现有高权限账号的例外；
  不把该例外记为最小权限通过，也不保证抵御该账号 DROP/TRUNCATE 保护对象。
- 备份加入 --routines，连同节点、leaf、触发器及附件保存。MySQL 5.7 的备份身份需要
  mysql.proc SELECT；该权限不授予应用运行身份。必须保留函数/触发器 DEFINER 身份与权限。

## 关系保护与 PostgreSQL 的保证差异

本增量延续已验证的 MySQL 单一关系事实方案：两个条件唯一索引由 STORED 生成列
`IF(is_primary=1,feedback_id,NULL)` / `IF(active=1,requirement_id,NULL)` 加 UNIQUE 实施；
主需求和当前版本 API 指针由关系派生，不能通过直接 SQL 写第二份指针制造背离。
合法历史行映射为 NULL，可以共存；FK、原 63 个值域/写保护 guard 及新增 5 个文件键 guard
拒绝非法关系、枚举和禁用检查后的写入。不是把 PG 提交时触发器机械改为 MySQL 行触发器，
也不依赖 Service 的 commit 前检查替代数据库保护。

PostgreSQL 保留存储指针与提交时延迟核对；MySQL 使用派生指针和即时唯一/FK约束，
物理表示与检查时点不同，已提交关系一致性、历史保留及事务原子性没有降低。
直接 SQL 写旧指针列在 MySQL 被拒绝；直接 SQL 的操作顺序必须符合即时约束。
API、领域实体关系、状态迁移、revision CAS 与发布语义不变，15 步主链及并发/回滚实测通过。
MySQL DDL 不具备 PG 的事务回滚保证：迁移失败必须停下保留现场；已有 0001 只允许停写升级。
详细原方案及失败候选证据见 [原关系保护交付记录](mysql57-delivery.md#关系一致性保证与-postgresql-差异)。

## 本地环境和命令

Mac arm64，独立 `colima-iterflow-mysql57` x86_64 QEMU TCG VM（2 CPU / 3 GiB）。
新容器 `iterflow-mysql57-portable-db`、端口 127.0.0.1:57358、新命名卷；不会重建已有 57357
数据库或本地 API/Web/Preview。Compose 固定 linux/amd64 Oracle MySQL 5.7.44，启用 binlog，
实际 VERSION() 为 5.7.44-log；全局两参数 OFF、SQL mode 为空、时区 +08:00。
应用会话严格模式 ON、严格 SQL mode 与 UTC；重启后继续核实全局 OFF/OFF。
测试仅创建随机前缀的专用库和测试附件；原 .env 不覆盖，测试秘密不进入报告或包。

```bash
cd /Users/xiaweiyi/Developer/worktrees/iterflow/mysql-57-adaptation
docker --context colima-iterflow-mysql57 compose --env-file tools/mysql57-proof/.env \
  -f tools/mysql57-portable/compose.yml up -d --wait
.venv/bin/python -m pytest -q tools/mysql57-portable/test_file_keys.py
DOCKER_CONTEXT=colima-iterflow-mysql57 .venv/bin/python tools/run-mysql-tests.py \
  --portable -q --tb=short -W error::DeprecationWarning
# 同时验证保留的 ON 配置；原专用 proof 服务须已启动。
DOCKER_CONTEXT=colima-iterflow-mysql57 .venv/bin/python tools/run-mysql-tests.py \
  -q --tb=short -W error::DeprecationWarning
```

不要同时运行会重启同一测试容器的两次测试。CI 为两种参数配置设独立 runner，保留原六项门禁。
恢复演练只在第二个新测试库和第二个测试附件目录/卷中进行。
部署备份使用包内 dc.sh 的 --routines client 命令；真实库/存储的恢复未授权。

## 结果与 Fresh Self-Review

最小真实数据库证明 3 passed；全局 OFF/OFF 完整业务验收 48 passed / 0 skipped。
覆盖合法键边界、不同长键共用前缀、大小写/尾空格、并发重复、旧快照、修改重复、
禁止篡改、501 字符拒绝、异常回滚，以及原主链、CAS、RBAC、DataScope、通知、审计、
文件权限、三次重启和隔离恢复。PostgreSQL + 实际独立 S3：376 passed / 0 skipped；
PG Alembic upgrade/check、Ruff/Mypy、前端 320 tests、构建、契约类型及 bundle 门禁通过。
ON 配置复跑 48 passed / 0 skipped；关系证明复跑 17 passed。
最终预检/文件/低权限/严格会话/恢复重点回归 7 passed，恢复后新增文件上传与删除另测 1 passed。
源代码 a147f4cf8da002a55097f6b58d2261d740d9e2bc 的八项 CI 全 PASS：
[run 38024618587](https://github.com/dede233/iterflow/actions/runs/38024618587)。
两种 MySQL 配置各 48 passed / 0 skipped，且分别通过实际 amd64 镜像启动、主链、重启、
备份恢复与恢复后函数写入。原六项门禁保留，浏览器 161 passed；后端 job 的 S3 skip
由独立 s3 job 实际执行，不能把该单 job 记为零跳过。
新离线包的本地验收结果另行记录，不沿用旧包 PASS。

新包本地 smoke 可用 `--api-port 57430 --web-port 57480`，恢复使用相邻的 57431/57481。
脚本先核实四个端口可用，冲突即在创建测试库之前退出；实测拒绝已占用的 57300，
保留原本地 API/Web。该工具增量经 Ruff、编译和 Fresh Self-Review。

Fresh Self-Review 为同一 Agent 的重新审查，不能称为 independent review。
确认完整键没有哈希/前缀碰撞问题，旧快照用 current read 防绕过，函数不拆事务；
先验证最小工程再接迁移；文件 leaf 不可任意填写，节点不可篡改，函数及触发器恢复不能遗漏。
复查发现并修复 permissive SQL 的超长截断问题，首次失败保存在
`docs/evidence/mysql57-portable/first-longkey-boundary-failure.txt`。
最初两个测试配置修复：binlog 使 VERSION() 添加 -log（错误精确断言修正）；
Alembic 会在初始迁移前创建空 alembic_version（仅迁移内部允许该空表，不放宽外部空库预检）。
无核心领域规格冲突，历史关系、revision CAS、发布原子性、Release 语义和 API 保持。

本地通过不等于远程通过。新方案仍要求目标库 utf8mb4/utf8mb4_bin、InnoDB/Barracuda、
允许所需 trigger/function，且 binlog 开启时信任函数创建者；后续在目标环境验证备份权限。
已观察远程字符集/排序规则尚不符合，但本次没有修改或连接该远程环境。

证据目录：`docs/evidence/mysql57-portable/`；部署模板说明：`deploy/mysql57/README.md`。

## 新 linux/amd64 离线包

- 镜像与部署模板冻结源：`a147f4cf8da002a55097f6b58d2261d740d9e2bc`。
- 实际本地包验收工具：`e5f6771d211f7670ac9e74b2e00d30b4e7a3688c`。该增量仅改测试端口和文档；
  backend/frontend/deploy/mysql57 三个构建输入 tree 与包源相同。
- 工具增量的八项 CI 全 PASS：[run 38025118713](https://github.com/dede233/iterflow/actions/runs/38025118713)。
- 离线 images.tar 加载到独立 x86_64 VM 后实际运行：正式空库迁移与 seed、低权限账号、
  15 步主链、旧 revision 409、通知/审计/文件权限、三次重启、第二个新库和附件卷恢复、
  恢复后新文件上传/下载/删除、68 guards 与再备份，全 PASS。全局仍 OFF/OFF。
- 完整 VERSION() 为 5.7.44-log，见 local-test-environment.json；verification.json 中
  mysql_version 记录产品基础版本 5.7.44。remote_verified=false。
- 本轮临时包测试库、账号及卷已清理；原 API/Web/Redis、PostgreSQL、Preview 保持健康。

包目录：`/Users/xiaweiyi/Developer/backups/iterflow/mysql57-package/2026-10-10/iterflow-mysql57-a147f4c-portable-linux-amd64`。
离线压缩包同名 `.tar.gz`，校验值见同目录 `.tar.gz.sha256`；包内 `SHA256SUMS` 校验所有有效载荷。

| 镜像 tag | 镜像 ID（全部 linux/amd64） |
| --- | --- |
| `iterflow-api:mysql57-a147f4cf8da0` | `sha256:423e3a26e4b45860a3e57e36e2526d49e28e22865833f28067e8b6f2e5a9d8c8` |
| `iterflow-web:mysql57-a147f4cf8da0` | `sha256:e5319f7ddc3c7aad32d4ab8bd12b0e9714e7ffc4eaea66d66262b732bbcf34af` |
| `iterflow-mysql57-redis:8.2.2-amd64` | `sha256:3f835dae62fe5012baf5a768293967c93bc09cf9e848d415351dfba04ee87537` |
| `iterflow-mysql57-client:5.7.44-amd64` | `sha256:dab0a802b44617303694fb17d166501de279c3031ddeb28c56ecf7fcab5ef0da` |

本地复现新包验收（保留已有页面）：

```bash
DOCKER_CONTEXT=colima-iterflow-mysql57 .venv/bin/python tools/smoke-mysql-package.py \
  --portable --api-port 57430 --web-port 57480 \
  --bundle /Users/xiaweiyi/Developer/backups/iterflow/mysql57-package/2026-10-10/iterflow-mysql57-a147f4c-portable-linux-amd64
```

正式启动、迁移、备份及隔离恢复命令见包内 README.md；本轮没有远程执行这些命令。
包只含四镜像、部署/空白配置模板、校验清单和验证记录，不含测试 dump、附件或密码/Token/JWT_SECRET 值。

## 后续部署条件与剩余门禁

本地适配与包准备通过，可以进入部署前核实；不能据此宣称远程适配完成或可以上线。
本次没有连接远程库、操作服务器或切换网站。两个全局参数无需作为本次方案的必改项；
目标库仍需满足 utf8mb4/utf8mb4_bin、会话严格模式、创建函数/触发器及保留 DEFINER 的条件。

后续还须在已授权的目标环境：确认空库与字符集/排序规则；用新包执行只读预检并核实
迁移/备份权限、会话设置及函数创建条件；确定站点域名、HTTPS、反向代理、ALLOWED_HOSTS/CORS
和备份位置；由用户在受保护文件填写生产专用秘密；正式迁移后仅 seed 新管理员，
不导入任何测试账号或数据；完成实际远程主链、权限、附件、重启与备份验收。
现有高权限 iterflow 账号是用户接受的例外，仍需保留保护对象及 DEFINER，不将其称为最小权限部署。

压缩包最终 SHA256：`b458f3abc8e842e8d0a0e47fd449cf30b503781e427bc6b5afd68878125dcf99`（276513274 bytes）。
包内 LOCAL_VALIDATION.md 不含自身压缩包 hash，避免自引用；以包外校验文件为准。
