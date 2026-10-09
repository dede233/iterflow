# MySQL 5.7 独立本地验证

仅用于此适配分支的全新测试容器、测试库和测试附件。不要填入远程连接或已有环境凭据。
测试固定要求 Oracle MySQL 5.7.44、127.0.0.1:57357；数据库缺失是失败，不会跳过。

```bash
cd /Users/xiaweiyi/Developer/worktrees/iterflow/mysql-57-adaptation
python3.12 -m venv .venv
.venv/bin/python -m pip install -e 'backend[dev]'
.venv/bin/python tools/init-mysql-test-env.py
```

配置生成器遇到已有 `.env` 即退出并保留文件。所有测试秘密为随机新值、权限 600，不提交 Git。
不要 `source` 不可信配置；验收 runner 以 Python 加载配置并且不打印凭据。

Apple Silicon 上旧 ARM Colima 的 amd64 用户态模拟发生过退出 139，见执行记录。
可创建完全独立 x86_64 profile，显式使用 QEMU CPU 模拟，不切换/重启现有 default profile：

```bash
brew install qemu lima-additional-guestagents
colima start iterflow-mysql57 --activate=false --arch x86_64 --vm-type qemu \
  --cpu 2 --memory 3 --disk 25 --mount-type 9p \
  --mount /Users/xiaweiyi/Developer/worktrees/iterflow/mysql-57-adaptation/data:w
docker --context colima-iterflow-mysql57 compose -f tools/mysql57-proof/compose.yml up -d --wait db
```

MySQL 的 Compose `platform` 始终是 `linux/amd64`。本地端口 57357 必须空闲；
仅停止此任务自己建立的旧 proof-db，不停用其他环境来腾端口。
该 profile 只挂载本工作目录的忽略目录 data：包验收的临时私密配置需要 bind mount，
文件夹 700、文件 600；测试结束自动删除。数据库仍使用独立 Docker named volume。
本次新 VM 的 resolv.conf stub 缺失，只修复了该 VM 的 DNS；没有改变现有 profile。
Redis / PostgreSQL 可在原 context 中独立启动本任务的新实例（57379 / 57332）：

```bash
docker --context colima compose -f tools/mysql57-proof/compose.yml up -d --wait redis postgres
DOCKER_CONTEXT=colima-iterflow-mysql57 .venv/bin/python -m pytest -q tools/mysql57-proof/test_proof.py
DOCKER_CONTEXT=colima-iterflow-mysql57 .venv/bin/python tools/run-mysql-tests.py -q --tb=short -W error::DeprecationWarning
```

Linux amd64 / CI 使用自己的默认 Docker context 启动三项服务并运行同样测试即可。
测试通过正式独立 Alembic 路径初始化随机 `iterflow_mysql57_` 库，seed 仅创建基础权限/角色
和新管理员；不使用 create_all/stamp。备份恢复用例只恢复到第二个随机测试库和第二个
临时测试存储，测试结束清理自己的库。三次连续重启后验证关系和附件持久化。

备份命令在测试中真实执行（容器自己的测试秘密通过 MYSQL_PWD 使用，不显示）：

```bash
# DB_NAME 必须是自己新建的隔离测试库；恢复只允许另一个空的隔离测试库。
docker --context colima-iterflow-mysql57 exec iterflow-mysql57-proof-db sh -c \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysqldump -uroot --single-transaction --routines --triggers --hex-blob --set-gtid-purged=OFF "$1"' sh "$DB_NAME" > isolated.sql
chmod 600 isolated.sql
docker --context colima-iterflow-mysql57 exec -i iterflow-mysql57-proof-db sh -c \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot "$1"' sh "$RESTORE_TEST_DB" < isolated.sql
```

MySQL 生成列由恢复 DDL 重建，触发器由 dump 保存；恢复后必须运行迁移账号预检并验证
63 个写保护触发器、两个唯一索引、用户/业务状态和本地附件。附件备份必须同时保留。
原 dump 含测试账号密码摘要，禁止纳入部署包或提交；证据只保存结果与 SHA256。

应用正式迁移入口为 `python -m app.cli.migrate`，它根据 DATABASE_URL 选择独立迁移链；
手动 Alembic 命令必须 `alembic -c alembic-mysql.ini upgrade head`，默认路径拒绝 MySQL。
`python -m app.cli.mysql_preflight --empty` 只读检查空库；无参数检查初始化后的表/head/
触发器/关系索引。完整主链验收不能由该预检代替。
