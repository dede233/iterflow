# AGENTS.md


## 项目命名

本项目正式产品名确定为：

- **中文名：迭程**
- **英文名：IterFlow**
- **完整名称：迭程 IterFlow · 需求与版本协作管理系统**
- **核心含义：迭代 + 流程，覆盖 Feedback → Requirement → Version → Release 的完整协作链路。**

建议统一使用以下工程命名：

```text
产品名：IterFlow
主仓库：iterflow
后端服务：iterflow-api
前端服务：iterflow-web
数据库：iterflow
PostgreSQL 服务：iterflow-db
Redis 服务：iterflow-redis
MinIO 服务：iterflow-minio
```

对外页面与文档优先显示“迭程 IterFlow”；代码、仓库、容器和服务名统一使用小写英文 `iterflow` 前缀。

如后续需要调整品牌视觉，可修改 Logo、登录页标题和文案，但不要因此改变核心业务模型或接口契约。

## 0. 适用范围

本文件是“需求与版本管理系统”仓库内所有开发 Agent、代码生成工具和人工开发者的最高优先级工程说明之一。
进入仓库后应先阅读本文件，再阅读 `DEVELOPMENT.md`、`TASKS.md`、`docs/` 与 `spec/`。

## 1. 规格优先级

发生描述冲突时，按以下优先级处理：

1. `AGENTS.md` 中的非协商规则
2. `docs/需求与版本管理系统_独立部署版_V1.5_完整开发基线.docx`
3. `spec/openapi-v1.5.yaml`
4. `spec/status-machines.md`
5. `DEVELOPMENT.md`
6. `TASKS.md`
7. 现有代码实现

禁止根据旧版本 V1.0–V1.4 文档推翻 V1.5 规则。
如 V1.5 文档与 OpenAPI 在核心业务上冲突，暂停相关实现，列出冲突点并询问，不得自行改变核心模型。

## 2. 核心业务模型：不可擅自修改

主链路固定为：

`Feedback -> Requirement -> Version -> Release`

规则：

- Feedback 是原始反馈。
- Requirement 是正式研发需求。
- Requirement 可直接新建，也可由 Feedback 转化。
- 多条 Feedback 可以归并到同一个 Requirement。
- 一条 Feedback 最多只能有一个“主 Requirement”。
- Version 只关联 Requirement，不允许直接把 Feedback 当作版本项。
- Release 表示一次实际发布记录。
- 发布成功后，符合条件的 Requirement 和关联 Feedback 自动同步上线状态。
- 不开发工时、Story Point、单需求预计开发时长、工时报表。

## 3. 技术栈：除非获得明确批准，不得替换

### Backend
- Python 3.12+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Redis
- MinIO / S3 compatible storage
- Pydantic v2
- JWT Access Token + Refresh Token
- RBAC

### Frontend
- Vue 3
- TypeScript
- Vite
- Element Plus
- Vue Router
- Pinia
- VueUse

### Deployment
- Docker / Docker Compose
- Nginx
- API 与 Web 独立容器

不要改成 Django、Flask、Node.js、Java、React 等另一套主技术栈。

## 4. 多人编辑与并发：必须实现

核心可编辑实体必须携带 `revision`。

写接口必须执行乐观锁：

- 客户端提交自己最后看到的 `revision`
- 数据库更新条件必须包含当前 revision
- 成功后 revision + 1
- 旧 revision 更新失败返回 HTTP 409
- 不允许“最后保存者静默覆盖”

冲突响应应尽量包含：

- `current_revision`
- `current_updated_at`
- `current_updated_by`
- 最新对象摘要

Redis 的“正在编辑”标记只用于提示，不是强制排他锁。建议 TTL 10 分钟并支持心跳续期。

状态、优先级、负责人、版本迁移等高频变更优先使用独立 API，避免整页覆盖。

## 5. 状态机：必须集中管理

禁止在 Controller / Router 内散落业务状态判断。

- 状态迁移规则必须集中在 Service / domain policy 中。
- 非法迁移返回 409。
- Version 发布必须通过专用 Service 事务。
- RELEASED / ONLINE 等终态规则严格按 `spec/status-machines.md` 与 V1.5 文档执行。

## 6. 事务边界：不得拆散

以下操作必须原子化：

### Feedback -> Requirement
同一事务至少包含：
- 创建 Requirement
- 创建 Feedback/Requirement 关系
- 回填 Feedback 主需求
- 更新 Feedback 状态
- 写审计日志

### Requirement 移动版本
同一事务至少包含：
- 关闭旧 VersionRequirement
- 新建目标 VersionRequirement
- 更新 `current_version_id`
- 写迁移原因与审计日志

### Version 发布
同一业务事务至少包含：
- 创建 Release
- 更新 Version
- 更新满足条件的 Requirement
- 更新对应 Feedback
- 创建通知事件/待发送记录

通知实际发送可以事务提交后异步执行。

## 7. 权限与安全：后端必须强制

前端隐藏按钮不等于权限控制。

每一个受保护 API：
- 验证登录身份
- 验证权限码
- 验证数据范围
- 对敏感管理操作写审计日志

不得在日志中记录：
- 明文密码
- Access/Refresh Token
- 对象存储密钥
- 数据库密码

密码使用 Argon2id 或项目已确定的安全摘要方案。

## 8. PC / Mobile 规则

同一 Vue 工程响应式适配，不另建第二套移动项目。

断点基线：
- Desktop: >= 1200px
- Tablet: 768–1199px
- Mobile: < 768px

移动端：
- 表格优先转卡片
- 多条件筛选进入抽屉
- 多列表单改为单列
- Dialog 可转全屏 Drawer/Page
- 详情区多列改为单列
- 操作按钮确保触屏可用

一期必须支持移动端：
- 登录
- 首页
- 反馈列表/详情/提交
- 需求列表/详情
- 版本列表/详情
- 通知中心
- 个人中心

权限矩阵、复杂字典、批量管理可提示使用 PC。

## 9. OpenAPI 契约

前后端接口以 `spec/openapi-v1.5.yaml` 为契约。

开发要求：
- 不要前后端分别创造字段名
- 新增接口先更新 OpenAPI，再写实现
- 修改响应结构必须同步前端类型
- 409 / 401 / 403 / 404 / 422 等错误行为保持一致
- 时间使用 ISO 8601；数据库保存 UTC，前端按本地时区显示

## 10. 数据库规则

- 使用 Alembic migration，禁止只手改数据库不留 migration。
- 生产数据禁止 destructive migration 无备份直接执行。
- 软删除/历史关系按规格处理，不随意物理删除业务历史。
- 编号字段（Feedback/Requirement/Version）必须唯一。
- 一条 Requirement 同时只能有一个 active VersionRequirement。
- 一条 Feedback 最多一个主 Requirement 关联。

## 11. 代码分层

Backend：
- `api/`：HTTP 与参数转换
- `schemas/`：Pydantic
- `services/`：业务规则/状态机/事务
- `repositories/`：数据库访问与数据范围
- `models/`：SQLAlchemy
- `core/`：配置、鉴权、中间件、异常、日志
- `tasks/`：异步任务

Router 不直接写复杂 SQL 或业务流程。

Frontend：
- `api/`：HTTP 封装
- `types/`：DTO/类型
- `views/`：页面
- `components/`：可复用组件
- `stores/`：会话与必要全局状态
- `composables/`：响应式和可复用逻辑

## 12. 开发工作方式

不要一次性大面积生成后不验证。

每个阶段必须遵循：

`阅读规格 -> 小步实现 -> 运行 -> 测试 -> 修复 -> 提交阶段结果`

进入下一阶段前，说明：
- 完成内容
- 修改文件
- 测试结果
- 未解决问题
- 是否存在规格冲突

如遇核心业务不明确，先提问，不要猜测。

## 13. 测试门禁

至少覆盖：

- Auth 登录/刷新/失效
- RBAC 权限绕过
- Feedback CRUD 与状态
- Feedback -> Requirement
- Requirement 状态机
- revision 并发冲突返回 409
- Requirement 加入/迁移 Version
- Version 发布事务
- 发布后 Requirement / Feedback 状态同步
- 移动端关键页面构建
- Docker 启动健康检查

任何影响主链路的改动不得在测试失败时宣告完成。

## 14. 最终验收主链路

至少实际跑通：

1. 管理员登录
2. 创建用户/角色并授权
3. 用户提交 Feedback
4. 负责人受理 Feedback
5. Feedback 转 Requirement
6. Requirement 设置负责人、优先级
7. Requirement 加入 Version
8. Requirement 状态按规则流转
9. Version 进入 READY
10. 发布 Version，生成 Release
11. Requirement 变为 ONLINE（满足发布规则时）
12. 关联 Feedback 显示已上线
13. 提交人收到站内通知
14. 全程有审计日志
15. 两人编辑同一 Requirement 时旧 revision 保存返回 409

## 15. 禁止事项

除非用户明确同意，不得：
- 改变四核心实体关系
- 删除 revision 乐观锁
- 改成硬排他锁替代乐观锁
- 把 Feedback 直接放进 Version
- 引入工时/Story Point
- 拆成独立 PC/移动两套业务前端
- 替换 Python/FastAPI 主后端
- 绕开 OpenAPI 契约
- 为“省事”删除权限、审计或事务规则