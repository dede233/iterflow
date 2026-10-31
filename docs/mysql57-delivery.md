# IterFlow MySQL 5.7 适配交付记录

2026-10-10 后续增量：用户授权保持两个 InnoDB 全局参数 OFF，另行本地适配。
以下为原包历史交付事实；新包及验证以 [OFF/OFF 增量记录](mysql57-portable-parameters.md) 为准，
不能把原包或原 CI PASS 当作新增实现已通过的证据。

本次仅完成独立本地环境适配及部署包准备。没有连接远程 MySQL、操作服务器、切换网站、
修改 Preview、合并/push master、创建 tag/Release 或改写历史。
本地必要门禁和离线包验收全部通过，可以进入后续部署准备；远程兼容性仍需另行核实。

## 分支与不可变基线

- 分支：`codex/mysql-57-adaptation`。
- 工作目录：`/Users/xiaweiyi/Developer/worktrees/iterflow/mysql-57-adaptation`。
- 起点 master：`a38081af9097f691c8289e9301951a0360ea0af7`；主仓库工作区保持干净。
- 镜像/部署模板源：`e319fd700020af2a9c32daf00eb895116e456b43`。
- 最终包验收代码：`d0c37166ebb94117d32acece9e8ab29e496f7fba`。
- 包源之后只调整隔离恢复测试工具、imports 与交付证据；backend/frontend/deploy/mysql57
  三个构建输入 tree 不变。最终交付 commit 由分支 HEAD / Git 日志及最终回复给出。

## 实现与文件范围

| 范围 | 主要文件 | 行为 |
| --- | --- | --- |
| 驱动与类型 | backend/pyproject.toml、requirements.lock、app/core/db_types.py、models/entities.py | 固定 PyMySQL，JSON、UTC DATETIME(6)，自然标识精确比较；保留 PG 分支 |
| 迁移与预检 | backend/alembic-mysql.ini、alembic/mysql_versions/mysql57_0001.py、app/cli/migrate.py、app/core/mysql_preflight.py、app/cli/mysql_preflight.py | 独立显式空库迁移，21 业务表；不 create_all/stamp；PG 历史不改 |
| 关系与事务 | models/entities.py、repositories/base.py、services/feedback_service.py、services/version_service.py | 单一关联事实、revision CAS、锁定发布候选并核对行数，事务回滚 |
| 会话与错误 | app/core/database.py、app/core/readiness.py | UTC、READ COMMITTED、严格模式；约束/死锁/锁超时映射 409；运行账号 readiness |
| 实测与 CI | tools/mysql57-proof/、backend/tests_mysql57/、tools/run-mysql-tests.py、.github/workflows/ci.yml | 真实 5.7.44 零跳过门禁、原六项 CI 保留 |
| 部署包 | deploy/mysql57/、tools/build-mysql-package.py、tools/smoke-mysql-package.py、Dockerfile/.dockerignore | Git 冻结源构建 amd64，外部数据库、分离账号、维护重启、备份与隔离恢复验收 |

完整修改清单：`git diff --name-status a38081af9097f691c8289e9301951a0360ea0af7 HEAD`。
`spec/`、`frontend/src/`、`backend/alembic/versions/` 无差异；API 仍为当前 1.8.1 开发基线。
没有新核心实体、角色、permission 或业务状态；新数据库迁移链仅实施同一领域模型的 MySQL 约束。

## 关系一致性保证与 PostgreSQL 差异

| 保障 | PostgreSQL 原路径 | MySQL 5.7 路径 |
| --- | --- | --- |
| 一个反馈最多一个主需求 | 条件唯一索引 + 存储指针的提交时延迟核对 | IF(is_primary=1,feedback_id,NULL) STORED + UNIQUE；主指针从关系派生 |
| 一个需求最多一个有效版本 | 条件唯一索引 + 存储指针的提交时延迟核对 | IF(active=1,requirement_id,NULL) STORED + UNIQUE；当前版本从关系派生 |
| 指针与关系一致 | 两份事实在 commit 时一致 | 单一关系事实，没有第二份可写列可背离；直接 SQL 写旧列失败 |
| 历史关系 | false 行不进入条件唯一键 | false 映射 NULL，合法历史可共存 |
| 实体存在性 | FK | FK；关联实体删除用 RESTRICT，更严格保留历史 |
| Boolean/枚举 | CHECK | BEFORE INSERT/UPDATE guard 执行，不能依赖 5.7 忽略的 CHECK |
| 防关闭检查绕过 | PG 数据库约束 | 63 个 INSERT/UPDATE/DELETE guard 拒绝 foreign_key_checks/unique_checks=0 写入 |
| 转需求/迁版/发布原子性 | Service 事务 + 数据库约束 | 同一 Service 事务 + InnoDB/FK/唯一键/guard；外部不见中间步骤，异常全回滚 |
| 旧 revision | WHERE revision，409，成功 +1 | 同样 CAS；不会自动重放业务写入 |

即时镜像 guard 的普通 SELECT 被实测旧快照绕过；加 FOR UPDATE 又使合法写入触发 MySQL 1442。
这些失败方案没有用于应用。MySQL 不模拟 PG 提交时触发器，也没有以 commit 前 Service 检查
代替数据库保护。逻辑核心实体关系和 API 指针语义保持；物理存储与检查时点不同，已提交关系
保证未降低。领域状态迁移仍由原 Service 集中执行，DB guard 保护值域。

运行账号必须仅有 21 表 DML 和 Alembic SELECT，不能 DROP/TRUNCATE/改变 trigger。
这与 PG 同样依赖管理员不破坏 schema；迁移/DBA 权限不属于不可信业务账号。
触发器 DEFINER 账号必须保留。MySQL DDL 非事务，初始化失败停下保留现场，不能 stamp/盲目续跑。

## 验证结果

本地 Oracle MySQL Community 5.7.44，新库、新卷、新账号和测试附件；没有导入旧环境账号或数据。
Mac arm64 使用独立 `colima-iterflow-mysql57` x86_64 QEMU TCG VM（2 CPU/3 GiB），
Compose 显式 linux/amd64。旧 ARM VM 的 amd64 用户态模拟曾退出 139；失败保留，未宣称修复。

- 最小数据库保护证明：17 passed / 0 skipped。
- 真实 MySQL 应用验收：43 passed / 0 skipped；包括 15 步主链、登录/改密/refresh/logout、
  RBAC/DataScope、合并反馈、版本历史、CAS、并发关联/转换/迁版/发布、全写入后异常回滚、
  Release/通知/审计、系统/模块、中文/日期/ISO 时间、文件授权、真实死锁/锁超时。
- MySQL 重启三次、隔离数据库/附件恢复、恢复后 63 guard 和重新备份：PASS。
- PostgreSQL 完整后端回归：375 passed / 1 skipped；该 skip 是真实 S3，单独真实 S3 CI 覆盖。
  PG-only：37 passed / 0 skipped，历史正式 Alembic upgrade/check PASS。
- 前端 47 文件 / 320 tests、构建、契约类型、bundle、dev/prod audit：PASS。
- Python hash 锁安装、pip check、prod/dev audit、Ruff/Mypy/编译、MySQL runtime OpenAPI parity：PASS。
- 最终离线包真实启动、15 步主链、三次重启、低权限运行、备份/第二个独立库与附件卷恢复、
  恢复后校验/再备份：PASS。
- 验收代码 d0c3716 的七项 CI 全 PASS：
  https://github.com/dede233/iterflow/actions/runs/37967917344 。
  backend/frontend/docker_smoke/browser_smoke/s3/backup_restore/mysql57 全部成功。
  本交付记录 commit 的 CI 结果以分支最新 run 和最终回复为准；构建输入与已验收源相同。

初次失败与修复、同一 Agent 的 Fresh Self-Review 见 `mysql57-adaptation-execution.md`。
没有把 Fresh Self-Review 称为独立审查；没有跳过必要数据库测试或忽略失败。

## 本地复现命令

详细环境建立和安全范围见 `mysql57-local-validation.md`。本工作目录已有随机私密配置，
不要覆盖；在新的工作目录才运行 init-mysql-test-env.py。测试 runner 拒绝非本地地址/版本，
独立库缺失即失败。

```bash
cd /Users/xiaweiyi/Developer/worktrees/iterflow/mysql-57-adaptation
docker --context colima-iterflow-mysql57 compose -f tools/mysql57-proof/compose.yml up -d --wait db
docker --context colima compose -f tools/mysql57-proof/compose.yml up -d --wait redis postgres
DOCKER_CONTEXT=colima-iterflow-mysql57 .venv/bin/python -m pytest -q tools/mysql57-proof/test_proof.py
DOCKER_CONTEXT=colima-iterflow-mysql57 .venv/bin/python tools/run-mysql-tests.py -q --tb=short -W error::DeprecationWarning
```

包命令在 `deploy/mysql57/README.md` 和包内 README.md；初始化流程为：
`mysql_preflight --empty → app.cli.migrate → mysql_preflight → app.cli.seed → up --wait`。
通过正式独立 Alembic 初始化新空库，seed 仅基础权限/角色和新管理员，首次登录改密。
备份为暂停写入后的 mysqldump + 只读附件 tar；恢复只允许新隔离库/附件卷。
本地测试可用以下命令再次自动演练迁移、15 步链路、三次重启和包内备份/隔离恢复：

```bash
DOCKER_CONTEXT=colima-iterflow-mysql57 .venv/bin/python tools/smoke-mysql-package.py \
  --bundle /Users/xiaweiyi/Developer/backups/iterflow/mysql57-package/2026-10-10/iterflow-mysql57-e319fd7-linux-amd64
```

该命令会新建随机测试库、账号和卷，完成后仅清理它们；不连接远程或真实存储。

## 包、镜像与校验

最终包：
`/Users/xiaweiyi/Developer/backups/iterflow/mysql57-package/2026-10-10/iterflow-mysql57-e319fd7-linux-amd64.tar.gz`

SHA256：`3700531f5d77b0693a15bf707d6084eff59155982d883c673594f5437ee637b7`。
大小：276,506,214 bytes（约 263.7 MiB）。
同目录 `.tar.gz.sha256` 为包外校验；包内 `SHA256SUMS` 已逐文件复核，最终 tar inventory 已复核。
`manifest.json` 记录源 commit / 四镜像；`verification.json` 记录实际离线镜像验收，
`ci-validation.json` 记录 d0c3716 七项 CI。对应 Git 证据在 docs/evidence/mysql57/package-*.json。

| linux/amd64 镜像 | Image ID |
| --- | --- |
| `iterflow-api:mysql57-e319fd700020` | `sha256:94c2d74d13915e753978467ccb6d0a98776fe2dd9f00c969da83be76f6fa8711` |
| `iterflow-web:mysql57-e319fd700020` | `sha256:d079a33f255cc1f70bcdd29dc83ad6508500df00a62c6dddd39c91fd9109bec3` |
| `iterflow-mysql57-redis:8.2.2-amd64` | `sha256:3f835dae62fe5012baf5a768293967c93bc09cf9e848d415351dfba04ee87537` |
| `iterflow-mysql57-client:5.7.44-amd64` | `sha256:dab0a802b44617303694fb17d166501de279c3031ddeb28c56ecf7fcab5ef0da` |

离线包不启动 MySQL 服务器，含 API/Web/Redis/5.7.44 客户端四个 linux/amd64 镜像。
不含真实 .env/cnf/CA、数据库 dump、测试内容、账号密码、Token 或 JWT_SECRET 值；配置模板空白。

## 后续部署条件与未验证范围

本地验证不代表远程兼容性或已上线。下一步仍须用户另行授权服务器/远程库操作，并提供：

1. 远程 VERSION()/version_comment、具体 5.7 patch/vendor；该实例字符集/collation/InnoDB/
   Barracuda/large_prefix/strict、binlog/trigger 条件、空间/连接额度。
2. 全新空 database、地址/端口、迁移和 runtime 独立账号及授权；保留 DEFINER。
3. TLS 策略、CA/主机名校验、网络路由与服务器 IP；真实密码由用户写受保护配置文件。
4. Linux amd64 Docker/Compose 版本、部署目录/域名/HTTPS 反向代理、备份存储与维护窗口。

未验证远程 patch/vendor、远程 TLS/账号/网络、服务器资源与生产负载。没有 PostgreSQL→MySQL
存量数据迁移；本次只支持全新空库。现有 PostgreSQL/Redis/API/Web/Cloudflare Preview 保持。
必要门禁通过后可进入后续部署准备；远程条件核实与授权前不能直接上线。
