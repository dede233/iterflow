# 需求按阶段分工与可选设计阶段

当前追加[全员开发完成发布门禁](development-completion.md)，该文档包含操作与验收；前述阶段记录保留为历史证据。

2026-10-10 用户确认：一名总负责人，多名开发、多名设计；人员按状态进度选择，设计按需经过，不强制所有需求设计。本次仅本地实现和验收，未部署线上。

## 操作方式

1. 创建或转化需求后，打开详情，单独「设置总负责人」，不用提前选择开发、设计人员。
2. 需求确认并排期后，需要设计的点击「开始设计」，只选择设计人员，至少一名，确认后进入「设计中」。不需要设计的直接点击「开始开发」。
3. 进入开发时，点击「开始开发」，只选择开发人员，至少一名。人员分配与进入「开发中」一起保存。
4. 设计中可「调整设计人员」；开发、测试、完成阶段可「调整开发人员」。调整某项分工会保留其他分工。负责人始终单独设置。
5. 设计人员的参与记录在进入开发后保留，可以继续查看参与的需求。开发人员按原流程提测、完成，ONLINE 仍只由成功发布产生。
6. 设计开始/恢复通知设计人员；开发开始、提测通知开发人员，并通知总负责人和创建人。成功发布仍通知全部相关人员，原反馈提交人上线通知继续保留。双角色去重，操作者不接收自己触发的通知。
7. 发生 revision 冲突时保留选择，手动加载最新需求，不自动重试覆盖。

开始阶段需要同时拥有需求编辑和状态权限。管理员、研发负责人具备这两项资格；产品/项目负责人原有角色可分配负责人、调整人员，但未自动增加状态权限。兼任研发负责人的产品人员可开始阶段。开发/设计基本角色只获得 SELF 范围的需求查看与既有状态权限，不获得分配人员或用户管理权限。

候选人员依然须为启用账号，有需求查看权限及对应启用角色。设计必须 DESIGNER；开发可 DEVELOPER 或 DEVELOPMENT_LEAD。手机阶段弹窗只展示当前阶段的人员选择。

## 状态与 API

主流程：

```text
草稿 → 已确认 → 已排期 → 设计中 → 开发中 → 测试中 → 已完成 → 已上线
                   └──────────→ 开发中（无需设计）
```

DESIGNING 可暂停、取消或进入开发；暂停允许恢复设计。没有新增设计完成状态、设计审批、开发退回设计、工时等功能。Feedback 和 Version 状态机保持原样。设计中的需求不能通过 Version Publish 完成发布。

- 新 `POST /requirements/{id}/start-stage`：status 为 DESIGNING/DEVELOPING，revision 与 user_ids 必填，人员 1–100 名且不能重复；仅允许从已排期开始设计/开发，或从设计中开始开发。
- 新 `PATCH /requirements/{id}/collaborators`：kind 为 OWNER/DEVELOPMENT/DESIGN。只修改指定分工，revision 成功增加一次；当前阶段人员不能通过此接口清空。
- 既有 GET、PUT collaborators 与需求/状态接口保留。普通状态接口进入设计，或从设计进入开发时，也要求已有对应分工。
- **兼容边界**：既有 `PLANNED -> DEVELOPING` 普通状态 API 保持原行为，不强制改写历史需求或已有客户端。新前端全部通过阶段接口选择人员后开始设计/开发。阶段接口的名单、角色及人数由后端强制验证，不依赖前端隐藏或选择器校验。

当前开发契约增加 DESIGNING 与上述两个操作；历史发布契约、tag、Release 不变。

## 事务、迁移与保护

阶段开始对需求父行加锁，校验 revision、当前状态、人员资格，然后只替换对应分工；状态变化、一次 revision CAS、人员审计、状态审计和通知同一事务提交。失败全部回滚。并发开始设计/开发只有一次成功，另一次 409。已有其他分工保留；旧人员变化保存在审计快照。

新增 PostgreSQL `0006_requirement_design_stage`，在同一 DDL 事务中扩展有效 CHECK；MySQL `mysql57_0004` 扩展有效 INSERT/UPDATE 保护触发器。MySQL 5.7 不执行历史 CHECK，本轮继续以实际触发器验证枚举。触发器交换时先安装包含全部原检查的新临时保护，再更换命名触发器，最后移除临时保护，没有无保护的写窗口。原编号、source、priority、禁用检查防绕过等规则保留；模板不符合预期时，在变更之前停止。

MySQL DDL 不原子，失败后停止并保留现场，不能 stamp 或盲目续跑。生产升级时先停应用写入并备份；本轮只在独立本地库执行。既有状态和账号、密码不改写。历史迁移保留，新增 migration 不支持破坏性 downgrade。

```sh
# backend 目录；配置只从受保护文件/环境读取
python -m alembic upgrade head                       # PostgreSQL
python -m alembic -c alembic-mysql.ini upgrade head  # MySQL 5.7
python -m app.cli.mysql_preflight                   # MySQL 迁移后检查
```

最新 head：PostgreSQL `0006_requirement_design_stage`，MySQL `mysql57_0004`。已有库升级不需要重跑 seed。新分工表 DML 授权见 `deploy/mysql57/runtime-grants.sql`。原关系保护、条件唯一、派生指针、发布事务及 RBAC 不降低；阶段的人员资格是新增服务规则，没有宣称它是数据库跨行约束的等价物。

## 本地验收范围

真实 Oracle MySQL 5.7.44-log，linux/amd64，在 Mac Colima x86_64/QEMU 的独立 portable OFF/OFF 环境运行；应用会话 strict ON、UTC。PostgreSQL 使用独立回归容器。浏览器使用新的本地 API/Web 57900/57980 与独立测试库，保留原本地站点、PostgreSQL、Redis 和 Preview。

本轮 MySQL 完整回归 58 passed、零跳过；补充的发布阻断及增强恢复两项复验 2 passed、零跳过，总计 59 个不同测试用例已验证。PostgreSQL 完整回归 386 passed，1 项既有可选真实 S3 测试因未配置端点跳过；真实 PG 专项 48 passed、零跳过。前端 327 passed、构建/类型/bundle 通过，Ruff/format、Mypy 99 文件和编译通过。

完整回归、阶段专项、发布阻断、升级/SQL 约束、备份恢复及界面结果以 `docs/evidence/requirement-design-stage/acceptance.json` 和 `backup-restore.json` 为准。前端实际验证总负责人单独设置、设计开始仅选设计、开发开始仅选开发，设计人员继续查看，阶段通知区分，390/768/1280 视口与手机弹窗。

Fresh Self-Review 由同一 Agent 完成：检查契约增量、阶段资格、CAS、事务回滚、角色与历史分工、有效 SQL 约束、无保护写窗口、现有 API 兼容、发布阻断及界面流程；不称为独立终审。

当前未 push/执行 branch CI，未构建验收本轮 linux/amd64 新部署包，未升级服务器或远程数据库。线上不具备本次新增功能；上线条件仍包括 CI、新包验证和受保护的升级前备份。本地测试数据和配置不进入部署包。
