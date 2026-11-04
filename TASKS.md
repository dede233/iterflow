# IterFlow Tasks

## 批量操作指引（2026-11-04，已部署 TEST）

- [x] 明确反馈/需求入口、操作用途与阶段、当前页/版本清单范围和50条上限。
- [x] 分步选择、核对、执行及结果展示；具体跳过原因、详情处理入口、关闭/代操作原因和全阻塞处理。
- [x] 保留检查时revision/最新名称与逐条结果，返回调整重新检查；提交中列表刷新不解除锁，未知结果先核对，不自动重放。
- [x] 手机全屏、步骤与底部操作保留、正文滚动；475单测、318合成浏览器、类型/构建/Bundle与生成类型一致性通过。
- [x] 用户授权后仅更新 TEST Web 为 `8d12acf`；API/worker保持 `c0f68e1`、数据库保持 `mysql57_0012`，preflight/prepare/deploy/verify全部通过，无回退。正式 `96ba96e` / `mysql57_0011` 容器及配置保护检查通过，不推送、合并或发布。
- [x] 正常 TEST API及桌面/375px页面验证：需求25确认revision 2→3、需求26缺人跳过且revision 1不变，反馈22受理/23关闭均revision 1→2。实现记录见 `docs/batch-operation-guidance-2026-11-04.md`，部署结果见 `docs/batch-guidance-test-deployment-2026-11-04.md`。
- [ ] 等待用户验收 TEST 批量操作及指引；尚未部署正式环境。

## 列表筛选选择与 TEST 部署（2026-11-04）

- [x] 需求版本/参与人、版本负责人改为可搜索分页选择，保留 URL 数字参数兼容、回显及清空。
- [x] 三个候选接口按对应列表权限与数据范围查询，不依赖人员管理权限，不泄露隐藏版本名称。
- [x] 前端467单测、309合成浏览器、类型/构建/契约一致性、后端84项及 PG/MySQL 双配置新增综合检查通过。
- [x] 最终镜像真实主链、保留 TEST 备份/隔离恢复迁移演练及配套升级通过；API/worker/Web 为 `c0f68e1`，既有迁移 `mysql57_0011 → mysql57_0012`，29 张旧表原列/91 个触发器/附件与逐服务 SMTP 指纹保留。
- [x] 在线 API 原前9项及续验v2的6项检查、桌面需求创建版本和重复号提示、三处筛选搜索/刷新回显/重置、375px筛选抽屉与选择查询及最终 verify 通过。两次主控 guard 失败与在线脚本两次误断言 STOPPED 均保留；仅合成账号创建需求 23/24、版本 22/23，未实际 publish。正式 `96ba96e` / `mysql57_0011` 容器及配置未变，未推送、合并或创建 tag/Release；执行见 `docs/version-flow-test-deployment-2026-11-04.md`。

## 版本入口与自动进度（2026-11-04，本地开发）

- [x] 用户明确需求仅创建版本并关联、稍后发布；版本进度自动汇总。
- [x] 原子创建关联、具体重复号409、表单保留、权限/范围/revision及失败回滚。
- [x] 派生进度统一详情/列表/统计，版本去除重复阶段操作，READY清单可调整，发布保留全量门禁。
- [x] 前端453单测、303合成浏览器、契约文档20项、PG完整593项通过；S3既有1项因本轮未配置而跳过。
- [x] 双MySQL各102项（含备份恢复/三次重启）、最终Docker真实主链2项及文档收口，见 `docs/version-workflow-simplification-2026-11-04.md`。该本地阶段当时未推送、部署或访问真实数据库；后续 TEST 部署见本文件首节。

## Issue #4 与空需求防护（2026-11-04，本地开发）

- [x] 开发契约、双数据库追加迁移、需求富文本及旧文本安全兼容。
- [x] 反馈/需求受限软删除、取消需求重开、多确认人任一人确认。
- [x] 折叠进度快捷操作、上线详情只读、列表及版本清单批量流转。
- [x] 空标题/描述创建、编辑和转需求校验，包含纯空白及不可见字符；正式异常记录保留。
- [x] 前端443单测、275合成API浏览器、契约/内容79项、PG全套及MySQL双配置各91项通过。
- [x] 最终镜像在全新隔离库的真实Docker浏览器主链2项通过，结果收口见 `docs/issue-4-improvements.md`。该本地阶段当时未推送、部署或修改线上数据；后续 TEST 部署见本文件首节。

## 通知邮箱取消绑定（2026-11-03）

- [x] 当前账号解绑接口、个人中心确认窗口、并发保护及契约同步；399 前端单测、18 浏览器用例、PostgreSQL 24 / MySQL 22 项和契约文档 20 项通过。
- [x] 冻结 `f879eaa` 并部署保留 TEST API/worker/Web；29 表与附件保留、桌面/375px 页面、正常 API、跨会话、3 条邮件跳过和 2 条站内通知送达通过。两次应用回退及部署顺序修正已记录，最终健康检查通过，正式未变。见 `docs/email-unbind-test-2026-11-03.md`。

## 流程入口检查（2026-11-03）

- [x] 检查需求六阶段、设计、退回／恢复及反馈受理、版本发布；本地复现并记录 3 类功能缺口和 1 类提示问题，见 `docs/workflow-audit-2026-11-03.md`。
- [x] 完成前端入口修复及本地回归（394 前端单测、123 后端回归、46 浏览器用例）；冻结 `ba5d46e`，通过正常文件上传仅部署 TEST Web，九组在线 HTTPS 检查及桌面／375px 页面验收通过。保留首次脚本预期修正记录，正式未变；执行见 `docs/workflow-fix-test-2026-11-03.md`。

## 邮件通知引导（2026-11-02）

- [x] 按邮箱状态显示引导，知晓状态按账号跨设备保存；保留站内通知与邮件偏好。
- [x] 当前开发契约、双数据库兼容迁移、前后端实现及本地验收。
- [x] 用户授权 TEST 部署：96ba96e / mysql57_0011，备份、隔离恢复迁移演练及 9 项在线检查通过；已验证邮箱页面检查通过。
- [x] 用户确认测试验收没有问题，要求按流程上线正式环境。
- [x] 修复旧浏览器夹具后分支/最终 master 八项 CI 全通过；master 5f5d74e 双远端一致，正式备份演练及 96ba96e / mysql57_0011 升级完成，维护 105.64 秒，数据保留及在线核验 PASS；执行见 `docs/mail-notice-production-2026-11-02.md`。

规则及测试记录见 `docs/mail-setup-notice-2026-11-02.md`。

## 当前协作流程优化

- [x] 用户批准方案并授权开工，采用方案推荐默认值；保留历史发布约束及证据。
- [x] 阶段 0：开发范围与默认规则冻结；新能力契约、迁移及状态规格仍须在各阶段实现前落地。
- [x] 阶段 1：反馈表单精简、版本内需求摘要弹窗（328 单测、五视口浏览器、构建与契约类型检查通过）。
- [x] 阶段 2：反馈多人接收／受理、环节人员和历史读取兼容（后端 378 项、PG 40 项、前端 331 项通过）。
- [x] 阶段 3：需求六阶段、确认／设计／验收记录和进度区。
- [x] 阶段 4：版本批量关联事务及多选界面。
- [x] 阶段 5：站内通知矩阵、邮箱验证／偏好、可靠邮件发送。
- [x] 阶段 6：完整回归、旧数据迁移演练和升级准备（后端 396、前端 335、浏览器 164 + 2 项通过；隔离 Docker/S3/备份恢复通过，未部署）。
- [x] 后续授权：当前分支已推送，修复类型边界与 HTTP 来源 UUID 兼容问题；770d7e5 的远端六项 CI 全通过（Run 41171763589）。文档收口后仍检查最新 SHA；未合并、发布、部署或操作真实数据库。

范围见 `docs/collaboration-workflow-improvement-plan.md`；实际验证记录见
`docs/collaboration-workflow-execution-log.md`。以上勾选只代表已验证结果，
不以实现文件存在代替测试通过。以下保留历史发布任务。
2026-10-23 用户确认开发人员、产品负责人、研发负责人均需完整版本流程权限。独立分支 `codex/version-role-permissions`，范围为默认角色授权、双数据库追加迁移、回归及当前文档，详见 [版本角色权限](docs/version-role-permissions.md)。保留原 DataScope、发布事务、全员开发确认、revision 与审计；已合并并按测试先行顺序部署至 8444/8443，见 [部署记录](docs/version-role-deployment-2026-10-23.md)。

## 当前开发文档

2026-10-13 本地导航文案：将“系统与模块”统一为四字“业务系统”，同步PC/移动入口、页面主标题及开发文档。分支 `codex/business-system-label`；构建/类型检查、11项导航测试和4项浏览器回归通过（含五种屏宽），首次同名标题选择器失败已修正为一级主标题并完整重跑。Fresh Self-Review确认仅文案及既有测试定位调整，无路由、权限、API或数据库变更；本轮未合并master或部署服务器。

2026-10-13 发布记录与版本详情交互增量，见 [抽屉操作与本地验证](docs/release-detail-drawer.md)。

- [x] 补齐发布记录/版本双向抽屉、移动全屏、返回上下文和前端回归。
- [x] 8444多账号实机验收、master八项CI、正式8443升级及两环境Web重启验证；中文记录及手册已同步。

2026-10-12 用户确认：[测试环境保留与更新流程](docs/test-environment-workflow.md)。8444继续保留，后续先测试验收再更新8443。

- [x] 记录环境隔离、保留保护及测试先行的部署规则。
- [x] 2026-10-12 配置测试环境开机恢复，完成四服务冷启动、Nginx异常恢复和数据保全演练，见 [中文记录](docs/master-merge-and-autorecovery-2026-10-12.md)。
- [ ] 配置测试环境定期备份；本次未执行。

2026-10-11 协作版本文档入口：[用户操作手册](docs/user-manual.md)、[接口集成指南](docs/api-guide.md)、[全员开发确认与验收](docs/development-completion.md)、[线上升级记录](docs/collaboration-online-upgrade-2026-10-11.md)、[主分支合并记录](docs/master-merge-2026-10-11.md)。当前契约为 `spec/openapi-development.yaml`；按阶段分工、可选设计、完成与发布全员确认门禁已部署 sx-kc.xyz:8443，实际源 commit 为 `2b37509`。随后按用户授权合入 master；本次未创建新的正式 tag/Release，已发布历史契约和下述发布证据保持不变。

当前追加[全员开发完成发布门禁](docs/development-completion.md)，该文档包含操作与验收；前述阶段记录保留为历史证据。

## 2026-10-10 需求开发、设计协作（本地）

后续用户确认设计可按需跳过，追加 DESIGNING 与阶段分配；当前增量见 `docs/requirement-design-stage.md`，本段为首轮本地记录；后续线上升级见顶部入口。

用户确认保留一名总负责人，可绑定多名开发、多名设计；本轮仅本地实现与验收，范围见 `docs/requirement-collaboration.md`。以下增量不改变历史发布范围记录。

- [x] 开发契约、分工关联、两类基础角色及双数据库追加迁移。
- [x] revision CAS、SELF/RBAC、事务审计和定向站内通知。
- [x] 需求详情分配界面与 PC/Tablet/Mobile 验收。
- [x] 真实 MySQL 5.7、PostgreSQL 回归、迁移和独立备份恢复。
- [x] Fresh Self-Review 与操作说明。
- [x] 2026-10-11 Branch 八项 CI、新 amd64 包、线上追加迁移与双份备份验收。
- [x] 2026-10-11 最新分支八项 CI 全通过后，no-ff 合并 29 个提交并进行文档收口；最终 master CI 以合并记录中的 Checks 入口实际结果为准。
- [ ] 本轮未执行外部独立审查；Fresh Self-Review 为同一 Agent 复查。

> 本次正式发布目标为 `v1.8.1`，Hotfix 外部独立终审 PASS，用户已授权 Final Release + Cloudflare Preview Resume。正式发布成立条件为新的 Release Branch / Final Master 六项 CI PASS、annotated v1.8.1 tag 与正式 GitHub Release；发布事实以最终 master commit、标签和 Release 为准，不提前记录 tag SHA。发布 base：`df9e1ba1a5ee1a4c763098d8e180250f409bedd3`；包、FastAPI、health、Frontend 与当前契约元数据同步 1.8.1，当前契约 `spec/openapi-v1.8.1.yaml`，API shape 不变。v1.8.0 及更早正式标签/Release/契约不可变；本轮只发布已审查的共享 PageHeader 平板响应式修复，随后将正式版本合入独立 Preview 并恢复验收，不部署 Production。证据见 `docs/v1.8.1-release-readiness.md`。

## V1.8 — Version Workspace & Main-Chain Productivity

- [x] Phase 0：正式V1.7基线审计与产品范围冻结；原始分析保留。
- [x] Phase 0：Scope branch六项CI、no-ff merge与final master六项CI。
- [x] Phase 1 — Query Context & Main-Chain Traceability：C4白名单query/安全return_to与C3授权lookup/关系导航。
- [x] Phase 2 — Scoped Relationship Selection：C1分页/搜索/竞态/权限降级/提交前revision。
- [x] Phase 3 — Version Worklist Productivity：C0可见清单筛选、优先级、统计与安全阻塞导航。
- [x] Phase 4 — Regression & Release Readiness：本地门禁、Fresh Self-Review、product branch/master CI与docs-only收口/final CI。

以下为 V1.8.0 阶段收口的历史事实。C2、C5–C16本版DEFER；scroll持久化/全局缓存不做。无新permission/migration/entity、TEAM、状态机或Publish变化。开发阶段版本曾保持1.7.0；本次发布授权同步1.8.0，并仅在final master CI后创建annotated tag/Release；不更新Preview或生产。正式开发 base：`cf9a2fbcd4f045c8dfbc34030b1a3449faa19e8f`。验收见 `docs/v1.8-release-readiness.md`，执行证据见 `docs/v1.8-autonomous-execution-log.md`；同一Agent复查不称外部独立终审。

## V1.7 历史开发清单

以下保留 V1.7 开发、发布准备时的基线与授权记录；其中 Preview SHA 是当时冻结值，不代表当前部署线。V1.7 已正式发布，历史授权不自动延续到 V1.8。

> 正式发布基线：v1.6.0 / `f0aa8475ff081fc963cdd08045d23e383a3c594e`。V1.7 已获用户自主开发授权；正式范围见 `docs/v1.7-plan.md`，事实与执行证据见 baseline audit / autonomous execution log。Phase 0–4开发版本为1.6.0；外部独立终审PASS，现已授权v1.7.0 Final Release并同步包/运行时元数据。Preview保持`33d36d78ab4bedf48835d124f295f1ca8c352eae`，不参与本次发布。V1.6 清单以其正式标签快照为历史依据。

## Phase 0 — Baseline Audit & Scope Freeze

- [x] 核对发布 Git/CI 事实，完成代码/契约/测试审计。
- [x] 冻结 C0/C1/C2/C3/C6/C8/C9；C4删除/C5/C7延期；日期右开、通知focus/visibility方案确定。
- [x] 主链补齐Publish、修正DUPLICATE文字、切换入口文档与清单，保留V1.6历史证据。
- [x] Fresh Self-Review与branch CI通过，no-ff merge/parents核验及docs closeout完成。
- [x] Final master CI通过（37002731061，attempt1六项success，实际HEAD见执行日志）。

## Phase 1 — Product Consistency & Correctness

- [x] C1 package.json → Vite define → UI，开发版本仍1.6.0。
- [x] C3 Feedback literal substring/case-insensitive/trim；建立V1.7契约并切换types/parity，冻结V1.6。
- [x] C8 refresh失败Hash安全回跳，不改变Router mode。
- [x] C9先写Feedback list/Audit list/detail deterministic race tests，仅修已复现页面。
- [x] 本地门禁、Fresh Self-Review、branch六项CI与合并/文档收口完成。
- [x] Final master六项CI（37005356072，attempt1六项success）。

## Phase 2 — Release Query Productivity

- [x] C2 offset-aware `released_from <= released_at < released_before`，允许单边，反向/空区间422。
- [x] version_id/rd.release.view/Version DataScope继续AND，契约、types、分页total一致。
- [x] 本地日期整天→下一日00:00 exclusive，五视口DatePicker/Popper回归。
- [x] 本地门禁、Fresh Self-Review（Fix Loop 1）、branch六项CI与合并/文档收口。
- [x] Final master六项CI（37007834004，attempt1六项success）。

## Phase 3 — Notification Freshness

- [x] focus + hidden→visible刷新未读数；30秒cooldown，无polling。
- [x] logout/account switch/旧响应/focus storm/read-all race回归。
- [x] 本地门禁、Fresh Self-Review（Fix Loop 1）、branch六项CI与合并/文档收口。
- [x] Final master六项CI（37010208267，attempt1六项success）。

## Phase 4 — Regression & Release Readiness

- [x] 完整主链、Publish原子回滚、CAS/40910、RBAC/SELF/ALL、附件、通知、Presence/Conflict/Release/Dashboard与批准候选回归。
- [x] Backend full/PG-only/Ruff/format/Mypy/compileall/Alembic/parity/dev-prod audit/production lock。
- [x] Frontend Vitest/types/build/bundle/npm audits/Playwright与375/390/768/1280/1440。
- [x] 验收文档、Fresh Self-Review、branch六项CI、合并与docs closeout。
- [x] Final master六项CI（37011793000，attempt1六项success），FINAL CLOSED / RELEASE READY。

## 冻结非范围

TEAM、废弃权限删除、trusted IP实现、新migration/permission/entity、状态机/Publish改造、Release回滚、工时/Story Point、独立Mobile、WebSocket/SSE/broker、额外Release搜索、正式发布或Preview部署。

## 2026-10-31 协作优化主线整合

- [x] 核对 master 10f6bfa 无漂移；用户明确取消逐人开发完成门禁。
- [x] 衔接双数据库迁移，保留历史开发确认、主线版本权限与详情增量；本地回归与专项通过。
- [x] 整合基线及 master 合并提交八项 CI 全部通过；合并 SHA 69c2c87、CI 41174648931 和修复结果已记录在 `docs/collaboration-workflow-master-merge.md`。文档收口及 UTC 快照边界修复提交均核验自身 CI，最终运行链接见交付回复。
