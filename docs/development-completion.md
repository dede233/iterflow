# 全员开发完成确认与发布门禁

2026-10-10 用户批准本地增量：开发人员必须分别点击完成，全部确认后才能发布。该规则追加到按需设计与按阶段分工流程，不改变 Feedback → Requirement → Version → Publish → Release 主链。线上尚未升级。

## 操作方式

1. 开始开发时选择开发人员，至少一名；总负责人和设计人员仍分别设置。
2. 每名开发人员使用自己的账号打开需求详情，在「协作人员」点击「确认本人开发完成」。界面显示每个人的「待确认／已完成」及已确认人数。
3. 开发人员只能确认本人绑定的工作。总负责人和管理员不能代其他人确认；研发负责人如果本人也被绑定为开发人员，可以确认自己的工作。
4. 状态「已完成」和个人开发完成确认是两项独立门禁。提测、验收完成沿用原状态流程；个人确认可在开发、测试或已完成阶段补充。全员确认不会自动跳过测试、把需求置为 DONE 或自动发布。
5. 版本必须 READY、所有有效需求必须 DONE，且每条需求至少有一名开发人员并已全部确认，才允许发布。发布弹窗列出尚未全员确认的需求，能打开需求查看待确认人员；即使绕过按钮直接调用发布 API，后端仍返回 409。
6. 任何重新进入开发的操作（退回、恢复、重新开发）都会清空该需求的既有确认，相关人员收到原有阶段通知，必须再次本人确认。
7. 调整开发名单时，保留未变更人员的确认；新增人员和移除后再加入的人员待确认。已有确认不因调整负责人或设计人员而失效。当前开发、测试、完成阶段禁止把开发名单清空；终态需求不能重新分配整份协作名单。
8. 每次确认都增加需求 revision 一次，写审计并通知总负责人、创建人和相关开发人员；不通知无关设计人员，不给操作者发自己的通知。旧 revision、重复确认或非法状态返回 409，前端不自动覆盖。

账号停用或开发角色/权限撤销后不能确认；既有分工不会自动视作完成。需要有分配权限的人员明确调整名单。既有需求升级后所有开发人员初始均未确认；没有开发分工的历史需求也会阻止发布，需要先补充分工并分别确认。已发布的 Release 和历史发布契约不重写。

## 契约与实现

新增 `POST /requirements/{requirement_id}/development-completion`，只接收 `{revision}`，拒绝 user_id、completed_at 等额外字段。操作者从认证身份获取，要求需求查看和状态权限、数据范围可见、当前绑定开发人员、启用且仍具开发资格。协作响应新增 `development_completions`，只包含各开发人员 ID 和本人确认的 UTC ISO 8601 时间（待确认为 null）。无新 permission code。

共享发布检查新增 `DEVELOPMENT_COMPLETION_CHECK`，检查和实际发布使用同一策略。实际发布先锁版本，再按 ID 锁有效需求与其开发参与记录，用数据库当前读重新检查确认，持锁直到 Release、Version、Requirement、Feedback、通知与审计事务提交。确认、分工和状态操作使用需求父行锁与 revision CAS，不能在检查通过后静默改变名单。发布失败没有业务写入；原发布事务失败回滚行为保留。

确认是服务层身份与发布策略，不宣称数据库能鉴别 JWT 操作者或管理员 SQL 修改的真实身份。数据库继续强制现有关系、外键和唯一约束，并新增「只有 DEVELOPMENT 记录可以有完成时间」约束：PostgreSQL 有效 CHECK，MySQL 5.7 有效 INSERT/UPDATE 触发器。未削弱原关系一致性保护。

## 迁移与运行

新增 PostgreSQL `0007_development_completion` 与 MySQL `mysql57_0005`；之前的迁移文件不修改。只给已有分工表追加 nullable 完成时间，既有业务、密码和关系保留，不自动认可历史工作。PostgreSQL TIMESTAMPTZ；MySQL DATETIME(6)，应用按 UTC 写入/读取。MySQL 原 71 个保护触发器保留，新增两个完成时间保护，总数 73。

```sh
# backend 目录，数据库配置从受保护配置/环境读取
python -m alembic upgrade head                       # PostgreSQL
python -m alembic -c alembic-mysql.ini upgrade head  # MySQL 5.7
python -m app.cli.mysql_preflight                    # MySQL 迁移后检查
```

MySQL DDL 不原子。实际升级前须停止写入并备份数据库与测试/业务存储；失败保留现场，不 stamp、不 create_all、不盲目重跑，也不做破坏性 downgrade。本轮仅在独立本地库升级。备份/恢复沿用 `deploy/mysql57/README.md` 和现有受保护配置的脚本；恢复演练只使用本轮随机创建的测试库、测试附件存储。

## 验收证据与范围

本地 Oracle MySQL 5.7.44-log（linux/amd64），在 Mac Colima x86_64/QEMU 独立 OFF/OFF 环境验证，应用会话严格模式、UTC、READ COMMITTED。PostgreSQL 使用独立回归容器；浏览器在独立 API/Web 57900/57980 和测试数据库执行，不影响原本地站点、数据库或 Preview。

全量 MySQL 62 passed、零跳过；PostgreSQL 389 passed，1 项既有可选 S3 测试未配置端点而跳过，真实 PG 专项 51 passed、零跳过；前端 330 passed、构建/类型/bundle 通过，Ruff/format、Mypy 99 文件与 compileall 通过。

结果和恢复校验保存在 `docs/evidence/development-completion/acceptance.json`、`backup-restore.json`。覆盖全员门禁、本人确认/管理员不能代点、并发 CAS、返工失效、名单变更、直接 SQL 域约束、发布与分工并发串行、注入通知异常回滚、重复发布、完整主链路、前端与契约、390/768/1280 浏览器及重启恢复。

Fresh Self-Review 由同一 Agent 执行，不称为独立终审。当前未 push 或执行 branch CI，未构建本轮 linux/amd64 新包，未连接远程数据库或升级线上服务。本地测试数据、凭据和附件不进入交付代码或部署包。

本地预览：`http://127.0.0.1:57980/#/login`。开发账号 `ceshi002`、`ceshi003`，发布管理员账号 `ceshi006`；使用约定的测试密码。已另建一条未确认开发人员的测试需求供手动验收，不会将这些测试账号迁移到线上。
