# 全员开发完成确认与完成及发布门禁

2026-10-10 用户批准本地增量：开发人员必须分别点击完成，全部确认后才能发布。该规则追加到按需设计与按阶段分工流程，不改变 Feedback → Requirement → Version → Publish → Release 主链。后续已于 2026-10-11 升级线上，实际范围见 [线上升级记录](collaboration-online-upgrade-2026-10-11.md)。

当前统一文档入口：[操作手册](user-manual.md)、[接口集成指南](api-guide.md)。下述分阶段验收保留为历史证据。

## 操作方式

1. 开始开发时选择开发人员，至少一名；总负责人和设计人员仍分别设置。
2. 每名开发人员使用自己的账号打开需求详情，在「协作人员」点击「确认本人开发完成」。界面显示每个人的「待确认／已完成」及已确认人数。
3. 开发人员只能确认本人绑定的工作。总负责人和管理员不能代其他人确认；研发负责人如果本人也被绑定为开发人员，可以确认自己的工作。
4. 提测后，只有至少一名开发人员且全部已本人确认时，产品或其他具备需求状态权限的人员才能将需求标记为「已完成」。未满足时「完成」按钮禁用，直接调用状态 API 也返回业务冲突 40913。个人确认可在开发或测试阶段进行；历史已完成记录仍允许本人补充确认。全员确认不会自动跳过测试、把需求置为 DONE 或自动发布。
5. 版本必须 READY、所有有效需求必须 DONE，且每条需求至少有一名开发人员并已全部确认，才允许发布。发布弹窗列出尚未全员确认的需求，能打开需求查看待确认人员；即使绕过按钮直接调用发布 API，后端仍返回 409。
6. 任何重新进入开发的操作（退回、恢复、重新开发）都会清空该需求的既有确认，相关人员收到原有阶段通知，必须再次本人确认。
7. 调整开发名单时，保留未变更人员的确认；新增人员和移除后再加入的人员待确认。已有确认不因调整负责人或设计人员而失效。当前开发、测试、完成阶段禁止把开发名单清空；终态需求不能重新分配整份协作名单。
8. 每次确认都增加需求 revision 一次，写审计并通知总负责人、创建人和相关开发人员；不通知无关设计人员，不给操作者发自己的通知。旧 revision、重复确认或非法状态返回 409，前端不自动覆盖。

账号停用或开发角色/权限撤销后不能确认；既有分工不会自动视作完成。需要有分配权限的人员明确调整名单。既有需求升级后所有开发人员初始均未确认；没有开发分工的历史需求也会阻止发布，需要先补充分工并分别确认。已发布的 Release 和历史发布契约不重写。

## 契约与实现

新增 `POST /requirements/{requirement_id}/development-completion`，只接收 `{revision}`，拒绝 user_id、completed_at 等额外字段。操作者从认证身份获取，要求需求查看和状态权限、数据范围可见、当前绑定开发人员、启用且仍具开发资格。协作响应新增 `development_completions`，只包含各开发人员 ID 和本人确认的 UTC ISO 8601 时间（待确认为 null）。无新 permission code。

共享发布检查新增 `DEVELOPMENT_COMPLETION_CHECK`，检查和实际发布使用同一策略。实际发布先锁版本，再按 ID 锁有效需求与其开发参与记录，用数据库当前读重新检查确认，持锁直到 Release、Version、Requirement、Feedback、通知与审计事务提交。确认、分工和状态操作使用需求父行锁与 revision CAS，不能在检查通过后静默改变名单。发布失败没有业务写入；原发布事务失败回滚行为保留。

进入 DONE 的检查在状态 revision CAS 获取需求父行锁后执行，对开发参与记录进行当前读并持锁至事务结束，与本人确认和人员调整串行。未分配人员或仍有人待确认时，整个状态事务回滚，status、revision、审计、通知均不提交。旧 revision 仍按原规则返回 40910。前端在协作数据加载中或加载失败时禁用完成；其他账号确认后需刷新需求。该补充不新增 API 字段或数据库迁移。

已有「DONE + 待确认」数据不自动改写或认可。可由绑定开发人员补充本人确认，或有权限人员填写原因「重新开发」后重新走提测和完成流程。开发名单后续变化仍会保留未变更人员确认，新增人员待确认，并继续受全员发布门禁约束。

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

## 2026-10-10 完成状态门禁补充验收

用户发现产品可在开发人员 0/1 确认时将需求置为 DONE。原实现只拦截发布，现补充状态事务内的全员确认检查、完成按钮禁用和加载失败时的禁用行为。无新增 migration、permission 或 API 字段；开发契约与受保护接口文档增加规则说明，历史正式契约未修改。

真实 MySQL 5.7.44 全量首轮 63 passed / 1 failed / 0 skipped；唯一失败为备份演练使用默认 Docker context 中的同名已停止容器。指定 `DOCKER_CONTEXT=colima-iterflow-mysql57` 后仅重跑该项，1 passed / 63 deselected / 0 skipped，保留首次失败。新增确认/完成专项 3 passed / 61 deselected。64 项必要 MySQL 场景全部覆盖通过。仅操作独立容器、随机测试库和测试存储。

PostgreSQL 全量 391 passed，1 项既有可选 S3 未配置而跳过；真实 PostgreSQL 专项 56 passed、零跳过。前端 335 passed；契约类型一致性、构建、bundle、Ruff/format、Mypy 99 文件、compileall 通过。多账号浏览器覆盖产品/管理员 API 绕过 409、0/2 与 1/2 禁止完成、2/2 才能完成、返工清空确认及 390/768/1280 视口。双数据库还验证失败不增 revision/审计/通知、注入异常全回滚、旧 revision 40910，以及 DONE 与名单变更并发串行。

证据：[验收结果](evidence/requirement-done-gate/acceptance.json)。Fresh Self-Review 为同一 Agent 复查；本次没有 push、branch CI、新部署包或线上升级。完整首次失败与后续测试日志留在本地 `data/done-gate-qa/`，不打包测试数据或凭据。

## 2026-10-11 线上升级收口

源 commit `2b37509` 的八项 Branch CI 及实际 linux/amd64 包验收通过后，按用户授权升级 sx-kc.xyz:8443。追加 MySQL 0003–0005；原记录摘要相同，未 seed、清空账号或代确认。升级前后数据库与附件备份均校验，重启、健康及只读页面验收通过。详细范围、首次失败修正、环境与备份路径见 [线上升级记录](collaboration-online-upgrade-2026-10-11.md)。上文各次本地验收事实保留。
