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

自查同时发现 MySQL runtime SQL 授权模板尚未包含六张新表，已补齐模板，并要求包验收核对模板表集合与实际迁移库一致；防止测试动态授权通过而交付模板遗漏。仅修改模板，没有对真实数据库执行 GRANT。

## 整合 CI 与合并执行

整合基线 `3f36ae93fa45c8f3135d458ffc8c0f60c571e190` 的 [Run 41174107412](https://github.com/dede233/iterflow/actions/runs/41174107412) attempt 1 八项全部成功：backend 124457983417、frontend 124457983209、docker_smoke 124457983383、s3 124457983391、browser_smoke 124457983397、backup_restore 124457983359、mysql57 standard 124457983533、mysql57 portable 124457983339。后端 415 passed / 1 skipped，PG 专项 77 passed；浏览器 173 passed；MySQL 两种配置各 67 passed，均完成实际 amd64 包主链、重启及隔离恢复。

随后提交 e5f7c6f 增强迁移历史/批量/投递测试及 UTC 快照、包 worker 重启；e563efa 补齐 MySQL runtime 授权模板和包内一致性检查。这两次增量本地验证见上文，将由最终 master 的全量 CI 再验证，不能拿 3f36ae9 的 CI 替代。

合并前再次 fetch 确认远端和本地 master 均为 `10f6bfa6410c7836d7d43e402a175d56ad9577c7`，无漂移。目标为 no-ff 合入 `e563efa`，在现有 master worktree 操作；原有未跟踪 data/ 与历史验收文件完整保留。此合并只推送 origin/master，不创建标签、Release，不部署、不执行真实数据库迁移。

最终 master CI 结果待实际运行完成后记录。

## master 验证完成

已创建并推送 no-ff 合并提交 `69c2c877cfee27b4142f03ea00559238f0cdc489`；第一父提交为冻结主线 `10f6bfa6410c7836d7d43e402a175d56ad9577c7`，第二父提交为源分支 `e563efae6eceac8275b7720196df73091ed81495`。合并树相对源分支仅增加合并记录并清除方案文档尾随空格，未再次改变产品代码。

[master CI 41174648931](https://github.com/dede233/iterflow/actions/runs/41174648931)，attempt 1，精确匹配上述 merge SHA，八项全部 SUCCESS，无重跑或失败忽略。

| 任务 | Job ID | 结果 |
| --- | --- | --- |
| backend | 124459592384 | PASS：416 passed / 1 skipped；PG 专项 78 passed / 0 skipped，迁移与类型检查通过 |
| frontend | 124459592641 | PASS：342 tests，类型、构建、bundle 与依赖审计通过 |
| docker_smoke | 124459592508 | PASS：隔离 Compose 初始化、健康与认证 |
| s3 | 124459592484 | PASS：真实 S3-compatible round trip，覆盖后端全量中的可选跳过项 |
| browser_smoke | 124459592541 | PASS：173 tests |
| backup_restore | 124459592557 | PASS：一次性 runner 的数据库/附件备份恢复 |
| mysql57 (standard) | 124459592458 | PASS：68 tests，实际 amd64 包主链、权限、重启、备份及恢复 |
| mysql57 (portable) | 124459592501 | PASS：68 tests，OFF/OFF 与 767-byte 键验证、实际包及恢复 |

本次记录为合并 CI 完成后的文档收口；文档收口提交同样运行全量 CI，最终提交 SHA 和对应 CI 链接在交付回复中提供，不以本表冒充其他 SHA 的结果。

本任务临时 PostgreSQL、Redis、MySQL 容器及其临时凭据已清理；原 Preview 容器、既有停止的 MySQL proof 容器、master worktree 原有未跟踪 data/ 与验收文件未修改。未创建 tag/GitHub Release，未发布、部署、执行真实数据库 migration/GRANT/restore；只推送 origin 源分支和 master。

### UTC 快照边界修复

最终核对发现：PostgreSQL 可能按非 UTC 会话时区返回带时区的 datetime，直接 replace(tzinfo=UTC) 会改变迁移快照表达的实际时刻。修正为“已有时区先换算 UTC；MySQL 的无时区 UTC 值才补 UTC 标记”。原历史表 completed_at 不更新。新增四种时间来源及未确认空值测试，5 passed；最新修复提交重新跑完整八项 CI，最终精确 SHA/运行链接在交付回复记录。本轮迁移始终未在真实业务库执行。
