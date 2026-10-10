# AGENTS.md


## 项目命名

本项目正式产品名确定为：

- **中文名：迭程**
- **英文名：IterFlow**
- **完整名称：迭程 IterFlow · 需求与版本协作管理系统**
- **核心含义：迭代 + 流程，覆盖 Feedback → Requirement → Version → Publish → Release 的完整协作链路。**

建议统一使用以下工程命名：

```text
产品名：IterFlow
主仓库：iterflow
后端服务：iterflow-api
前端服务：iterflow-web
数据库：iterflow
PostgreSQL 服务：iterflow-db
Redis 服务：iterflow-redis
对象存储：本地默认使用 LocalFileStorage，生产可配置 S3Storage
```

对外页面与文档优先显示“迭程 IterFlow”；代码、仓库、容器和服务名统一使用小写英文 `iterflow` 前缀。

如后续需要调整品牌视觉，可修改 Logo、登录页标题和文案，但不要因此改变核心业务模型或接口契约。

## 0. 适用范围

本文件是“需求与版本管理系统”仓库内所有开发 Agent、代码生成工具和人工开发者的最高优先级工程说明之一。
进入仓库后应先阅读本文件，再阅读 `DEVELOPMENT.md`、`TASKS.md`、`docs/` 与 `spec/`。

2026-10-11 当前开发主线：用户已明确授权将 MySQL 5.7 适配和需求协作分支合入并推送 master，合并记录见 `docs/master-merge-2026-10-11.md`。当前开发契约为 `spec/openapi-development.yaml`，保留 PostgreSQL 路径；本次仅同步 Git 主线与文档，不重新部署服务器或操作数据库，不创建 tag/Release。以下 V1.8.1 正式发布说明及各版本授权章节保留为历史记录，不代表本次又进行正式发布。

版本状态：本次正式发布目标为 `v1.8.1`，Hotfix 外部独立终审 PASS，用户已授权 Final Release + Cloudflare Preview Resume。正式发布成立条件为新的 Release Branch / Final Master 六项 CI PASS、annotated v1.8.1 tag 与正式 GitHub Release；发布事实以最终 master commit、标签和 Release 为准，不提前记录 tag SHA。发布 base：`df9e1ba1a5ee1a4c763098d8e180250f409bedd3`；包、FastAPI、health、Frontend 与当前契约元数据同步 1.8.1，当前契约 `spec/openapi-v1.8.1.yaml`，API shape 不变。v1.8.0 及更早正式标签/Release/契约不可变；本轮只发布已审查的共享 PageHeader 平板响应式修复，随后将正式版本合入独立 Preview 并恢复验收，不部署 Production。证据见 `docs/v1.8.1-release-readiness.md`。

## 1. 规格优先级

发生描述冲突时，按以下优先级处理：

1. `AGENTS.md` 中的非协商规则
2. V1.5 核心领域冻结规则及 `docs/需求与版本管理系统_独立部署版_V1.5_完整开发基线.docx`
3. `docs/v1.8-plan.md`：仅定义已批准的 V1.8 增量范围、非范围和阶段目标
4. 当前开发契约：`spec/openapi-development.yaml`；已发布的 V1.5/V1.6/V1.7/V1.8/V1.8.1 契约冻结，历史发布快照以不可变标签为准
5. `spec/status-machines.md`
6. `docs/v1.8-baseline-audit.md`：正式 V1.7 基线实现事实盘点，不用于推翻冻结业务规则
7. `DEVELOPMENT.md`
8. `TASKS.md`
9. 当前代码和测试

禁止根据旧版本 V1.0–V1.4 文档推翻 V1.5 规则。
如 V1.5 文档与 OpenAPI 在核心业务上冲突，暂停相关实现，列出冲突点并询问，不得自行改变核心模型。
V1.8 Plan 不能改变 Feedback → Requirement → Version → Publish → Release 主链、状态机、Publish 事务、Release 记录语义、revision CAS 或 RBAC/DataScope 基本原则。

## 2. 核心业务模型：不可擅自修改

主链路固定为：

`Feedback -> Requirement -> Version -> Publish -> Release`

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
- S3 Compatible Object Storage（本地默认 LocalFileStorage，可选 S3Storage）
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

对象存储必须通过统一的 `StorageService` 抽象访问。业务模块不得直接依赖 boto3、SeaweedFS、RustFS 或其他厂商实现；当前 Driver 为 `LocalFileStorage` 与基于标准 S3 API 的 `S3Storage`。

`StorageService` 至少提供上传、删除、存在性检查、下载 URL 生成和打开文件能力。LocalFileStorage 必须拒绝绝对路径、`..` 路径穿越和任意目录读取，真实磁盘文件名使用系统生成的 `storage_key`。S3Storage 只使用 boto3 标准 S3 API，保持厂商无关。

文件元数据保存在数据库，业务关联只使用 `file_id`，不得把物理路径作为业务主数据。下载前始终由后端执行身份、权限和数据范围校验；signed URL 必须短时有效。

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

2026-10-10 用户批准本地需求协作增量：保留一名总负责人、多名开发/设计，人员按阶段选择，并增加可选 DESIGNING（设计中）。PLANNED 可进入 DESIGNING 或直接 DEVELOPING；详细规则与 API 兼容边界以更新后的 `spec/status-machines.md`、`spec/openapi-development.yaml` 和 `docs/requirement-design-stage.md` 为准。这是既有需求状态机的明确授权增量；不改变 Publish/Release、CAS、核心实体关系及 RBAC，不自动授权线上升级或历史发布重写。

2026-10-10 用户进一步明确授权：绑定的每名开发人员本人确认完成后才可发布。新增发布门禁、个人确认和双数据库追加迁移，规则见 `docs/development-completion.md`；不自动授权服务器操作。

2026-10-10 用户指出未确认开发人员时产品仍可完成需求。本地补充：进入 DONE 也必须至少一名开发人员且全部本人确认，后端在状态事务内强制校验，失败 409 且不提交任何业务写入；提测规则、历史已完成记录和发布门禁保留。本次无需新增迁移，不自动授权线上升级。

禁止在 Controller / Router 内散落业务状态判断。

- 状态迁移规则必须集中在 Service / domain policy 中。
- 非法迁移返回 409。
- Version 发布必须通过专用 Service 事务。
- RELEASED / ONLINE 等终态规则严格按 `spec/status-machines.md` 与 V1.5 文档执行。
- Version 的 `RELEASED` 只能通过 `POST /versions/{id}/publish` 进入；普通状态接口不得设置。
- Version 允许 `READY -> TESTING`，但必须填写原因并写审计日志。
- Requirement 的 `ONLINE` 只能由成功发布事务自动产生；普通状态接口不得设置。
- Requirement 允许在所属 Version 尚未发布时 `DONE -> DEVELOPING`，但必须填写原因并写审计日志。
- V1.5 MVP 仅支持成功发布，固定写入 `Release.result = SUCCESS`。

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

2026-10-08 用户授权增加仅超级管理员 / 研发负责人可见的接口文档。当前开发入口改为 `spec/openapi-development.yaml`，新增 AuthMe 可选资格标记与受保护的文档读取接口；不新增角色、permission 或 migration，不修改核心业务契约。`spec/openapi-v1.8.1.yaml` 保留为已发布历史快照，不重写已有 tag / Release；该开发快照不构成新的正式发布。

V1.8.1 正式发布时的契约为 `spec/openapi-v1.8.1.yaml`，由正式 V1.8 契约复制，仅更新 info.version / description，无 API shape 变化；生成类型与 parity 入口同步切换。V1.5/V1.6/V1.7/V1.8 契约冻结，历史正式快照以不可变标签为准。后续 API 变更继续 contract-first，并遵守核心业务规格优先级。

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

## 16. V1.7 历史自主执行授权与停止条件

用户已授权按 Phase 0–4 自主推进。每阶段必须 Implementation Pass → 本地门禁 → Fresh Self-Review → branch 六项 CI → 验证 master 未漂移 → no-ff merge → docs-only closeout → final master 六项 CI；全部通过才能继续下一阶段。执行证据记录在 `docs/v1.7-autonomous-execution-log.md`，同一个 Agent 的复查不得称为 independent review。

每阶段最多三轮 Fix Loop。明确外部基础设施失败可在 HEAD 不变且保留首次失败证据时只重跑失败 job 一次；再次失败停止。真实测试失败必须修复，不降低门禁。需要新 migration、新 permission、新核心实体、TEAM、状态机/Publish 改变、无法在授权范围小修的安全问题，或 master 外部漂移时立即停止。

Phase 0–4已完成RELEASE READY，外部独立终审PASS。本次用户已授权v1.7.0 Final Release：仅版本元数据/当前发布文档、本地及六项CI门禁、no-ff merge、annotated tag与正式GitHub Release；完成后停止。Cloudflare Preview升级和正式部署另行授权，不操作生产恢复/volume/数据库。


## 17. V1.8 Final Release 授权与停止条件

V1.8 C0/C1/C3/C4 Implementation、Fresh Self-Review、Release Readiness 与外部独立终审均 PASS。用户已授权 release/v1.8.0：仅版本元数据、V1.8 契约快照/工具入口、当前发布文档及版本断言；本地门禁 → Release Fresh Self-Review → branch 六项 CI → master 无漂移 → no-ff merge → final master 六项 CI → annotated tag / GitHub Release → 双远端镜像核验。最多三轮 Fix Loop；明确瞬时基础设施错误允许同 HEAD failed jobs 重跑一次并保留首次失败证据。业务改动、新迁移/权限、未知 master 漂移、契约 shape 漂移、历史 tag 漂移或错误 release/tag 目标立即 HARD STOP。发布后停止；Preview 升级、生产部署/migration/restore、volume 或真实数据操作均未授权。

## 18. V1.8.1 Final Release + Preview Resume 授权

本次正式发布目标为 `v1.8.1`，Hotfix 外部独立终审 PASS，用户已授权 Final Release + Cloudflare Preview Resume。正式发布成立条件为新的 Release Branch / Final Master 六项 CI PASS、annotated v1.8.1 tag 与正式 GitHub Release；发布事实以最终 master commit、标签和 Release 为准，不提前记录 tag SHA。发布 base：`df9e1ba1a5ee1a4c763098d8e180250f409bedd3`；包、FastAPI、health、Frontend 与当前契约元数据同步 1.8.1，当前契约 `spec/openapi-v1.8.1.yaml`，API shape 不变。v1.8.0 及更早正式标签/Release/契约不可变；本轮只发布已审查的共享 PageHeader 平板响应式修复，随后将正式版本合入独立 Preview 并恢复验收，不部署 Production。证据见 `docs/v1.8.1-release-readiness.md`。

Release Fresh Self-Review → 本地门禁 → 新 Release Branch 六项 CI → master 无漂移 → no-ff merge → 新 Final Master 六项 CI → annotated tag / 正式 GitHub Release → Gitee 镜像核验。随后 no-ff merge 正式版本到 Preview，保留基础设施补丁并验证产品 tree 相同；新 Preview 六项 CI → 新 pre-hotfix backup → 实际升级 → 从 768px 原阻断缺陷开始验收 → restart persistence → post-upgrade backup。禁止真实 restore、删除 volume、新增 migration/permission、其他产品开发或 Production 操作；冻结 SHA 漂移、API shape 变化、数据/账号异常或三轮 Fix Loop 后仍失败立即 HARD STOP，保留现场。
