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

### 主线合并完成

按用户授权取消旧逐人开发确认门禁，并完成双数据库整合、历史数据兼容与回归修复。master 合并前确认 10f6bfa 无漂移；no-ff 合并并推送 `69c2c877cfee27b4142f03ea00559238f0cdc489`。其 [CI 41174648931](https://github.com/dede233/iterflow/actions/runs/41174648931) attempt 1 八项全部通过（原六项 + MySQL standard/portable）；完整 Job ID、测试计数和修复记录见 `docs/collaboration-workflow-master-merge.md`。本次文档收口仍验证其自身 CI；未发布、部署或操作真实数据库。

## 2026-10-31 转需求默认确认人

用户要求：转需求时，需求确认人默认当前账号，允许修改。

- `FeedbackDetailView.vue` 在打开转换弹窗时按当前登录身份初始化确认人；向人员选择器提供显示名称，避免远程选项未加载时只显示数字 ID。保留更换、清空和单选能力，不在编辑过程中重新覆盖用户选择。
- 当前账号没有 `rd.requirement.view` 时不预填不合格人员，沿用后端人员读取资格校验。关联已有需求继续发送空 participants，不改变已有分工；直接新建需求和其他环节默认值不变。
- 需求仍从待确认开始，不生成自动确认记录；无 API、数据库、权限或状态机改动。方案中旧的“任何环节均不默认创建人”已按本次用户指令更新。
- 本地验证：详情组件、需求 API、详情权限三组既有回归共 **38 项通过**；`npm run build` 的 Vue/TypeScript 检查及 Vite 构建通过；`git diff --check` 通过。组件回归有 jsdom XHR AggregateError 控制台输出，但测试断言和进程退出均通过；本次没有将它作为真实后端联调证据。
- Fresh Self-Review：默认值只在打开时设置，提交仍读取可编辑的 convertRoles；不会恢复已清空值，不改变 LINK_EXISTING 或隐式执行确认。无规格冲突。
- 仅本地修改，未推送、合并、部署或连接真实数据库；未重新运行全量后端及远端 CI。

## 2026-10-31 紧凑可折叠需求进度

- 用户要求：进度区域不遮挡需求详情，减少占用并支持收缩。`RequirementProgress.vue` 改为默认收起的摘要栏，显示阶段、环节人员或版本、待确认提示；长人员名称截断，完整名称在展开区域可见。
- 展开后六阶段按桌面六列、平板三列、手机两列展示，保留原流转按钮、确认弹窗、人员管理与审计记录。人员与历史区分别折叠，减少重复信息。按钮支持 Enter/Space、焦点样式、aria-expanded/aria-controls；切换需求或登录身份时收起，revision 刷新不改变折叠选择。
- 沿用 Vue/Element Plus 和现有样式变量；没有改 API、权限、状态机、CAS、数据库或摘要弹窗。需求摘要仍不显示进度。
- 修改文件：进度组件及其既有组件测试，四个受折叠操作影响的浏览器用例文件，以及方案和执行记录。
- 本地测试：进度和详情组件 **28 项通过**；页面头部、详情抽屉和全页面响应式 **48 项浏览器回归通过**。视觉检查后补充详情间距及独立人员折叠，再跑 **11 项需求页屏宽回归、2 项进度组件回归和 Vue/TypeScript + Vite 构建**，全部通过。11 种宽度覆盖 375、390、767、768、820、1024、1199、1200、1201、1280、1440px；检查收起高度、需求详情在视口内、六阶段、键盘展开收起和无横向溢出。
- 已检查 375px 收起和 1440px 展开截图，保存在本地 deliverables/iterflow/2026-10-31/requirement-progress-collapse。详情组件测试仍有前次记录的 jsdom XHR 控制台输出；断言通过。本轮浏览器使用隔离 mock API；真实后端 release 用例仅补充展开动作，未重新执行真实主链。
- Fresh Self-Review：按钮仅控制展示，不触发写接口；权限变化会清空旧响应并收起，确认提交仍携带当前 revision、不重放冲突。无规格冲突、无未解决的本次布局缺陷。
- 已完成本地实现及验证；未推送、部署、修改正式环境或真实数据库。

## 2026-11-02 环节人员合入进度卡片

- 用户要求：将独立人员区域合并到进度卡片，在待开发时选择人员。`RequirementProgress.vue` 移除独立人员折叠区；待确认卡片设置确认人，待开发卡片展示设计、开发、验收人员并在进入该阶段后提供选择入口。后续非终态仍可调整，待验收卡片另提供验收人入口；只读、无编辑权限及终态隐藏编辑入口。
- 新增 `RequirementPeopleDialog.vue`，使用现有人员选择器与 participants 接口。打开时读取人员及 revision；保存局部环节时保留其他环节，设计/开发多选、确认/验收单选，保存不推进阶段。409 保留输入、不自动重试，手动重新加载后才能按新数据调整。账号或权限变化清除旧数据；保存期间避免重复提交。
- 回归发现原进度折叠监听在同一需求对象刷新时也触发，导致保存后意外收起；改为分别监听需求 ID 与身份，revision 刷新保留展开状态。
- 修改文件：上述两个组件、组件类型声明、进度组件测试、新增人员弹窗测试与浏览器用例，以及方案/本记录。没有 API、后端、状态机、权限或数据库改动，无规格冲突。
- 本地门禁：前端 **53 文件 / 349 tests PASS**，Vue/TypeScript 与 Vite 生产构建 PASS，`git diff --check` PASS。包含局部人员保存不覆盖其他环节、revision 取值、409 保留选择、权限切换、只读及终态入口限制。既有详情组件测试仍有 jsdom XHR AggregateError 控制台输出，断言及退出码通过。
- 浏览器：375/768/1440px 三组实际选择设计、开发、验收人员并保存、卡片回显、原确认人保留、状态不变的 mock API 回归通过；另 **11 项需求页响应式回归 PASS**，覆盖 375–1440px、折叠键盘交互、详情可见与无横向溢出。首轮组件测试暴露上述收起问题，修复后通过。浏览器用例前两次分别定位到了 Element Plus 输入占位层与上一选择器退出中的选项；改为点击实际选择框并按 aria-controls 定位所属列表，保留全部业务断言，无强制点击或自动重试。
- Fresh Self-Review：人员全量提交保留未编辑环节、读写使用同一 revision 快照、提交失败不触发 updated；后端继续强制 RBAC/DataScope、终态及 CAS。已检查桌面卡片与手机弹窗截图。
- 本轮仅本地开发与隔离 mock 验证；未运行远端 CI 或真实主链、未推送合并、未部署测试/正式环境、未修改真实数据库或发送邮件。

## 2026-11-02 进度卡片按钮换行适配

- 用户反馈“调整确认人”按钮换行。原因是网格使用窗口断点，桌面窄详情抽屉仍强制六列，按钮允许自动折行。
- `RequirementProgress.vue` 改用进度内容容器宽度控制列数：达到 300/456/924px 时依次两/三/六列，更窄时单列。人员按钮使用单行及紧凑左右间距，保留完整文案、点击入口和默认折叠行为；不以文字裁切或缩小字号隐藏问题。
- 扩展已有人员浏览器回归，覆盖独立详情页和列表详情抽屉的 320/375/768/1200/1440/1800px 共 **12 项 PASS**。检查按钮文字实际单行且未越出按钮或卡片，同时保留人员选择保存、确认人保留、阶段不变的原断言。另 **11 项需求页响应式回归 PASS**，Vue/TypeScript + Vite 构建 PASS，git diff --check PASS。
- 已目视检查 375px 手机与 1800px 桌面抽屉截图。证据保存在本地 `deliverables/iterflow/2026-11-02/people-button-layout`。本轮仅隔离 mock 浏览器验证，没有重跑真实业务主链或远端 CI。
- Fresh Self-Review：仅布局样式及既有测试覆盖调整，API、人员保存、权限、状态机、数据库均无变化；无规格冲突或未解决的本次显示问题。未推送、合并或部署，测试环境仍为上次 c86e7b3 Web。

## 2026-11-02 确认人员前置校验、多名验收人和自动安排人员

用户连续要求：修复确认内容时提示“请先分配对应环节人员”的流程问题；验收人可以多选、单人通过即可；需求确认后自动弹出人员选择窗口。

- 原因：进度组件把管理员资格直接视为可执行所有环节操作，即使未指定有效确认人也显示可提交入口。现在前端与后端一致：先设置有效确认人；普通人员本人确认可不填说明，管理员代操作必须填写原因。确认内容不要求预先安排设计、开发或验收人员，后端门禁未放松。
- 确认成功从 DRAFT 进入 CONFIRMED 后，等待详情刷新和确认弹窗关闭动画，再自动打开设计／开发／验收人员窗口。仅本次成功操作触发一次；确认失败、无人员编辑权限、切换需求或身份、后续重新确认不触发。窗口从接口读取最新 revision，保留已有分工；关闭不会撤销确认，保存不会自动开始开发，卡片保留再次打开入口。
- ACCEPT 支持多人；新建需求、反馈转新需求和人员调整入口全部使用多选。任意一名有权限的有效验收人员可推进 TESTING → DONE，记录实际操作者和当时人员快照。提交验收对所有验收人员生成待办通知，邮件遵循验证和偏好；并发确认只有一次成功，另一请求返回 409，不重复写成功记录或事件。CONFIRM 仍单人，不新增角色或权限。
- 先更新开发契约，再同步类型与内置接口说明。首次真实数据库验证发现此前“不需要迁移”的判断不成立：数据库还有限制 CONFIRM/ACCEPT 单人的唯一约束。新增 PostgreSQL `0012_multiple_acceptance` 与 MySQL `mysql57_0010`，只将唯一约束范围缩至 CONFIRM；不删除或改写人员历史，不补造验收记录。MySQL 保留唯一索引、修改生成列表达式。已有多人有效验收时拒绝降级；单人及额外停用记录可往返迁移且数据不变。
- 文件范围：进度组件和人员选择入口、后端人员校验与 ORM、双数据库追加迁移、开发契约及生成说明、前后端回归、AGENTS／当前方案／状态规格／手册补充。已发布契约与历史迁移保持不变。

验证结果（全部使用本次新建隔离实例，未接入真实数据库）：

| 门禁 | 实际结果 |
| --- | --- |
| 前端全量组件／单元测试 | 53 文件，362 PASS；既有 jsdom XHR 控制台输出仍存在，断言与退出码通过 |
| Vue／TypeScript、Vite 生产构建、生成类型一致性 | PASS |
| 后端全量（含真实 PostgreSQL、HTTP 主链、发布回滚／并发、邮件本地接收器、旧数据升级） | 427 PASS；1 项 S3 集成因未配置隔离 S3 服务 SKIP，不计为通过 |
| MySQL 5.7 standard：协作、实际发布主链、旧数据迁移 | 16 PASS |
| MySQL 5.7 portable：关闭 large_prefix／strict、空 sql_mode、+08:00、binlog | 同组 16 PASS |
| 浏览器人员多选、回显、单行按钮与窄抽屉 | 320/375/768/1200/1440/1800px，页面及抽屉共 12 PASS，mock API |
| 浏览器缺失确认人 → 设置确认人 → 确认 → 自动安排人员 | 375/1440px 共 2 PASS；手机关闭后保持待开发，桌面使用确认后的 revision 保存且不自动开始开发，mock API |
| Ruff、mypy、git diff --check | PASS；mypy 108 个源文件 |

修复和首次失败证据：前端新增参数化测试最初把空数组展开为缺失参数，改为对象行；真实 PG/MySQL 首轮分别 2 项失败暴露数据库单人约束，追加迁移后全过；全量后端首轮 1 项失败暴露内置契约说明未同步，重新生成后 427 PASS；扩展自动弹窗保存的浏览器测试首轮桌面选择器把父弹窗嵌入 has 条件导致超时，修正相对定位后两项全过，未强制点击或跳过断言。初始截图捕获过渡动画重叠，改为确认窗口关闭完成后再打开人员窗口，并目视检查最终 375/1440px 截图。

Fresh Self-Review（同一 Agent）：确认和人员保存仍是独立显式事务，最新 revision、不重放冲突；切换身份／对象不会打开旧请求的人员窗口；多人验收未改变发布事务、实际验收审计、权限和数据范围；数据库层继续拒绝多名有效 CONFIRM，迁移往返和拒绝有损降级均实际验证。无未解决的本次业务失败或规格冲突。

证据目录：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-02/confirmation-and-multi-acceptance`。本轮只本地提交；未推送、合并、跑远端 CI、部署或修改真实数据库，未通过真实邮箱发送测试邮件。测试环境仍是此前 a5333d5 Web。后续部署本功能需同时升级 API／worker 和 Web，并在停止写入、备份后执行对应追加迁移；不能仅替换 Web。存在多人有效验收数据时不能直接退回旧应用和单人约束。

## 2026-11-02 测试部署演练发现并修复 MySQL 启动检查

- 用户授权将人员选择／多人验收改动部署到保留测试环境，正式环境不动。停止测试写入并完成数据库、附件备份后，在新建内网 MySQL 副本恢复并演练升级。
- 首次恢复因 socket ping 命中初始化临时服务而 TCP 尚未就绪失败；改为带认证的 TCP SELECT 1 就绪检查后恢复成功，原始失败证据保留。
- 实际部署 CLI 演练暴露 `mysql_preflight` 仍要求 `mysql57_0009`，导致升级至 0010 后检查失败。此前回归仅直接执行 Alembic，未覆盖 CLI 的升级后校验；实际保留测试库此时尚未迁移。
- 修复运行时只接受 0010，迁移预检允许从 0009 升级，保留旧版本兼容路径和 completion trigger 校验。扩展迁移回归，实际调用部署 CLI 并重复执行，检查旧 head 的运行时拒绝及新 head 的完整校验。
- 新建本地隔离 MySQL：standard **17 PASS（35.73s）**、portable **17 PASS（36.78s）**，覆盖协作、多人验收、完整发布主链、旧数据迁移和 preflight。首次本地容器启动退出 139，测试连接失败已保留；重建／启动并确认认证 TCP 就绪后测试通过。Ruff、mypy 与 diff check PASS。
- 未调整发布事务、权限、数据范围或已发布契约；未修改正式环境。后续实际部署结果另记，不将本节作为部署成功证明。

### 测试环境部署完成

部署源码 `cd1f7ee24b933b0adafb1b9513cfa033194deae7`，2026-11-02 11:47:18 +08:00 完成 TEST API／worker／Web 和 MySQL 0010 升级。隔离恢复迁移、29 表内容与附件保留、服务健康及正式环境不变核验通过。实际浏览器自动选人／两名验收人保存和真实 HTTPS 单人验收、旧 revision 409、唯一实际操作者记录通过。专用需求 ID 17 保留待发布，未发布版本。完整备份、首次失败及最终验证见 `docs/test-deployment-multiple-acceptance-2026-11-02.md`。

## 2026-11-02 邮箱验证码同行布局及重新验证入口

- 用户要求：验证码输入框在左、发送按钮在右，同一行；已有验证邮箱时，点击“重新验证”后才展示该行。
- `MailPreferences.vue` 使用可收缩输入框与不换行按钮，手机端两者高至少 44px。未验证邮箱直接显示该行，尚未申请验证码时输入框禁用；已验证邮箱默认只显示重新验证入口，展开不发起请求。验证成功后收起，身份变化或重新加载时重置展开状态。待验证提示与“验证邮箱”操作一同按展开状态显示。
- 保留现有发送、验证码确认、revision、错误后保留输入和邮件偏好逻辑；没有 API、权限、数据库、通知发送策略改动，无规格冲突。
- 验证：现有邮件设置／个人中心组件 **5 PASS**，个人中心浏览器回归 **2 PASS**（含五个屏宽），Vue／TypeScript 与生产构建 PASS，diff check PASS。首次 npm 命令因 shell PATH 中默认 Node 路径失效未启动，改用已安装 Node 22.23.2 后通过。
- 实际浏览器在本地内存 mock API 预览，320／375／768／1440px 检查输入框位于左侧、按钮在右且同高、文字单行、页面无横向溢出；另实际操作已验证隐藏 → 点击重新验证 → 模拟申请／填写 → 验证成功收起，全部通过。未发送真实邮件或连接真实数据库。
- Fresh Self-Review：仅展示状态及布局；展开不自动申请验证码，旧请求仍受 identity／sequence 保护，成功确认和用户切换清理展开状态。证据：本地 `deliverables/iterflow/2026-11-02/mail-code-inline`。未推送、合并或部署，测试环境仍为 cd1f7ee。

## 2026-11-02 验证码布局测试部署

- 按用户最新授权，将 `1923a22` 仅 Web 更新到保留测试环境，完成时间 12:05:43 +08:00；正式环境未变更。
- 镜像源码／config／公网产物一致性、API/Web 健康和 ready、worker 运行全部 PASS。正式容器及配置、测试 API/worker/DB/Redis 和邮件配置前后核对一致；未执行数据库操作。
- 实际测试页面完成已验证默认隐藏 → 点击重新验证展开 → 刷新收起检查；375px 输入框与按钮同一行、44px 高、无横向溢出，PASS。没有发送邮件或重新提交验证。
- 完整范围、证据与回退记录：[验证码布局测试部署](test-deployment-mail-layout-2026-11-02.md)。无规格冲突或未解决部署问题；本次不运行远端 CI、不推送合并、不部署正式环境。

## 2026-11-02 重新验证前隐藏通知邮箱输入区

- 用户补充要求已验证邮箱在点击“重新验证”前，也隐藏“通知邮箱”标签和输入框。
- `frontend/src/components/MailPreferences.vue` 将通知邮箱表单项移入既有 `showVerification` 条件块，与验证码行一同展开／收起；未验证时直接展示，当前邮箱及验证状态文字保留。无 API、数据库或验证请求逻辑变更。
- 既有 MailPreferences／ProfileView 测试 5 PASS；Vue／TypeScript 与 Vite 生产构建 PASS；git diff --check PASS。此轮未重跑浏览器或邮件投递测试。
- Fresh Self-Review：仅调整模板条件范围，确认成功和用户切换仍沿用既有收起逻辑，无规格冲突或未解决问题。本轮未部署；测试环境仍为 1923a22，正式环境未操作。
