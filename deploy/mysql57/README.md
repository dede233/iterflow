# 迭程 IterFlow：MySQL 5.7 空库部署包

本包用于 Linux amd64 与全新空库。仅在本地 Oracle MySQL 5.7.44 和 GitHub Linux amd64
测试过；远程版本、供应商、TLS、网络和权限未核实。当前未操作服务器/远程数据库。
API 仍为 1.8.1 开发基线，本适配分支不是新的正式 tag/Release。

包含 API、Web、Redis 与 MySQL 5.7.44 客户端镜像；Compose 不启动数据库服务器。
数据库必须由管理员单独提供。API 使用低权限账号，迁移/seed 使用另一个受限账号。
MySQL 双指针改为关系事实派生：API 字段不变，数据库生成列唯一键 + 外键 + 68 个写保护
触发器保证基数、布尔/枚举及禁用检查绕过；历史关系保留。PostgreSQL 原迁移与路径保留。

## 部署前必须确认

- 目标确为 Oracle MySQL 5.7，具体 patch/vendor；不能用 MariaDB 或未经验证版本代替已测 5.7.44。
- 新库完全空（没有表/视图），默认 utf8mb4 / utf8mb4_bin；InnoDB、Barracuda。
  全局 innodb_large_prefix / innodb_strict_mode 可为 OFF；应用和迁移连接必须成功设置
  SESSION innodb_strict_mode=ON。空间、网络、端口和连接额度足够。
- 迁移账号具有目标库 CREATE/ALTER/INDEX/REFERENCES/TRIGGER/CREATE ROUTINE/EXECUTE、DML、
  读 schema 元数据权限；binary logging 开启时由 DBA 确认创建 trigger/function 的能力，
  本路径预检要求 log_bin_trust_function_creators=ON。不要自行授予运行账号 SUPER。
- 推荐运行账号只拥有 `runtime-grants.sql` 的 21 业务表 DML、Alembic 与键登记表 SELECT，
  没有 DDL/TRIGGER/GRANT/管理权限或其他继承授权。用户已明确接受此次使用现有高权限
  iterflow 账号的例外；它可删除数据库保护对象，不属于最小权限验证通过。
- 保留触发器 DEFINER 账号及必要权限，不能在迁移后删除该账号。
- 管理员提供数据库 hostname、database、迁移/运行账号、TLS 策略与 CA；真实密码只写服务器
  受保护文件。URL 中的用户名/密码必须 percent-encode，避免特殊字符改变连接含义。
- Docker Engine 支持 linux/amd64，Compose >= 2.30（raw env_file），外部 HTTPS 反向代理和
  网站域名/ALLOWED_HOSTS/CORS 已确定；本包默认 Web/API 只监听 127.0.0.1。

应用会设置会话 UTC、READ COMMITTED、innodb_strict_mode、严格 SQL mode 与完整唯一/外键检查。
MySQL DATETIME(6) 保存 UTC，API 仍输出 ISO 8601 带时区。死锁/锁超时返回 409，需要重新读取
后由调用者决定是否重试；服务不会自动重放发布写入。

## 初始化与启动（本次不在远程执行）

```bash
sha256sum -c SHA256SUMS
docker load -i images.tar
cp .env.runtime.example .env.runtime
cp .env.migration.example .env.migration
cp mysql-client.cnf.example mysql-client.cnf
chmod 600 .env.runtime .env.migration mysql-client.cnf
```

填写空白项；`.env.runtime` 不包含管理员初始密码。`.env.migration` 填新管理员、随机初始密码
及独立迁移账号；JWT_SECRET 使用新的随机 >=32 字符值。raw env 文件用字面值，不加 shell 引号。
images.env 只有镜像/commit/端口/库名，没有秘密。编辑其中 MYSQL_DATABASE_NAME 为 DBA 提供的库名。
真实配置、附件、dump、账号和密钥不在包中，不要从已有测试环境复制。

连接格式：`mysql+pymysql://USER:ENCODED_PASSWORD@HOST:3306/DB?charset=utf8mb4`。
如要求 TLS，挂载管理员的 CA 到 ./tls，两个 URL 均附加
`&ssl_ca=/run/iterflow/tls/ca.pem&ssl_check_hostname=true`，并单独验证实际握手与身份。
支持方式见 [SQLAlchemy PyMySQL SSL 文档](https://docs.sqlalchemy.org/en/20/dialects/mysql.html#ssl-connections)。
本地无 TLS 的测试不能替代远程 TLS 验证。

```bash
./dc.sh config --quiet
./dc.sh --profile init run --rm migrate python -m app.cli.mysql_preflight --empty
./dc.sh --profile init run --rm migrate
./dc.sh --profile init run --rm migrate python -m app.cli.mysql_preflight
./dc.sh --profile init run --rm seed
./dc.sh up -d --wait redis api web
curl --fail http://127.0.0.1:8000/ready
curl --fail http://127.0.0.1:8080/
```

先执行正式迁移，然后 seed；不使用 create_all、stamp head 或 PG 历史迁移。
MySQL DDL 不原子：失败即停，保留现场；不要 stamp/盲目续跑。由 DBA 确认仅针对自己的空库
清理失败初始化后重建。seed 只创建基础角色、权限和新管理员，首次登录必须改密。
迁移后必须检查 mysql57_0002、68 个 trigger、键登记函数及完整唯一约束；runtime readiness
只用低权限检查。长键保持原 500 字符/2000 字节范围，分成 512 字节二进制段，以
UNIQUE(parent_id,segment) 确定路径，再以文件 leaf_id UNIQUE 保证完整键唯一；无哈希/前缀误判。
登记节点不可修改或删除，文件删除后可复用路径；节点积累需要计入存储容量。
旧的本地 mysql57_0001 安装可在停止全部写入、备份后正式 upgrade head；禁止在线升级或 stamp。

维护重启使用 `./restart.sh`：先停止 Web/API，再重启 Redis，按健康依赖启动 API 和 Web。
Web 的 Nginx 在启动时解析 API；不要在 API 尚未恢复时并行启动 Web。本地代理 DNS 曾在
该窗口把 `api` 解析到外部 fake IP，导致持续 502。包验收验证三次按依赖重启，并通过代理
检查 `/api/v1/auth/me` 就绪后逐项断言持久化；业务写入不自动重试。

## 备份与恢复

mysql-client.cnf 使用单独受保护的备份账号，配置真实 host/user/password 和 TLS。
该文件 mode 600；若由非 root 用户持有，在 images.env 填该用户的 BACKUP_UID/BACKUP_GID。
只有在已明确授权的环境中执行以下维护命令；本次实际演练只发生在隔离本地测试库/存储。
暂停全部业务写入及 DDL，使 DB 与附件获得一致快照；备份目录必须新建且 mode 700。

```bash
umask 077
mkdir backup-new
./dc.sh stop api
./dc.sh --profile ops run --rm -T client > backup-new/database.sql
./dc.sh --profile ops run --rm -T storage-backup > backup-new/uploads.tar
sha256sum backup-new/database.sql backup-new/uploads.tar > backup-new/SHA256SUMS
./dc.sh start api
```

任何一条失败立即停止，不把失败/空文件视为备份。确认 API 重启健康并保存备份至独立存储。
备份账号需要读取数据、SHOW VIEW/TRIGGER，以及该服务器上 mysqldump 所需的额外权限；
`--single-transaction --no-tablespaces --routines --triggers --hex-blob --set-gtid-purged=OFF`
保留表、数据、键登记函数与写保护。MySQL 5.7 的 --routines 备份需要 mysql.proc SELECT，
由 DBA 仅为受保护备份身份核实该权限；不授予应用运行账号。
`--no-tablespaces` 避免 5.7.31 起额外的 PROCESS 要求，见 [MySQL mysqldump 文档](https://dev.mysql.com/doc/refman/5.7/en/mysqldump.html)。
请先在目标环境验证备份权限，不能以能登录替代能备份。

恢复仅面向一个明确新建的隔离测试库与测试附件卷，mysql-client.cnf 指向该测试环境：

```bash
sha256sum -c backup-new/SHA256SUMS
./dc.sh --profile ops run --rm -T --entrypoint mysql client \
  --defaults-extra-file=/run/secrets/mysql-client.cnf RESTORE_TEST_DB < backup-new/database.sql
```

在独立测试存储解包 uploads.tar，核对属主/权限；确保 DEFINER 在恢复环境存在且具有权限。
用迁移账号执行 MySQL 预检、主链/权限/附件验收及重启验证，再生成恢复后的备份。
禁止将此命令机械用于真实库或复用生产附件卷。本包不提供自动真实 restore/删除 volume 功能。

## 本地证据与边界

上一版本地关系证明 17 项、应用验收 43 项零跳过；含主链 15 步、CAS、并发转换/关联/迁版/发布、
异常回滚、RBAC/DataScope、通知/审计、中文和日期、文件权限、三次重启与独立恢复。
PostgreSQL 完整回归 375 passed / 1 S3 skip，PG-only 37 项零跳过；独立 S3 CI 通过。
前端 320 tests、构建/契约/依赖审计通过，上一版七项 branch CI 通过。
本次 OFF/OFF 增量的本地结果见 docs/mysql57-portable-parameters.md；CI 已增加两种参数环境，
新代码的 CI 结果须另行核实，不能沿用上一版 PASS。远程尚未验证这一增量。
包的最终源 commit、镜像 ID/架构及额外启动验证见 manifest.json / verification.json。

Apple Silicon 测试使用独立 QEMU x86_64 VM；旧 ARM VM + amd64 用户态模拟有退出 139 的历史
失败，不能宣称该环境稳定。正式远程版本/配置仍须核实并执行部署前门禁，不能据本包宣称已上线。
