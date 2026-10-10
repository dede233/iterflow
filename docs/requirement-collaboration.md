# 需求开发、设计协作 — 本地实现与使用说明

当前追加[全员开发完成发布门禁](development-completion.md)，该文档包含操作与验收；前述阶段记录保留为历史证据。

本文件记录首轮一次分配全部人员的实现与验收。2026-10-10 用户随后要求按阶段选择人员并增加可选设计中，当前操作方式与新验收见 `docs/requirement-design-stage.md`；首轮验收证据保留。

2026-10-10 用户确认：保留一名总负责人，一条需求可绑定多名开发人员、多名设计人员。本次在 `codex/requirement-collaboration` 分支实现，仅本地测试；未更新线上、合并 master、创建 tag/Release 或修改远程数据库。

## 使用方法

1. 管理员在用户管理中，为开发账号授权「开发人员」，为设计账号授权「设计人员」。同一个账号可以拥有两种角色，也可保留其他已授权角色。
2. 产品经理、研发负责人或管理员打开需求详情，点击「分配协作人员」。选一名总负责人，以及需要参与的开发、设计人员；支持按姓名搜索和分页加载更多候选。
3. 保存后，相关人员在自己的需求列表中可看到该需求。仅有关联并且仍具备需求查看权限的账号获得访问；不会因此获得其他反馈、版本的全部访问范围。
4. 具备需求状态权限的关联人员可按既有状态机更新需求。分工更新、状态变更、加入/移除/迁移版本、成功发布上线时，对需求创建人、当前总负责人、开发及设计人员生成站内通知。
5. 同一人同时担任开发、设计或负责人时，一次事件只收到一条需求通知；操作者不接收自己触发的通知。停用或撤销需求查看权限的账号不接收新通知。
6. 移除开发/设计关联后，单靠该关联获得的 SELF 访问立即收回；若账号仍是创建人、负责人或拥有 ALL 数据范围，仍按那些资格访问。
7. 如果保存提示 revision 冲突，保留当前输入供对照，手动加载最新需求后重新分配，不自动覆盖他人修改。

目前是站内通知，不包含邮件、企业微信或钉钉发送。既有反馈提交人发布通知继续保留。角色负责操作资格，需求关联负责数据范围；关联不等于授予管理权限。

## 权限与接口

新增基础角色 `DEVELOPER`、`DESIGNER`，默认数据范围 SELF，具有 `dashboard.view`、`rd.requirement.view`、`rd.requirement.status`、`rd.version.view`、`rd.release.view`。没有新增 permission code，也不授予需求编辑、人员分配、用户管理、版本发布权限。拥有多个角色时继续使用原有权限合并规则。

分配沿用 `rd.requirement.edit`，并校验目标需求的数据范围。开发候选须有启用的 DEVELOPER 或 DEVELOPMENT_LEAD 角色；设计候选须有启用的 DESIGNER 角色。全部候选还须是启用账号并有需求查看权限。候选接口仅返回 ID、显示名和开发/设计资格，不返回账号、电话、邮箱或密码信息。

当前开发契约 `spec/openapi-development.yaml` 增加：

- `GET /requirements/assignee-options`：按 OWNER/DEVELOPER/DESIGNER、姓名关键词查询，每页 50 人。
- `GET /requirements/{id}/collaborators`：读取当前负责人、开发、设计及需求 revision。
- `PUT /requirements/{id}/collaborators`：携带 revision 原子替换分工，成功 revision + 1，旧 revision 返回 409。

已发布契约保持原样；既有需求读写接口、状态机与主链关系保留。旧接口的 owner_id 写入仍可用。

## 数据保护与迁移

新增 `rd_requirement_participant`，复合主键 `(requirement_id, user_id, discipline)` 允许一人同时开发和设计，拒绝同一分工重复关联；用户、需求均为 RESTRICT 外键。PostgreSQL 使用有效 CHECK；MySQL 5.7 使用 INSERT/UPDATE 行触发器严格验证 DEVELOPMENT/DESIGN（包括大小写、尾空格），三类写触发器拒绝关闭 FK/unique 检查的会话。

该新增关联没有冗余指针或跨行提交时不变量，约束在写入时有效即可。此前 PostgreSQL 延迟约束、MySQL 关系重构、条件唯一保护保持原样，没有把 Service 检查宣称为数据库约束的替代。

人员分配在需求父行锁与 revision CAS 下执行，分工、需求 revision、审计前后快照和通知同一事务提交。状态和发布通知加入原业务事务；注入中途异常时通知与业务写入全部回滚。移除旧分工的历史记录保存在审计快照。

正式迁移路径：

```sh
# PostgreSQL（backend 目录，使用受保护的本地配置）
python -m alembic upgrade head
# MySQL 5.7（backend 目录，使用受保护的本地配置）
python -m alembic -c alembic-mysql.ini upgrade head
python -m app.cli.mysql_preflight
```

新 PostgreSQL head 为 `0005_requirement_collaboration`；MySQL 为 `mysql57_0003`。迁移新增角色并关联已有权限，保留已有账号、密码、角色和需求，不需要重跑 seed。全新空库才按原初始化流程 seed。若已有同代码 DEVELOPER/DESIGNER 角色，迁移在创建新表之前明确报错，需先人工核实，不覆盖既有角色。降级会删除业务分工，脚本明确拒绝 destructive downgrade。

MySQL运行账号还需授予新表 SELECT/INSERT/UPDATE/DELETE，见 `deploy/mysql57/runtime-grants.sql`。上线升级前必须完成备份、branch CI、新包构建与容器启动验收，再安排迁移。禁止将这里的本地测试账号/密码/数据导入正式环境。

## 本地验收记录

- Oracle MySQL 5.7.44-log，linux/amd64，Mac Colima x86_64/QEMU；独立 portable 容器端口 57358，global large_prefix OFF / innodb_strict_mode OFF，应用会话 strict ON、UTC；**56 passed，零跳过**。
- PostgreSQL 完整后端：**383 passed，1 skipped**。跳过项是未配置真实 S3 endpoint 的既有可选集成测试；真实 PG 必要验收单独执行 **15 passed，零跳过**。
- 新旧数据库正式空库迁移、已有账号/需求升级、角色代码冲突保护、直接 SQL 约束、并发分配 CAS、SELF/RBAC、停用与撤权、通知去重、状态/发布异常回滚均通过。
- 完整主链与原 MySQL 验收继续通过；独立测试库三次重启、附件及分工备份恢复、71 个保护触发器和文件函数恢复均通过，证据见 `docs/evidence/requirement-collaboration/backup-restore.json`。
- 前端：**325 passed**，生成类型一致性、TypeScript/Vite 构建、bundle gate 通过；Ruff/format、Mypy（99 文件）和编译通过。
- 最终中文通知文案与卡片间距微调后，重新执行 MySQL 协作 **8 passed**、PostgreSQL 协作 **8 passed**、前端 **325 passed** 和构建门禁；完整回归的上述数字来自微调前的本轮实现。
- 浏览器实际登录产品、开发、设计、无关成员四种账号；一负责人、两开发、两设计分配，开发变更状态、设计收通知、无关成员拒绝访问均通过。1280/768/390 视口检查无横向溢出，手机分配弹窗通过。
- Fresh Self-Review：同一 Agent 复查契约增量、迁移历史不变、SQL 保护、事务边界、通知去重、scope 收回和界面错误/竞态处理。不是外部独立终审。

复现本地数据库验收（先准备项目隔离测试环境，工具会读取本地受保护配置）：

```sh
DOCKER_CONTEXT=colima-iterflow-mysql57 .venv/bin/python tools/run-mysql-tests.py --portable -q
cd backend
python -m pytest -q -W error::DeprecationWarning
python -m ruff check app tests tests_mysql57
python -m mypy app
cd ../frontend
npm run check:api-types
npm test
npm run build
npm run check:bundle
```

远程 MySQL 小版本、本次新增迁移在远程执行、新版本 linux/amd64 部署包、branch CI、外部终审和线上升级均**未验证/未执行**。本地通过不表示线上已拥有该功能或可以直接上线。本次没有读取服务器密码或生产账号数据。
