# DEVELOPMENT.md

2026-11-10 本地补齐支付宝小程序发布目标，并按平台联动字段：PC Web 仅显示访问地址，两种小程序仅显示 AppID，保存清空不适用字段；修复编辑误带只读字段。追加 PG 0018_alipay_targets / MySQL mysql57_0016 扩展平台约束，历史快照保留，存在支付宝记录拒绝降级。509 前端、51 PG 专项+17迁移回归、双 MySQL 各18+2、6浏览器及静态/类型/构建通过；仅任务隔离数据库测试，未部署/推送/合并或修改保留数据库。详情、首轮浏览器定位修正与回退边界见 `docs/alipay-release-targets-2026-11-10.md`。

2026-11-10 按钮对齐与布局修复已部署保留TEST：仅Web更新到0c12952，API/worker仍097b2dd，数据库沿用mysql57_0015。本轮509单测、最终镜像13浏览器/138静态文件、16部署保护及构建类型预算PASS；preflight/prepare/deploy/verify均PASS，线上桌面/375px按钮、筛选重置和摘要底栏通过，无回退。正式5401215及TEST非Web容器/配置保持不变，无数据库命令或业务写入，无推送/合并/tag/Release。执行与Web回退见 `docs/ui-action-alignment-test-2026-11-10.md`，等待用户验收。

2026-11-10 按用户指定 ui-ux-pro-max 完成本地按钮对齐修复：版本清单按钮统一尺寸、筛选底边对齐，并修复共享卡片/页头/底栏及重复间距；13专项+109相关浏览器、类型/构建/预算通过，覆盖19页面多尺寸与真实本机页面。修复前2项预期失败用于复现；新增几何断言补齐原验收缺口。未部署TEST/正式、推送/合并或操作数据库；结果与限制见 `docs/ui-action-alignment-2026-11-10.md`。

2026-11-10 UI与发布覆盖已部署保留TEST：API/worker/Web冻结097b2dd，数据库仍mysql57_0015（35表/110触发器）。preflight/prepare/deploy/verify、完整停写数据和附件保留、逐服务SMTP及正式保护PASS；本轮509前端/构建/类型/预算通过。合成需求36/版本29验证正常发布仅记录A、后补B/C、唯一Release13/上线时间不变、历史版本28记录保留及权限/CAS/旧入口拒绝；桌面1040px弹窗、375px、空footer和内层双蓝框修复通过。无迁移/权限修改/真实回库，正式5401215/mysql57_0012不变且未连接正式数据库，无推送/合并/tag/Release。新语义已写入，禁止无条件退回旧目标门禁应用；执行与回退边界见 `docs/ui-coverage-test-deployment-2026-11-10.md`。以下未部署结论为此前本地阶段历史。

2026-11-10 本地修复选择器/文本输入的内外双重蓝框：焦点统一显示在外层 wrapper，其他键盘焦点提示保留。6 项浏览器、构建/类型及桌面/375px 实测通过，未部署/推送/合并；详见 `docs/ui-modal-form-fix-2026-11-10.md`。

2026-11-10 人员及列表筛选下拉框空底栏已本地优化：footer 按需提供，正常加载完隐藏，分页/失败/空结果提示保留。6 项浏览器、4 种人员响应状态及构建/类型检查通过；未部署/推送/合并。详见 `docs/ui-modal-form-fix-2026-11-10.md`。

2026-11-10 用户反馈需求弹窗过窄，本地将新建/编辑需求最大宽度统一为 1040px，保留小屏自适应及独立滚动底栏；49 项浏览器、构建/类型检查和三宽度长文本实测通过。未部署/推送/合并，记录追加于 `docs/ui-modal-form-fix-2026-11-10.md`。

2026-11-10 用户反馈新建需求弹窗底栏遮挡，已检查并修复需求/反馈/版本新建及从需求创建版本共四个入口，改为独立滚动内容和正常布局底栏；业务规则不变。509 单测、113 项唯一浏览器、6 组本机弹窗及 8 组整页表单验收、构建/类型/预算检查 PASS。仅本地，未部署、推送或合并；原因、上一轮验收缺口和失败修正见 `docs/ui-modal-form-fix-2026-11-10.md`。

2026-11-10 用户确认按视觉基础、需求、版本、表单/移动端、首页顺序实施 UI 优化，本地已完成。前端 509 项、226 项唯一分段浏览器、构建/类型/产物预算/契约生成检查及真实页面 8 组表单布局通过；保留业务流程、权限、CAS 和发布语义，无 API/迁移变更。仅本机登录及已有合成数据只读验收，未部署 TEST/正式、推送或合并；失败、修正及证据见 `docs/ui-refinement-2026-11-10.md`。

2026-11-10 发布覆盖调整本地完成：恢复正常版本发布，发布时可选已发布小程序/PC、发布后多选补记；目标不作为上线门槛，原Release/上线时间/通知及旧实际记录保留。无新增迁移/权限。PG全量702 PASS/1 S3条件跳过及最终36项，前端507，双MySQL各16，83个相关浏览器及真实Docker双宽度主链PASS；失败/修正见docs/release-coverage-2026-11-10.md。本轮未部署/推送/合并/tag/Release或访问真实数据库，TEST仍2b9fd16/mysql57_0015、正式5401215/mysql57_0012（既有记录，未重查）。


2026-11-10 用户确认发布目标仅用于记录发布覆盖范围：版本仍通过原需求验收/系统/权限/CAS检查正常发布；发布时可选已发布小程序或PC，发布后可多选补记，不再以目标全部完成为上线门槛。授权本地调整开发契约、前后端和隔离测试；既有成功记录、原Release/上线时间/通知保留，旧未完成计划不推断已发布。无自动部署、推送、合并或真实数据库操作。本轮记录见docs/release-coverage-2026-11-10.md。此规则替代2026-11-09目标计划门禁。


2026-11-09 多目标发布本地开发完成：目标目录、首次/补发/显式重新发布、实际登记与历史快照、首次部分成功冻结和全部完成原子上线、目标记录筛选及旧版本兼容均完成。PG全量697 PASS/1条S3条件跳过，前端506、浏览器361唯一用例、双MySQL各158唯一用例及补充隔离/验证、契约/静态/构建通过；分段失败与修正完整保留。PG0017_target_releases/MySQL0015、35表/110触发器，仅新建隔离资源。未推送、合并、部署、tag/Release或访问真实数据库，TEST/正式仍以既有记录为准。源分支codex/multi-target-release；详见docs/multi-target-release-2026-11-09.md。

2026-11-09 用户授权完成多小程序发布目标方案开发，基于已通过八项 CI 的 5d79a48 在 codex/multi-target-release 本地实施。允许目标目录、首次/补发/显式重新发布批次、逐目标实际登记、首次全部完成复用主链发布事务及冻结门禁、历史目标查询和必要的双数据库追加迁移/开发契约；沿用原 RBAC/DataScope、版本/批次/目标 revision、版本→批次→目标→需求锁序。原 Release 仍每版本一条，补发不重开需求或重复全局通知；旧数据不推断目标。仅新建本任务隔离实例验证，不部署任何环境、不推送/合并/tag/Release、不连接或修改真实数据库。此前 5d79a48 的准备/CI 结论只适用于原候选，不自动覆盖本增量。设计、执行与兼容见 docs/multi-target-release-2026-11-09.md。

2026-11-09 用户确认 TEST 验收无问题，授权将业务系统绑定、更新公告及详情归属/最近操作整批做上线准备，推送当前开发分支运行完整八项 CI 并核对双远端 master 无漂移，修复准备中发现的门禁问题并记录。仅准备，不合并 master、不创建 tag/Release、不切 TEST/正式、不连接或修改真实数据库。正式最近已验证 5401215/mysql57_0012，TEST de8ab75/mysql57_0014；正式基线由既有部署记录提供，本轮不冒称重新核查服务器。范围、0012→0014 及最小运行权限/回退边界见 `docs/production-preparation-2026-11-09.md`，实际同 SHA 八项与最终 Git 结论见该文档指定交付目录中的 `readiness-result.json`。

2026-11-09 详情归属与最近操作已部署保留 TEST：API/worker/Web 冻结源码 de8ab75，数据库仍 mysql57_0014。preflight/prepare/deploy/verify、32 张表停写完整行/账号会话/公告/审计及附件保留、运行账号实际查询、逐服务 SMTP 与正式保护均 PASS；线上反馈/需求/版本详情、需求抽屉/摘要和 375px 验收通过，需求 1 展示最近 10 条且完整历史 17 条保留。只读取已有合成记录，正常登录会话除外；无迁移、权限修改、业务写入或回退。正式 5401215/mysql57_0012 未变，未连接正式数据库；无推送/合并/tag/Release。详细结果、限制和应用回退见 `docs/detail-system-activity-test-2026-11-09.md`，等待用户验收。

2026-11-09 用户授权将详情业务系统归属与最近10条操作部署保留TEST验收，正式环境不变。配套更新API/worker/Web，保持mysql57_0014，不迁移/seed/恢复数据库或修改权限；保留账号、审计、公告、附件和SMTP配置。先核对两环境基线与残留任务、备份和冻结镜像校验，再短暂维护切换、合成账号及桌面/375px验收。只应用回退，无推送/合并/tag/Release。执行见`docs/detail-system-activity-test-2026-11-09.md`。

2026-11-06 用户追加详情业务系统归属及最近操作人/最近10条操作。本地已完成反馈/需求/版本详情、抽屉及需求摘要统一归属和可折叠操作记录；按对象查看权限/DataScope读取最小审计摘要，不截断完整历史，不新增权限或迁移。500前端、23浏览器（截图复查7项）、PG12项、双MySQL各1项及静态/构建/契约通过；本轮无部署、推送、合并或线上数据库访问。执行及限制见`docs/detail-system-activity-2026-11-06.md`。

2026-11-05 更新公告 TEST 恢复及在线验收完成：冻结8f4e7db/mysql57_0014，补齐两张公告表最小DML权限并修正代理恢复操作顺序。草稿/发布权限、图片大图、重要弹窗、账号跨会话已读、发布后修正保留已读及375px布局PASS；最终健康和正式保护PASS。合成公告id=1保留供验收。正式5401215/mysql57_0012未变，未连接正式数据库；无推送/合并/tag/Release。失败与修正详见`docs/update-announcements-test-2026-11-05.md`。

2026-11-05 用户进一步明确授权将更新公告部署保留 TEST。冻结源码 8f4e7db，配套 API/worker/Web 与 mysql57_0013 → 0014；先备份、隔离恢复迁移和数据/附件保留证明，再切换及合成账号验收。正式 5401215/mysql57_0012 保持不变，不连接正式数据库，不推送/合并/tag/Release。多目标发布仍仅方案。本次执行见 docs/update-announcements-test-2026-11-05.md。

2026-11-05 用户确认实施 IterFlow 自身更新公告：草稿/发布、富文本截图、账号已读同步、轻量提醒和重要公告弹窗；允许必要开发契约和追加双数据库迁移，仅本地隔离验证。本轮不自动部署任何环境、推送/合并或创建 tag/Release。公告独立于业务 Version/Release，默认仅启用内置 SUPER_ADMIN 管理。多小程序发布另按“首次目标全部完成才整体上线、之后新增补发批次”整理方案，尚未实现该发布语义变更。见 `docs/update-announcements-2026-11-05.md` 与 `docs/multi-target-release-plan-2026-11-05.md`。

2026-11-05 用户授权按已确认的单系统版本方案开发业务系统绑定，测试通过后部署保留 TEST 验收，正式环境不变。允许更新开发契约、追加 PostgreSQL/MySQL 5.7 兼容迁移及必要前后端实现；本地仅新建隔离实例，TEST 先备份和迁移演练，保留数据/附件/配置。新版本必须指定系统，关联/迁移/修改/集中提验/发布统一校验；旧版本保留空归属，不自动回填或重写历史。无推送、合并、tag/Release 或正式数据库操作授权。

2026-11-05 下一版本准备已完成代码绑定审查，并在本地隐藏业务系统管理页面的模块入口；构建/类型检查及 5 项合成浏览器测试 PASS，历史模块与反馈选择保留。需求系统交互/校验、版本系统归属仍待补齐；用户已明确一个版本归属一个业务系统、只关联同系统需求；创建、关联、迁移及编辑防绕过校验已纳入准备方案，尚未实现。见 `docs/business-system-binding-audit-2026-11-05.md`。该增量未推送、合并或部署，不修改线上数据。

2026-11-05 本批正式上线完成：源码 5401215、mysql57_0012，维护 116.47 秒；候选/master 八项 CI、隔离演练、TEST 恢复及数据/配置/上线后检查 PASS。master 564916b 双远端一致，无 tag/Release，执行及回退说明见 [正式升级记录](docs/production-deployment-2026-11-05.md)。以下“尚未上正式”均为此前阶段事实；下一版本在独立分支准备业务系统绑定审查与模块入口隐藏。

2026-11-05 当前整批上线准备见 [准备与回退清单](docs/production-preparation-2026-11-05.md)。用户确认需求图片验收通过，本次保留编号展示并移除复制按钮；运行开发分支八项 CI 并核对 master，无正式切换或数据库操作。

2026-11-04 本地追加版本集中提交验收：版本需求清单可将已确认、实际已完成开发的待开发需求直接提交验收，并与开发中需求一起逐条处理。缺少开发/验收人员时可按原权限补齐，保存后重新检查；当前内容确认、设计、人员、权限/范围、版本及需求 revision 与关联门禁由后端强制执行。快捷提交须说明原因，不补造开始开发记录，验收人独立确认与专用发布事务保留。无迁移或新权限；已部署保留TEST，API/worker/Web为`b9b2cc1`、数据库仍`mysql57_0012`，在线主链及环境保护复核PASS，正式不变。范围及本地验证见 `docs/version-submit-acceptance-2026-11-04.md`，部署及在线结果见 `docs/version-submit-test-deployment-2026-11-04.md`。

2026-11-04 批量操作指引已部署保留 TEST，待用户验收：反馈/需求列表与版本需求清单统一为“选择操作和记录 → 核对并执行 → 查看结果”，明确范围、可执行/跳过原因、实际动作及逐条结果；保留未知结果待核对和提交期间快照。仅 TEST Web 更新为 `8d12acf`，API/worker 保持 `c0f68e1`、数据库保持 `mysql57_0012`；preflight/prepare/deploy/verify、桌面及375px在线验收通过，未触发回退。正式 `96ba96e` / `mysql57_0011` 容器和配置保护检查通过。本次不变更接口、权限、状态机或数据库，不推送、合并或发布。实现及本地验证见 `docs/batch-operation-guidance-2026-11-04.md`，部署及在线结果见 `docs/batch-guidance-test-deployment-2026-11-04.md`；以下配套部署为此前阶段记录。

2026-11-04 用户追加需求管理版本/参与人及版本管理负责人改为下拉选择，并授权本轮增量部署保留 TEST。候选接口按列表权限和可见对象关系过滤，支持关键词、分页与安全回显；不新增角色或迁移。前端467单测/309合成浏览器及三套隔离数据库验证通过。TEST API/worker/Web 已更新为 `c0f68e131b5fd8232c70e4b237b78bfd93d8f72b`，既有迁移 `mysql57_0011 → mysql57_0012` 完成；备份、隔离恢复迁移演练、29 张旧表原列/91 个触发器/附件保留、逐服务 SMTP 指纹、在线 API、桌面/375px 页面及最终 verify 均 PASS。部署和验收脚本的失败、修正及证据全部保留，线上仅用合成账号创建需求 23/24、版本 22/23，未实际发布版本。正式保持 `96ba96e` / `mysql57_0011`，容器和配置未变；本轮未推送、合并或创建 tag/Release。实际结果见 `docs/version-flow-test-deployment-2026-11-04.md`。

2026-11-04 本地阶段的后续增量为需求创建版本并原子关联、重复版本号精确提示及版本自动汇总进度。用户明确只创建关联、稍后发布，并取消重复的版本开发/测试人工推进；规则及隔离验证见 `docs/version-workflow-simplification-2026-11-04.md`。该阶段当时未部署，相对 Issue #4 不新增迁移；后续 TEST 部署结果见上段。

2026-11-04 Issue #4 本地阶段完成七项需求及空需求防护，规则、双数据库迁移与实际验证见 `docs/issue-4-improvements.md`。该阶段当时未推送、合并或部署；后续 TEST 部署结果见上段，下文更早阶段保留为历史记录。

2026-10-31 历史开发阶段为授权的协作流程优化，范围及默认规则见
`docs/collaboration-workflow-improvement-plan.md`，阶段结果见
`docs/collaboration-workflow-execution-log.md`。下文 v1.8.1 发布目标为历史记录；
该阶段包版本暂不变，当时不执行正式发布或真实数据库升级。
2026-10-23 用户确认开发人员、产品负责人、研发负责人均需完整版本流程权限。独立分支 `codex/version-role-permissions`，范围为默认角色授权、双数据库追加迁移、回归及当前文档，详见 [版本角色权限](docs/version-role-permissions.md)。保留原 DataScope、发布事务、全员开发确认、revision 与审计；已合并并按测试先行顺序部署至 8444/8443，见 [部署记录](docs/version-role-deployment-2026-10-23.md)。

## 当前开发文档

2026-10-12 当前主线已合入反馈关联名称修复；8443/8444产品源为3fe3a42。保留测试环境已配置开机恢复和异常恢复，操作与验证范围见 [中文合并与运维记录](docs/master-merge-and-autorecovery-2026-10-12.md)。后文2026-10-11部署事实保留为历史，不代表当前产品源。

2026-10-12 后续部署规则：[测试环境保留与更新流程](docs/test-environment-workflow.md)。保留8444独立测试环境，每次更新先通过测试验收，再按对应授权更新8443正式环境；必要门禁失败时停止正式更新。

2026-10-11 协作版本文档入口：[用户操作手册](docs/user-manual.md)、[接口集成指南](docs/api-guide.md)、[全员开发确认与验收](docs/development-completion.md)、[线上升级记录](docs/collaboration-online-upgrade-2026-10-11.md)、[主分支合并记录](docs/master-merge-2026-10-11.md)。当前契约为 `spec/openapi-development.yaml`；按阶段分工、可选设计、完成与发布全员确认门禁已部署 sx-kc.xyz:8443，实际源 commit 为 `2b37509`。随后按用户授权合入 master；本次未创建新的正式 tag/Release，已发布历史契约和下述发布证据保持不变。

当前追加[全员开发完成发布门禁](docs/development-completion.md)，该文档包含操作与验收；前述阶段记录保留为历史证据。

需求协作已按用户要求追加可选设计阶段与按阶段分配，当前操作与门禁见 `docs/requirement-design-stage.md`。

2026-10-10 用户授权的本地增量：一名总负责人、多名开发、多名设计及定向站内通知，见 `docs/requirement-collaboration.md`。开发契约仍为 `spec/openapi-development.yaml`；新增迁移不改历史发布快照。本地测试通过不构成线上部署事实。


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

## 1. 开发目标

本次正式发布目标为 `v1.8.1`，Hotfix 外部独立终审 PASS，用户已授权 Final Release + Cloudflare Preview Resume。正式发布成立条件为新的 Release Branch / Final Master 六项 CI PASS、annotated v1.8.1 tag 与正式 GitHub Release；发布事实以最终 master commit、标签和 Release 为准，不提前记录 tag SHA。发布 base：`df9e1ba1a5ee1a4c763098d8e180250f409bedd3`；包、FastAPI、health、Frontend 与当前契约元数据同步 1.8.1，当前契约 `spec/openapi-v1.8.1.yaml`，API shape 不变。v1.8.0 及更早正式标签/Release/契约不可变；本轮只发布已审查的共享 PageHeader 平板响应式修复，随后将正式版本合入独立 Preview 并恢复验收，不部署 Production。证据见 `docs/v1.8.1-release-readiness.md`。

完成标准不是“代码已生成”，而是：

`docker compose up -d`

后可以通过浏览器实际完成：

`登录 -> 提交反馈 -> 转正式需求 -> 加入版本 -> 状态流转 -> 发布版本 -> 反馈显示已上线`

并支持 PC 与移动端核心操作。

## 2. 目录

```text
.
├── AGENTS.md
├── DEVELOPMENT.md
├── TASKS.md
├── README.md
├── docs/
├── spec/
├── backend/
├── frontend/
├── tools/
└── deploy/
```

### 规格
- `docs/`：V1.5 已发布主文档 PDF/Word、V1.6 历史证据、V1.7 历史证据、V1.8 规划和基线审计
- `spec/openapi-development.yaml`：当前开发契约，增加受保护的接口文档及当前账号文档资格标记。
- `spec/openapi-v1.8.1.yaml` 及更早契约：已发布冻结快照；开发快照不是新 Release，包版本暂保持 1.8.1。
- `spec/status-machines.md`：状态机

## 3. 本地环境

macOS / ServBay 本机启动脚本和目录整理约定见 [tools/README.md](tools/README.md)。
主项目保存在 `~/Developer/work/iterflow/`，人工临时 worktree 与备份分别集中到
`~/Developer/worktrees/iterflow/` 和 `~/Developer/backups/iterflow/`；上传文件归属
主项目的 `data/uploads/`，不依赖旧开发 worktree。

建议：
- ServBay（可直接提供 Python、PostgreSQL、Redis 与 Nginx/Caddy），或 Docker Engine / Docker Desktop
- Docker Compose v2（使用容器开发时）
- Python 3.12+
- Node.js 20+ 或 22+
- npm 10+
- PostgreSQL/Redis 可使用 ServBay 或 Docker
- 本地对象存储默认使用 LocalFileStorage，不要求启动 S3 服务

## 4. 环境变量

本地 Python/Vite 分进程开发在根目录复制：

```bash
cp .env.example .env
```

Docker Compose 一键部署则复制到 `deploy/.env`；不要误以为根目录 `.env` 会自动被 `deploy/docker-compose.yml` 读取。

生产/共享环境禁止继续使用示例密码。

重要变量至少包括：
- DATABASE_URL
- REDIS_URL
- JWT_SECRET
- JWT_ACCESS_TTL_MINUTES
- JWT_REFRESH_TTL_DAYS
- STORAGE_DRIVER
- LOCAL_STORAGE_PATH
- S3_ENDPOINT
- S3_ACCESS_KEY
- S3_SECRET_KEY
- S3_BUCKET
- S3_REGION
- INIT_ADMIN_USERNAME
- INIT_ADMIN_PASSWORD

本地开发使用 `STORAGE_DRIVER=local` 与 `LOCAL_STORAGE_PATH=./data/uploads`。相对路径以项目根目录解析；物理路径不作为业务主数据，数据库只保存 `storage_key` 等文件元数据。

切换到标准 S3 API 时设置 `STORAGE_DRIVER=s3` 以及 `S3_*` 变量。`S3Storage` 使用 boto3 标准 S3 API，不绑定特定厂商，可连接 SeaweedFS、RustFS、AWS S3 或其他 S3 Compatible Object Storage。

业务代码只依赖 `StorageService`，不得直接调用 boto3 或厂商 SDK。文件表保存 `original_name`、`storage_key`、`size`、`mime_type`、`sha256`、`storage_driver`、`created_at`、`created_by`，业务关系使用 `file_id`。

LocalFileStorage 的 `storage_key` 必须由系统生成；实现需拒绝绝对路径、`..` 和解析后逃逸存储根目录的路径。附件下载先经过 IterFlow 后端鉴权；S3 模式可以在鉴权后签发短时有效的 signed URL。

Docker Compose 另需 `POSTGRES_PASSWORD` 用于初始化 PostgreSQL；该变量不会传入 API。`.env.example` 中所有凭据均留空，启动前必须显式填写。Docker 内的 `DATABASE_URL` 需使用服务名 `db`。

## 5. 基础设施启动

```bash
docker compose -f deploy/docker-compose.yml up -d db redis
```

若 PostgreSQL 与 Redis 已由 ServBay 启动，可以跳过此步并在 `.env` 中填写本机连接地址。生产 Compose 包含 `db`、`redis`、一次性的 `migrate`/`seed`、`api` 与 `web`；S3 自托管服务不是强制依赖。

检查容器：

```bash
docker compose -f deploy/docker-compose.yml ps
```

## 6. Backend

进入：

```bash
cd backend
```

建议虚拟环境：

```bash
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

安装：

```bash
pip install -e ".[dev]"
```

Migration：

```bash
alembic upgrade head
```

初始化管理员和基础权限：

```bash
python -m app.cli.seed
```

首次管理员登录并修改密码后，在「系统设置 → 业务系统」创建至少一个业务系统及模块。反馈表单只显示已启用的选项；停用不会删除历史关联。修改现有系统或模块时需提交当前 `revision`，冲突返回 409。

启动：

```bash
uvicorn app.main:app --reload --port 8000
```

健康检查：

```text
GET http://localhost:8000/health
```

API 文档：

```text
http://localhost:8000/docs
```

健康检查：

```text
GET http://localhost:8000/health  # 仅进程存活
GET http://localhost:8000/ready   # PostgreSQL / Redis / 当前 Storage Driver 就绪
```

## 7. Frontend

```bash
cd frontend
npm install
npm run dev
```

本地 API 不在默认的 `8000` 端口时，可在 `frontend/.env.local` 设置 `ITERFLOW_API_PROXY_TARGET=http://127.0.0.1:8001`，Vite 会将 `/api` 代理到该地址。

构建：

```bash
npm run build
```

如果构建失败，不进入下一阶段。

## 8. 测试

Backend：

```bash
cd backend
pytest -q
```

代码检查：

```bash
ruff check app tests
```

类型检查：

```bash
mypy app
```

Frontend：

```bash
cd frontend
npm run build
```

Vitest：

```bash
npm run test
npm run check:api-types
npm run check:bundle
```

## 9. Docker 全量启动

配置 `deploy/.env` 后一键启动（从根目录复制 `.env.example`）：

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

最终应做到：
- Web 可访问
- API 健康
- DB migration 成功
- Redis 可用
- LocalFileStorage 可读写；配置 S3 时 S3Storage 可连接
- 登录可用
- 主链路可用

`migrate` 与 `seed` 自动执行，失败则 API 不启动。首次管理员密码仅首次创建时必需；已有管理员时可留空。生产 Web 默认只绑定回环地址，公网接入必须经 HTTPS 反向代理。详见 `docs/production-runbook.md`。

## 10. 数据库变更

所有 schema 修改必须生成 Alembic migration。

示例：

```bash
alembic revision --autogenerate -m "add xxx"
alembic upgrade head
```

提交 migration 前：
- 检查 upgrade
- 检查 downgrade
- 在空库验证
- 在已有测试数据的库验证

## 11. OpenAPI 变更

V1.7 Phase 1 从V1.6契约建立V1.7快照（历史事实）；历史 V1.8 Final Release 从 `spec/openapi-v1.7.yaml` 复制建立 `spec/openapi-v1.8.yaml`，无业务shape变化，切换 runtime元数据、生成类型与parity；旧文件冻结。`spec/openapi-v1.5.yaml` 当前已有发布后补充，不继续将其当作增量文件；历史正式契约以 `v1.5.0` 标签为准。API 修改流程：

1. 先提出并评审当前开发契约，明确字段与错误行为。
2. 更新 Backend schema/router/service，并校验运行时 OpenAPI 与当前开发契约一致；`backend/scripts/sync_openapi.py` 当前使用 V1.8.1 契约，避免覆盖历史文件。
3. 使用 `frontend/package.json` 中与当前开发契约一致的 `generate:api-types` 生成 TypeScript DTO。
4. 增加/更新测试，并执行 OpenAPI parity、`npm run check:api-types` 和构建门禁。

核心契约变化需要用户确认。

## 12. revision 并发开发规范

核心更新请求必须传 revision。

正确示例：

```sql
UPDATE rd_requirement
SET title = :title,
    revision = revision + 1,
    updated_at = NOW(),
    updated_by = :user_id
WHERE id = :id
  AND revision = :revision;
```

影响行数为 0：
- 查询当前对象
- 返回 409
- 前端显示冲突界面
- 不自动重试覆盖

反馈转需求、需求迁版和版本发布等跨表事务也必须先执行带 revision 条件的原子更新；禁止用“先读取 revision、再普通 ORM 赋值”替代条件更新。

## 12.1 状态终态规则

- `Version.RELEASED` 只能由 `POST /versions/{id}/publish` 成功发布事务产生。
- 普通 Version 状态接口禁止设置 `RELEASED`；`READY -> TESTING` 必须填写原因并审计。
- `Requirement.ONLINE` 只能由成功发布事务产生。
- `DONE -> DEVELOPING` 仅限所属 Version 尚未发布，必须填写原因并审计。
- V1.5 MVP 的 publish 不接收 result 参数，成功后固定写入 `Release.result = SUCCESS`。

## 13. Redis 编辑提示

建议键：

```text
edit_lock:{entity_type}:{id}
```

当前 Redis 值包含：
- `user_id`
- `display_name`
- `active_at`（开始或最近一次 heartbeat 时刷新）

实体类型为 FEEDBACK、REQUIREMENT、VERSION；当前实现 TTL 为 600 秒，接口见 `backend/app/api/v1/editing.py`。Phase 1 已在 Feedback/Requirement/Version 实际打开编辑时 start、编辑期间每 120 秒 heartbeat、关闭/保存/离页时 end；只浏览详情不 start，提示他人编辑但不强制排他。

仅用于协作提示，不影响业务写入权限。

## 14. 日志

每个请求应带 request_id。

业务审计和运行日志分离：
- 运行日志：应用运行、异常、性能
- 审计日志：用户业务操作前后值

禁止日志记录密码、Token、Secret。

## 15. Git/提交建议

每个阶段小步提交，例如：

```text
feat(auth): implement login and refresh token
feat(feedback): add feedback create/list/detail
feat(requirement): add optimistic locking
feat(version): add requirement assignment
feat(release): implement release transaction
fix(concurrency): return latest revision on conflict
```

不要把全部模块一次塞进一个不可审查提交。

## 16. Agent 阶段报告格式

每个 Task 阶段结束回复：

```text
阶段：
完成：
修改文件：
数据库 migration：
API 变化：
测试：
已验证场景：
未解决：
需要确认：
下一步：
```

若测试未通过，明确写“未完成”，不得标记 Done。
