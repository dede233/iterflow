# 协作流程优化实施记录

## 2026-10-31 开工与范围冻结

用户在方案交付后明确授权开工。开发分支为 `codex/collaboration-workflow`，复用当前工作目录；开始时仅有上一轮新增、尚未提交的方案文档，无其他未提交改动。

按方案推荐默认值实施：反馈接收人不自动扩大读取范围；需求取消总负责人，保留历史访问依据；多人设计／开发不强制会签；取消独立排期；邮件默认仅待办与上线；批量关联全成全败。正式版本号暂不变，实际环境迁移、合并发布和部署未执行。

AGENTS.md、DEVELOPMENT.md、TASKS.md 已区分本轮开发授权与历史发布授权。阶段 0 的产品范围和实施默认值已冻结。各新增能力仍须先更新开发契约及状态规格，再实施后端、迁移与前端；本批次复用已有读取和反馈写入契约，无新增 API 或状态变化。

## 阶段 1 表单精简与摘要体验

### 已实现

- 反馈新建／编辑移除期望结果与实际结果字段，并从写入 payload 移除；旧值在详情显示为历史补充信息，不清空数据库历史值。
- 版本需求清单的桌面“查看”和手机卡片“查看”改为摘要弹窗，包含需求描述、验收标准、状态、优先级、类型及权限范围内的来源反馈。
- 保留完整详情入口；关闭摘要不改变当前版本路由、清单状态和页面上下文。
- 摘要独立执行需求权限检查与 scoped GET；来源反馈读取失败不阻断摘要；关闭、切换需求或账号／权限改变时清空旧数据并拒绝过期异步响应。
- 手机摘要使用实际全屏尺寸，桌面和平板采用居中弹窗；弹窗挂载到 body，以支持版本详情已处于弹层的情况。

### 修改文件

- `frontend/src/views/feedback/FeedbackCreateView.vue`
- `frontend/src/views/feedback/FeedbackDetailView.vue`
- `frontend/src/views/version/VersionDetailView.vue`
- `frontend/src/components/RequirementSummaryDialog.vue`
- `frontend/src/components/RequirementSummaryDialog.spec.ts`
- `frontend/src/views/detailViews.component.spec.ts`
- `frontend/e2e/collaboration-summary.spec.ts`
- `frontend/components.d.ts`（组件自动生成声明）
- 当前授权／任务文档、方案与本记录。

### 实际验证结果

| 检查 | 结果与边界 |
| --- | --- |
| 前端全量 Vitest | 48 个测试文件，328 项通过；包含历史值不被编辑覆盖、摘要权限撤销、旧响应隔离、403／404／500 与重试 |
| vue-tsc 与 Vite build | 通过 |
| check:api-types | 通过，当前开发契约未改变 |
| check:bundle | 通过，最大 JS chunk 273.7 KiB |
| Playwright 摘要与表单测试 | 375、390、768、1280、1440 五个视口全部通过 |
| 截图复核 | 手机与平板实际截图复核；修正手机全屏被全局弹窗边距覆盖的问题 |
| git diff --check | 通过 |

浏览器使用单独的本地 Vite 端口 5178，并拦截 API 返回固定测试数据；这是实际浏览器 UI 验证，不是完整后端端到端验收，也未使用真实业务数据。未运行后端、PostgreSQL、Docker 或远端六项 CI，因为本批次没有后端／契约／数据库变更；这些门禁保留在后续对应阶段和最终验收。

首次浏览器测试中两个手机用例因断言了外层 overlay 而非 dialog 面板的 fullscreen class 失败，修正定位后五项通过。随后截图发现手机尺寸受全局 CSS 限制，修正本组件样式并增加实际宽高断言，再跑五视口全部通过。测试截图禁用动画以避免捕获淡入过程；固定测试数据的 completion_rate 修正为契约中的 0–1 比率。

### Fresh Self-Review

由同一执行 Agent 从 diff 和测试结果进行复查，不称为独立评审。检查点：旧字段保留、无契约变更、目标对象独立授权、无越权来源读取、竞态失效、上下文保留、手机尺寸和安全文本插值。未发现本批次遗留阻断问题；与已批准范围无规格冲突。

### 尚未实现

阶段 2–6 尚未完成：反馈接收人及受理、需求环节人员与新流程、可操作进度区、版本批量关联、邮件投递和旧数据迁移。当前摘要暂展示现有需求信息，人员和精简进度将在后续对应阶段接入。本批次完成不代表整个优化方案或发布候选已完成。

## 阶段 2 接收人与环节人员基础

2026-10-31 用户明确要求阶段通过后直接继续，不逐次等待确认。本阶段代码提交 f4d0818，通过本地门禁后进入阶段 3。

- 开发契约先行增加人员候选、反馈接收人修改／转交、环节人员读取／修改；同步类型与受保护中文接口文档。
- 0005 migration 增加受理字段、接收关系、参与关系与持久事件；历史确认信息保持空，有协作数据时拒绝破坏性 downgrade。
- 反馈接收人须有原有读取资格；受理 CAS 保证单人成功，转交保留原受理事实。
- Requirement SELF 范围增加有效参与人，保留原 owner 读取依据；移出成员不再因参与关系可见。
- 前端接入搜索分页人员选择、接收与转交面板、环节人员面板，新建反馈界面至少选一人。
- 过渡兼容：旧 API 客户端省略 recipient_ids 仍能创建历史形式反馈；显式列表不能为空或含无资格人员。阶段 6 需确认兼容口径，不能声称本阶段所有 API 新建均强制接收人。
- 业务事务内持久保存事件，消费及邮件发送在阶段 5 实现。

实际门禁：后端 378 passed / 1 skipped（未配置 S3）；PostgreSQL 专项 40 passed / 0 skipped；前端 49 文件、331 passed；Ruff、Mypy、构建、类型和 bundle 检查通过。新增测试验证无资格人员失败无残留、并发受理单一胜者、转交保留受理人、参与范围增减、旧 owner 读取、前端冲突不自动重放及账号切换失效旧响应。

仅使用本任务独立 Docker 容器 iterflow-workflow-test-db（127.0.0.1:32768）和 iterflow-workflow-test-redis（127.0.0.1:32769）。upgrade head、alembic check 和隔离旧迁移往返测试通过，没有连接或修改真实数据库。旧测试夹具补入新增依赖表，已发布契约冻结改为校验 v1.8.1 文件摘要，开发契约继续完整 runtime parity。

修改文件范围：collaboration schemas／service／router，反馈 service，需求 repository，entities 和 0005 migration，对应后端测试和文档资源，前端 collaboration API、PeopleSelector、CollaborationPeople、反馈与需求详情、生成类型及组件测试。Fresh Self-Review 属于同一 Agent 自查，检查权限、CAS、旧字段与事务边界。未部署、未执行真实数据库操作或远端 CI。后续新状态流程、批量关联和邮件尚未完成。

## 阶段 3 需求六阶段与进度区

完成：0006 迁移保留旧阶段原始记录，将 PLANNED 映射到 CONFIRMED；旧 DONE/ONLINE 保留完成资格。新需求拒绝 owner 写入，普通创建与反馈转换从 DRAFT 开始，关联版本不改变阶段。确认、设计、开发与验收要求环节资格；范围/验收标准变更使确认失效；版本发布与需求内容修改采用版本→需求锁顺序。步骤条展示六阶段、人员、设计进度、真实确认快照及历史；列表改为参与人/环节筛选，创建页支持环节分工。

主要修改：backend 的 workflow schema/service、requirement/version/feedback/publish-check services、models、0006 migration、开发契约与状态规格；frontend 的 RequirementProgress、需求列表/创建/详情、状态词汇与查询参数；历史迁移、流程、主链及组件测试。

实际测试：后端全量 380 passed / 1 skipped（S3 未配置）；随后新增独立 PostgreSQL 旧数据迁移测试 1 passed，验证旧关系/owner 保留、不伪造确认、不发通知、升级不重复记录及拒绝无审核降级。前端 50 文件 / 333 tests passed；vue-tsc/Vite、类型一致性、bundle、Ruff、Mypy 与 diff check 通过。历史迁移测试改用反射出的历史表模型，避免用新增列写入旧数据库；旧状态文案和 owner 筛选测试随新语义同步。测试使用隔离 Docker 数据库，未连接真实库。

Fresh Self-Review（同一 Agent 自查）：确认普通状态入口不能绕开角色和确认；旧确认内容不被覆盖；历史 owner 仅保留读取；发布前检查内容版本。未发现阶段阻断或与本轮授权冲突。摘要人员/精简进度接入、批量事务、邮件和最终五视口及完整门禁继续在阶段 4–6 完成，不代表发布候选已就绪。

## 阶段 4 版本批量关联

完成：contract-first 增加批量关联接口（1–50 条、去重、请求 UUID、版本与逐条需求 revision）。事务先锁版本，再按 ID 锁需求；完整检查权限、归属、终态和过期修订后才写入，全部成功才提交，版本递增一次、每条需求递增一次；重复旧请求返回 409，不重复关联或审计。界面支持关键词/状态/优先级筛选、当前页多选、跨页保留、已选清单和逐项冲突原因。摘要加入只读阶段/人员信息。

主要文件：version schema/service/router、开发契约与类型、BulkRequirementPicker 及测试、VersionDetailView、RequirementSummaryDialog、协作 PostgreSQL 测试、五视口浏览器用例。

验证：后端全量 383 passed / 1 skipped（S3 待最终隔离门禁）；包含批次回滚、两个版本争抢同组需求、状态不隐式改变、重复请求不重复关系。前端 51 文件 / 334 tests passed，跨页 revision 快照与冲突不重放用例通过；vue-tsc/Vite、Mypy 通过；摘要五视口 Playwright 5 passed。Fresh Self-Review 检查全事务、权限过滤、选择快照与旧异步响应失效，无阶段阻断。请求标识用于审计追踪，revision 是重复写防线；重复提交返回冲突而不伪装成新成功。继续阶段 5。

## 阶段 5 站内通知与邮件

完成：0007 持久偏好/验证挑战/投递记录，确认与验收角色有效唯一索引；业务动作、转需求、版本归属及发布均在原事务写事件。worker 事务扩展事件并去重，重新校验收件资格，站内/邮件独立投递；保留原发布站内通知并避免重复。支持邮箱验证码、偏好、变更地址失效、验证前历史事件不补发、默认 SMTP 关闭及非生产地址白名单。管理员可查看脱敏状态并重试失败记录。新增 Compose worker 定义和运行说明，仅修改配置文件，未启动实际部署。

主要文件：mail schema/router/preferences/delivery services、tasks/mail_worker、0007、config/models、协作/需求/反馈/版本事件接入；MailPreferences 及个人中心；开发契约/类型/中文文档、.env.example、Compose 和 docs/collaboration-notifications.md。

实际验证：后端全量 388 passed / 1 skipped（S3 留待最终门禁）；最终事件操作者修订后版本事务/并发/邮件专项 35 passed。本地 TCP SMTP 收件箱验证真实协议投递、验证码、站内保留、重复消费、地址改变、移除接收人、账号停用、超时结果不确定、稳定 Message-ID、永久失败/手动重试、重试上限和回滚。前端 52 文件 / 335 tests passed；类型/build/bundle、Ruff/Mypy、独立新空库 0001→0007 upgrade 与 Alembic check 均通过。

Fresh Self-Review：不记录 SMTP 原始异常、凭据或验证码；验证码有过期/频率/尝试限制；发信前重新授权；重复请求不自动重放。SMTP 超时仍可能重复，文档明确不保证严格一次投递。旧事件在升级时标记已处理，不补发邮件。无阶段阻断。正式 SMTP、真实地址和站点配置尚未测试，待后续部署授权；继续阶段 6 最终集成、旧数据演练与门禁。


## 阶段 6 最终集成、兼容与本地验收

2026-10-31 完成。本阶段按用户授权自主推进，只使用一次性测试库和测试容器；没有部署到 Preview/Production，没有连接真实数据库，没有 push、merge、tag 或 GitHub Release。

### 集成补齐

- 新反馈 API 与界面统一要求至少一位接收人；阶段 2 的临时旧客户端省略兼容已结束，缺少字段返回 422。历史反馈仍允许无分工。
- 反馈转新需求可以同时配置确认/设计/开发/验收人员，角色校验和创建仍在同一事务。关联已有需求不改写其分工。
- 待确认支持要求补充说明，意见与实际操作者留痕；列表补充当前待处理人，继续取消总负责人输入。
- 邮箱确认更新用户采用 revision CAS；管理员修改邮箱彻底清除原验证与挑战，改回旧地址也须重新验证。验收通过后给关联版本负责人产生待发布邮件待办。
- 备份/恢复脚本将 notification-worker 纳入停写、失败停机和恢复范围。兼容映射、升级顺序、回退限制与真实环境待验项记录于 `docs/collaboration-workflow-upgrade.md`。
- 前端更新到经审计的兼容依赖，Vite 6.4.5、vue-tsc 3.3.14、Vitest 4.1.12，并锁定有修复的传递依赖；后端镜像 setuptools 升至 84.1.0。运行时 Python requirements.lock 未改动。

主要修改文件：开发 OpenAPI/生成类型/中文文档；feedback/workflow/requirement schemas 和 services、需求 repository、邮件与用户管理 service；反馈详情/需求列表/进度组件；后端协作、邮件、旧数据迁移测试；浏览器协作夹具及主链/筛选/个人中心回归；Dockerfile、前端 lockfile、备份恢复脚本和升级说明。

### 最终结果

| 门禁 | 实际结果 |
| --- | --- |
| 后端全量，DeprecationWarning 作为错误 | **396 passed，0 skipped**，包含 PostgreSQL 与真实 S3 往返 |
| PostgreSQL 专项 | 独立运行 56 passed / 0 skipped；新增邮箱变更测试后全量包含全部 **57** 个 PG 用例，另邮件/用户专项 8 passed |
| 前端单测 | **52 文件、335 passed** |
| 浏览器拦截 API 回归 | 最终单独全量 **164 passed**，五视口及 PageHeader 平板断点、抽屉/弹窗、筛选、分页、多选、失败重试、冲突与权限 |
| 真实生产构建浏览器 | **2 个主链用例通过**，真实 PostgreSQL/Redis/Local Storage、独立账号及受限角色；15 个页面 × 五视口检查 |
| 旧数据迁移 | PLANNED、DONE、ONLINE、PAUSED、DRAFT 五种历史场景通过；关系/owner 保留、无虚假确认、无补发、重复 upgrade 无重复迁入记录、拒绝破坏性 downgrade |
| Alembic / 契约 | 新空库 0001→0007；最终 alembic check 无差异，runtime parity 6 passed，历史契约摘要冻结校验通过 |
| 静态与构建 | Ruff check/format、Mypy 104 文件、compileall、API types、vue-tsc、Vite 和 bundle 通过；最大 JS chunk 274.1 KiB |
| 依赖审计 | npm 全量/生产零漏洞；Python 开发环境/生产锁零已知漏洞，本地 iterflow-api 包正常显示非 PyPI 跳过 |
| Docker | API/Web 镜像构建、全新测试 volume 迁移/seed、健康/ready/Web/登录、代理审计 IP 通过；worker 正常运行 |
| S3 | 隔离 SeaweedFS 4.22 真正上传/读取/下载/删除通过 |
| SMTP | 本地 TCP SMTP 测试收件箱；验证、偏好、去重、撤权、邮箱变化、超时不确定、永久失败、重试边界通过；无真实发信 |
| 备份恢复 | 数据库单独备份、数据库+附件备份、校验、故意破坏测试数据后恢复、额外表清除、附件 SHA256、登录和 ready 全通过 |
| 重启持久性 | 恢复后单独重启 worker；Release=1、ONLINE requirement=1、未处理事件=0、投递记录=106、已发送站内记录=52，前后一致 |
| 工作区检查 | git diff --check、修改脚本 bash -n 通过 |

真实浏览器主链包含初始密码修改、受限账号提交反馈、单人受理与转需求、人员分工、两人编辑 409、明确重新加载、版本批量添加、确认/开发/验收、发布前并发变更阻断、重新验收后成功发布、Release、Requirement/Feedback ONLINE、提交人站内通知、审计、SELF 数据范围及各视口。最终浏览器覆盖由 164 个拦截 API 用例和 2 个真实后端用例共同组成，不把拦截数据测试当作真实端到端。

### 测试环境与可追溯日志

测试容器使用 Colima：`iterflow-workflow-test-db`（32768）、`iterflow-workflow-test-redis`（32769）、`iterflow-workflow-test-s3`（34784）；最终数据库为独立新建的 `iterflow_workflow_final`。Docker 演练使用 `/tmp/iterflow-workflow-smoke` 独立副本与同名 Compose project，容器名、volume、端口均与原环境隔离（Web 34781/API 34780/PG 34782/Redis 34783）。SMTP 默认关闭；协议测试仅使用进程内本地测试服务器。

本机详细日志：`/tmp/iterflow-final-backend2.log`、`/tmp/iterflow-final-postgres.log`、`/tmp/iterflow-mail-invalidation.log`、`/tmp/iterflow-final-frontend.log`、`/tmp/iterflow-final-schema-check.log`、`/tmp/iterflow-final-mock-green.log`、`/tmp/iterflow-final-all-browser.log`（含真实主链成功记录和初次组合运行失败）、`/tmp/iterflow-final-smoke2.log`、`/tmp/iterflow-final-backup-drill.log`、`/tmp/iterflow-final-pip-audit.log`、`/tmp/iterflow-final-npm-audit.log`、`/tmp/iterflow-worker-before.log`、`/tmp/iterflow-worker-after.log`。日志是本机临时验收证据，不含真实 SMTP 凭据。

### 失败与修复记录

- Docker 首次构建因隔离容器 DNS 失败，临时 Compose 副本加入 build extra_hosts 后成功；未修改正式部署网络，也未重启共享 Docker。S3 首次 bind mount 因 Colima 无法读取宿主临时文件失败，改为向专用测试容器 docker cp 配置后通过。
- 原依赖审计暴露旧版本问题；npm 10 更新依赖时触发解析器错误，使用 npm 11 在规范化临时路径解析 lockfile，再用项目 npm ci 安装成功并审计归零。运行时安装仍可使用正常 npm ci；Docker 构建已验证。
- 旧浏览器用例仍使用“确认/已确认/已完成”和单选弹窗，已按新语义更新。Element Plus 多选框的隐藏 input 不适合直接 check，改为点击用户可见 label；接收人选择点击可见 select wrapper。没有使用 force click 绕过真实交互。
- 个人中心旧测试未拦截新增邮件设置接口，访问真实测试 API 时出现认证重定向，补齐夹具后 2 项通过。
- 初次组合浏览器运行中，真实主链已通过后启动恢复演练，导致尚在运行的部分静态页面用例遇到服务停机；保留该失败日志。最终将 164 项完整页面回归放在独立 Vite 服务重新运行，全部通过，与真实后端主链的 2 项成功结果分别记账。没有将有失败的组合日志宣称为全绿。

### Fresh Self-Review 与交付边界

同一执行 Agent 重新检查契约、差异、权限、事务、锁顺序、CAS、历史语义、通知资格与备份停写，不称为独立评审。修复了邮箱改回旧地址恢复验证资格的问题以及待发布邮件待办遗漏。未发现本轮范围内未解决的阻断或规格冲突。

阶段 0–6 的本地实现和验收完成。已发布契约/标签/Release 未改，真实数据库和正式 SMTP 未操作。远端六项 CI 未触发，不能把本地对应门禁称为远端 CI PASS；正式合并、版本号、发布与部署仍不在本轮操作范围。真实数据规模迁移耗时和正式邮件连通性保留到目标环境授权验收。


## 后续授权：分支推送与远端六项 CI

2026-10-31 用户授权推送当前分支、运行六项 CI、直接修复失败并记录结果。仅推送 GitHub origin 的 `codex/collaboration-workflow`，不合并、不创建 tag/Release、不部署、不操作真实数据库。推送前工作区干净，HEAD 为 `28dff2f1b8bb1cbc10929ebe469eebe0faa1b279`；origin/master 为 `10f6bfa6410c7836d7d43e402a175d56ad9577c7`。未更改 master 或 Gitee 分支。

CI 的 push 过滤只有 master、phase/**、fix/**，因此使用现有 workflow_dispatch 指定本分支触发完整六项，不调整触发规则或降低门禁。

### 第一轮与修复

[Run 41171078601](https://github.com/dede233/iterflow/actions/runs/41171078601)，attempt 1，检查原始提交 `28dff2f`。结果：frontend、s3、docker_smoke、backup_restore 成功；backend、browser_smoke 失败。首次失败证据保留在该 Run，未将真实代码失败作为基础设施错误重跑。

1. backend：395 passed / 1 skipped（独立 S3 job 已通过），PostgreSQL 57 passed；Ruff 通过，Mypy 报 `collaboration_service.py` 将普通 str 传入 ParticipantOut.role 的 Literal 类型。CI 安装 SQLAlchemy 2.1.6/Pydantic 2.14.2，本地原为 2.0.54/2.13.5；在本地升级到相同版本后以禁用增量缓存的 Mypy 复现同一错误。修复为显式通过 `ParticipantOut.model_validate` 校验数据库结果，保留角色值的运行时限制，不使用 ignore 或降低类型检查。
2. browser_smoke：159 passed / 7 failed，全部集中在批量添加需求。CI 使用 `http://iterflow.example.test:8080`，属于非安全上下文，`crypto.randomUUID` 不可用；弹窗组件在初始化请求 UUID 时抛错。localhost 被浏览器视为可信来源，先前本地验收没有覆盖这一区别。修复增加 `createRequestId`：优先原生 randomUUID，否则使用仍可用的 `crypto.getRandomValues` 生成符合 RFC 4122 v4 格式的随机 UUID，不使用 Math.random。原 revision 快照、请求追踪和批量原子事务保持不变。

本地修复验证：Ruff check/format、Mypy --no-incremental（104 文件）、compileall、schema/契约 13 项通过；前端 52 文件 / 336 项通过（同时覆盖有/无 randomUUID 的批量选择与冲突保持），类型生成一致性、生产构建、bundle 通过。另以生产 bundle 在普通 HTTP 来源下验证 375px/1280px 两种视口：确认 isSecureContext=false、randomUUID 不可用，仍可选择、提交并得到有效 UUID 与原 revision。测试资源从本地构建产物拦截返回、API 使用测试夹具，不依赖真实服务。最初的临时域名解析方案遇到宿主 Surge 代理阻断，已保留日志并停止该次测试；未修改系统 hosts 或代理配置。最终本地证据见 `/tmp/iterflow-remote-ci/http-origin-build.log`、`frontend-fix.log`、`fix-local-tests.log`。

修复涉及协作 service 返回模型构造、前端 requestId 工具及批量组件/回归用例；没有 API shape、数据库 migration 或生产配置变更。后续对修复提交重新运行全部六项 CI，最终结果在下文记录。


### 修复提交完整六项 CI 通过

修复提交：`770d7e532c726e4d4ffdefba9cc540603f7463c7`。已推送到 origin/codex/collaboration-workflow，并重新 workflow_dispatch 全部六项。[Run 41171763589](https://github.com/dede233/iterflow/actions/runs/41171763589)，attempt 1，六项全部 success。

| Job | 结果 | 证据 |
| --- | --- | --- |
| backend | PASS | [124451031505](https://github.com/dede233/iterflow/actions/runs/41171763589/job/124451031505)：395 passed / 1 skipped（S3 独立验证）、PG 57 passed / 0 skipped、Ruff、Mypy 104 文件、compileall、迁移与契约、开发/生产审计、生产锁安装均通过 |
| frontend | PASS | [124451031309](https://github.com/dede233/iterflow/actions/runs/41171763589/job/124451031309)：52 文件 / 336 tests、依赖审计、生成类型、构建、bundle 274.1 KiB 通过 |
| docker_smoke | PASS | [124451031371](https://github.com/dede233/iterflow/actions/runs/41171763589/job/124451031371)：runner 内新 volume 的构建、迁移、seed、health/ready、Web、登录和代理审计 IP 通过 |
| s3 | PASS | [124451031386](https://github.com/dede233/iterflow/actions/runs/41171763589/job/124451031386)：一次性 S3 兼容服务实际往返通过 |
| browser_smoke | PASS | [124451031351](https://github.com/dede233/iterflow/actions/runs/41171763589/job/124451031351)：普通 HTTP 域名、真实生产构建下 **166 passed**，包含两个真实后端主链与全部页面回归 |
| backup_restore | PASS | [124451031356](https://github.com/dede233/iterflow/actions/runs/41171763589/job/124451031356)：runner 临时库及附件的备份、破坏、恢复与校验通过 |

没有关闭测试、降低断言、增加自动重试或使用旧提交的成功替代新提交检查。此次只有一轮代码修复，两个真实问题均已在新提交上重新验证。

### 文档收口与边界

本节记录已经完成的实现提交及其远端证据。提交/推送本次文档收口后，仍需对分支最新 SHA 再运行六项 CI；最终分支检查以 [CI 工作流该分支的实际 Run](https://github.com/dede233/iterflow/actions/workflows/ci.yml?query=branch%3Acodex%2Fcollaboration-workflow) 与最终交付消息中的 SHA/Run 为准，不预写尚未发生的 PASS。

推送目标仅为 GitHub origin 的当前功能分支。核验 origin/master 仍为 `10f6bfa6410c7836d7d43e402a175d56ad9577c7`；未推送 master、未合并、未创建 PR/tag/Release、未部署、未修改真实数据库、未发真实邮件。CI 使用一次性 runner 的数据库、S3、volume 和测试账号。临时本地 HTTP 验证服务已停止，工作区代码修复和所有记录均纳入当前分支。

## master 合并整合

用户授权合并并推送 master；确认 master 为冻结的 10f6bfa。发现源分支与主线存在双数据库和旧逐人确认规则差异，用户明确选择新验收方案后继续整合。兼容取舍、迁移衔接、测试和远端结果集中记录于 `docs/collaboration-workflow-master-merge.md`，此处不预先宣告合并完成。
