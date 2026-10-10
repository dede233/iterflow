# MySQL 5.7 全局 OFF/OFF 本地适配增量

用户于 2026-10-10 授权先在本地适配不修改 RDS 的 `innodb_large_prefix`、
`innodb_strict_mode` 全局参数。此次不操作应用服务器或远程数据库。
原交付包仍是历史测试产物，不能直接用于 OFF/OFF；本增量必须重新验证及构建。

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
新增 CI 与新包验收结果后续记录，不沿用旧包 CI PASS。

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
