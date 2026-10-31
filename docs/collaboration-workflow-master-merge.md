# 协作流程优化合并记录

## 授权与基线

用户授权核对 master 无漂移后合并、推送并完成 CI，问题直接修复；不发布、不部署、不修改真实数据库。发现主线旧规则冲突后，用户明确选择取消逐人开发完成确认，由开发参与人提交验收、指定验收人确认。

- 冻结主线：`10f6bfa6410c7836d7d43e402a175d56ad9577c7`；开始合并前 fetch 核对一致。
- 原功能分支：`d7c97de880bb269f7c61bde60fd872da28cc4d03`，其六项 CI 全通过（[41172175516](https://github.com/dede233/iterflow/actions/runs/41172175516)）。
- 两线共同祖先：`a38081af9097f691c8289e9301951a0360ea0af7`。主线已有 MySQL 5.7、旧多人协作、版本权限、反馈名称与详情抽屉，不能直接用功能分支 tree 覆盖主线。
- 先在功能分支整合 master，处理 30 处文本冲突及自动合并后的语义冲突；验证通过后再 no-ff 合入 master。
- 主线 CI 目前实际为八项：backend、frontend、docker_smoke、s3、browser_smoke、backup_restore、mysql57 (standard)、mysql57 (portable)。全部保留，不缩减到六项。

## 冲突处理与兼容

保留双数据库、版本角色权限、精确文件键/有效关联保护、反馈名称、业务系统名称和发布/版本详情抽屉。需求统一使用新六阶段、环节分工、可选设计子进度；不保留可绕过新流程的旧分工/逐人确认写入口。旧客户端须随应用升级，开发契约与中文接口说明同步，正式发布契约不变。

原部署迁移不改写。PostgreSQL 新迁移衔接为 0009–0011，MySQL 为 mysql57_0007–0009；原参与表与 completed_at 保留，新 rd_requirement_actor 复制旧设计/开发分工。旧 PLANNED/DESIGNING 映射 CONFIRMED，原设计中转为 IN_PROGRESS 子进度。迁移快照保存真实旧状态、负责人和确认时间，不虚构确认/验收人。历史 DONE/ONLINE 兼容资格保留。

MySQL 新增微秒 UTC 时间、有效单确认/验收人的生成列唯一索引、新表完整性开关保护；worker 使用 MySQL 5.7 支持的行锁。MySQL 包配置加入 worker 与停写/重启顺序；本轮仅修改配置和在隔离测试中验证，不执行任何真实环境升级。

原逐人确认测试按新批准规则更新，同时保留权限、并发 CAS、分工竞态、发布原子回滚、设计阻断、内容重新确认、账号停用、重开、备份恢复和角色权限覆盖。共享新流程用例在两种数据库运行。

## 本地验证记录

- PostgreSQL 全量：415 passed / 1 skipped（独立 S3 门禁负责真实对象存储测试）。
- PostgreSQL 空库升级到 0011、Alembic check：通过，无模型差异。
- 前端：52 文件 / 342 tests passed，API 类型、构建、bundle 通过。
- Ruff / Mypy：通过，108 个应用源文件。
- 初次 MySQL 全量：58 passed / 9 failed。失败涉及旧反馈创建缺接收人、恢复脚本仍用旧接口、迁移测试旧 head/表数断言，以及本地一次性 MySQL 缺测试入口库；已修复，复验结果待下文记录。
- 新建本任务隔离容器：iterflow-merge-ci-pg / iterflow-merge-ci-redis / iterflow-merge-ci-mysql。没有使用 preview 数据库，也没有启动或清理已有 MySQL proof 容器。

## 后续验证状态

整合分支、master 合并提交、远端最终 SHA 与八项 CI 结果将在实际完成后追加；本段不表示已经合并或通过远端验证。

### 整合复验与 Fresh Self-Review

- 整合提交 `3f36ae93fa45c8f3135d458ffc8c0f60c571e190` 已推送源分支，运行 [41174107412](https://github.com/dede233/iterflow/actions/runs/41174107412)。
- 本地 MySQL 全量复验：67 passed（133.22 秒）；初次九个问题全部修复。
- 自查补充 PostgreSQL 历史迁移与跨库流程专项 16 passed；MySQL 新流程专项 10 passed，覆盖批量添加全成全败、旧 revision、站内投递消费及失效人员。MySQL 历史设计/人员/确认时间迁移及隔离恢复专项 3 passed。
- 自查修正 MySQL 历史确认快照的 UTC 时区标记；补齐包重启后 worker 启动；恢复证据的触发器数量改为数据库实查值（91），消除旧脚本写死 73 的过时记录。证据见 `docs/evidence/collaboration-workflow/merge-mysql-standard-backup-restore.json`。
- 冻结的 PostgreSQL 0001–0008 与 MySQL 0001–0006 文件未改写。这里是同一 Agent 的 Fresh Self-Review，不称 independent review。
