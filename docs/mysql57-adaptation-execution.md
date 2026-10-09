# MySQL 5.7 本地适配执行记录

基线 master：`a38081af9097f691c8289e9301951a0360ea0af7`。
分支：`codex/mysql-57-adaptation`；工作目录：
`/Users/xiaweiyi/Developer/worktrees/iterflow/mysql-57-adaptation`。
本次授权覆盖 MySQL 驱动、独立迁移、兼容实现及测试；不延续历史发布授权。
不操作远程数据库、服务器、Preview、master、历史迁移、tag 或 Release。

## 阶段 0 — 最小关系保护验证

本机 Docker Server 为 linux/arm64，MySQL 显式采用 `platform: linux/amd64` 模拟运行。
镜像 mysql:5.7.44，registry digest：
`sha256:4bc6bc963e6d8443453676cae56536f4b8156d78bae03c0145cbe47c2aad73bb`。
新容器、端口 127.0.0.1:57357、新卷；临时测试库仅使用 `iterflow_proof_` 随机前缀。
不使用或导入已有环境数据。测试密码在忽略的 `.env`（权限 600）。

双向即时触发器方案被实测否决：

1. 一致性 guard 使用普通 SELECT 时，REPEATABLE READ 旧快照能够让指针不一致的 UPDATE 提交。
2. 改为 FOR UPDATE 当前读后，合法关系写入失败（MySQL 1442）；触发器链不得锁定原写入表。

两个否决场景均保留为可重复证据测试，测试 PASS 表示确认该方案不可采用。

通过的候选：MySQL 采用单一关系事实，`current_version_id` / `main_requirement_id`
从有效/主关系实时派生；不存储第二份可写指针。关联仍为 RequirementFeedback /
VersionRequirement，历史关系仍保留，业务基数和 API 字段语义不变。
生成列把 true 的父 ID 映射到唯一键、false 映射 NULL；外键保护实体存在性，
INSERT/UPDATE 触发器执行布尔域约束。所有表 InnoDB。
PostgreSQL 继续保留实体指针列与提交时延迟检查，历史迁移不修改。

保证差异是物理写法与检查时点，不是已提交关系保障：PG 允许事务内先写指针，
提交时核对两份数据；MySQL 只有关联事实，派生指针无法单独赋值或出现背离。
直接 SQL 写旧指针列失败，写只读投影失败；重复有效关系/无效外键/非法布尔值/
覆盖生成列均被 DB 拒绝。合法多步迁移仍在同一个事务内，外部读者不见中间状态，
异常回滚保留旧关系。ORM 必须使用 SQL 表达式派生属性，不能把 API 字段作为物理列更新。

`tools/mysql57-proof/test_proof.py`：15 passed；初次执行 14 passed / 1 failed，
原因是只读 VIEW 的预期错误码写成 1348，真实为 1288；修正断言后通过。
证据：`docs/evidence/mysql57/phase0-pytest.txt`。

Fresh Self-Review：完成，没有用 Service 检查代替 DB 约束；没有信任可伪造的会话标记。
候选验证仅覆盖最小模型，尚不代表应用完成适配。阶段 1–4 未完成，禁止部署声明。

## 阶段 1 — 独立迁移、驱动、类型与约束

新增 PyMySQL 1.2.3（固定版本及 PyPI SHA256）；PostgreSQL 驱动保留。
独立 `alembic-mysql.ini` / `mysql57_0001` 使用冻结的显式 DDL，21 张业务表；
不调用 create_all，不 stamp，不修改任何 `alembic/versions/` 历史脚本。
默认 Alembic 路径拒绝 MySQL URL，避免误运行 PostgreSQL 历史迁移。
空库检查拒绝已有表/视图；MySQL 非事务 DDL 失败保留部分库，禁止自动 stamp/续跑。
本地初次 FK DDL 失败库 `iterflow_mysql57_app` 保留；调整关系 FK 为 RESTRICT 后，
新库 `iterflow_mysql57_app2` 迁移及 seed 通过，后续类型/防绕过增强在随机新库重验。
仅 seed 基础角色、权限和新管理员，没有已有账号/附件/数据导入。

MySQL 使用 JSON、UTC DATETIME(6)、utf8mb4；会话设置 UTC、READ COMMITTED、严格模式。
布尔/枚举由 INSERT/UPDATE 触发器执行，不能依赖 5.7 不执行的 CHECK。
所有业务表 INSERT/UPDATE/DELETE 触发器拒绝 foreign_key_checks/unique_checks=0 的写会话。
运行账号必须无 DDL/TRIGGER 权限；迁移账号分离。运行 readiness 不要求 TRIGGER 权限，
由迁移后预检检查所有 63 个写保护触发器，runtime 检查表集/head/关系唯一索引。

自然唯一标识采用 VARBINARY + UTF-8 codec，保持 PostgreSQL 的大小写和尾空格精确相等；
数据库触发器验证 UTF-8/字符数，文本搜索显式转字符类型。
MySQL 关系 FK 使用 RESTRICT（生成列 base 列不支持 CASCADE）；较 PG 更严格地拒绝物理删除
有关联的实体，历史关系保留。当前业务 API 不物理删除这些实体，移除/迁版行为保持。

Fresh Self-Review：识别并补齐会话关闭外键/唯一检查的绕过；不依赖应用约定。
目前迁移版本尚在本地开发，后续需要应用全量验收与 linux/amd64 镜像验证。

## 阶段 2 — 事务与并发兼容

MySQL 发布在同一事务内按 ID 锁定合格对象，以 status + revision 条件更新并核对 rowcount，
随后只对实际更新的 ID 写审计和通知；PostgreSQL RETURNING 路径保持。
CAS 更新仍使用 WHERE revision、成功 +1；只把 MySQL 派生指针交给关联事实，
不会将 SQL 表达式作为物理 UPDATE 目标。
MySQL 转需求先锁定反馈进行 current read，之后仍使用 revision CAS，防止并发 CREATE_NEW
在验证旧 revision 前产生重复业务编号候选。
死锁/锁超时/数据库约束冲突映射为 HTTP 409（40940），不自动重放业务写入。
数据库异常不向响应暴露 SQL/连接凭据。

真实 MySQL 应用验收当前 39 passed（含 13 个日期用例）；0 skipped。
覆盖主链、Auth/首次改密/Refresh rotation/logout、创建角色/用户、RBAC/DataScope、中文字面搜索、
文件上传/下载/删除、旧 revision 40910、多反馈归并/迁版历史、并发转换/迁版/发布、
发布写入完成后的故障回滚、数据库枚举/布尔/指针/外键/唯一检查关闭绕过。
对应证据：`docs/evidence/mysql57/mysql-acceptance.txt`。
PostgreSQL 早期完整回归 375 passed、1 skipped（真实 S3 由单独门禁覆盖），
后续最终代码仍须复跑；不宣称此结果已覆盖所有最终变更。
Fresh Self-Review：发布候选读取与 UPDATE 均在同一事务内；未弱化 revision 或添加业务模型/状态。
阶段 3 的持续运行、备份恢复、最终回归与 CI 尚未完成；阶段 4 尚未开始。
