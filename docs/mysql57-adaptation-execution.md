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
