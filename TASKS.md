# IterFlow Tasks

## 2026-11-10 小程序品牌管理（本地完成）

- [x] 一个品牌配置微信/支付宝，发布和补记分别选择平台，保留各自时间。
- [x] 原子保存及完整成员revision校验，旧ID/历史/唯一Release/通知保留，无迁移或新权限。
- [x] 511前端、PG与双MySQL、11合成浏览器/2本机真实页面、Docker与静态/构建/契约验证通过，失败和修正留档。
- [ ] 按后续部署授权先更新保留TEST验收，再安排正式更新与九品牌录入。正式纠正前仅添加开电微信一条，其余16平台未添加。
- 记录：`docs/grouped-mini-program-targets-2026-11-10.md`。上一批累计增量已正式上线0ef3e0d/mysql57_0016，master0acf583双远端与八项CI通过；以下旧准备清单为历史。

2026-11-10 用户已验收最新TEST，累计增量上线准备进入八项CI与master无漂移核查；正式目标mysql57_0012→0016、五张新表最小权限。仅推送准备分支，不合并/部署或连接真实数据库；完整范围、升级和回退清单及同SHA证据入口见 `docs/production-preparation-2026-11-10.md`。

2026-11-10 本地移除反馈新建/编辑/详情及桌面和手机筛选的模块入口，所属系统全宽；旧URL模块条件不再生效。普通编辑保留旧模块，仅换系统时清空，后端及历史数据不变。509单测、8浏览器、类型/构建/预算PASS；未部署、推送、合并或操作数据库，详情和首轮定位修正见 `docs/feedback-module-removal-2026-11-10.md`。

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

2026-11-05 业务系统绑定已开发并部署保留 TEST：冻结源码 676e9dd，mysql57_0013；本地前端 491、PG 670+3、MySQL 两配置各 140 及浏览器/契约/真实 Docker 主链通过。备份/隔离迁移/29 表原数据与附件保留/最终健康及正式保护 PASS；在线同系统 6 组与桌面/375px 验收通过，跨系统场景因 TEST 仅一启用系统在线未跑，隔离测试覆盖。旧系统不自动回填，模块管理入口隐藏；正式 5401215/mysql57_0012 不变，不推送/合并/tag/Release。详见 `docs/business-system-binding-test-2026-11-05.md`；等待用户验收。以下准备阶段记录为历史状态。

2026-11-05 用户授权按已确认的单系统版本方案开发业务系统绑定，测试通过后部署保留 TEST 验收，正式环境不变。允许更新开发契约、追加 PostgreSQL/MySQL 5.7 兼容迁移及必要前后端实现；本地仅新建隔离实例，TEST 先备份和迁移演练，保留数据/附件/配置。新版本必须指定系统，关联/迁移/修改/集中提验/发布统一校验；旧版本保留空归属，不自动回填或重写历史。无推送、合并、tag/Release 或正式数据库操作授权。

2026-11-05 下一版本准备已完成代码绑定审查，并在本地隐藏业务系统管理页面的模块入口；构建/类型检查及 5 项合成浏览器测试 PASS，历史模块与反馈选择保留。需求系统交互/校验、版本系统归属仍待补齐；用户已明确一个版本归属一个业务系统、只关联同系统需求；创建、关联、迁移及编辑防绕过校验已纳入准备方案，尚未实现。见 `docs/business-system-binding-audit-2026-11-05.md`。该增量未推送、合并或部署，不修改线上数据。

2026-11-05 本批正式上线完成：源码 5401215、mysql57_0012，维护 116.47 秒；候选/master 八项 CI、隔离演练、TEST 恢复及数据/配置/上线后检查 PASS。master 564916b 双远端一致，无 tag/Release，执行及回退说明见 [正式升级记录](docs/production-deployment-2026-11-05.md)。以下“尚未上正式”均为此前阶段事实；下一版本在独立分支准备业务系统绑定审查与模块入口隐藏。

## 2026-11-05 上线准备

- [x] 用户确认 TEST 需求图片验收通过。
- [x] 移除详情和摘要的复制编号按钮，保留编号展示及原生文本选择。
- [x] 汇总未上线范围，补充 mysql57_0011 → 0012 与回退边界，见 `docs/production-preparation-2026-11-05.md`。
- 本轮八项 CI、最终候选 SHA 与 master 无漂移核对以本轮交付目录 `readiness-result.json` 的实际结果为准；本任务清单不提前标记通过。
- 不合并、不创建 tag/Release、不切换正式环境、不访问正式数据库；正式备份/演练留待正式授权阶段。

## 版本集中提交验收（2026-11-04，已部署TEST）

- [x] 用户选择省去开始开发点击，保留验收人独立确认。
- [x] 专用版本提验接口、双 revision/关联/权限/人员/内容/设计校验；每条事务、实际流转记录及通知，不放开普通需求列表跳级。
- [x] 三步弹窗支持待开发与开发中混选，快捷说明、缺人补齐及全量重检；结果不确定时不自动重放。
- [x] 491前端单测、19新增/43相关浏览器、PG全量659项（S3集成1项跳过）、MySQL双配置各60项、22文档契约及类型/构建/静态检查通过；Docker实际集中提验→独立验收→自动READY、Release=0通过。失败修正、复查与定点清理见 `docs/version-submit-acceptance-2026-11-04.md`。
- [x] 用户授权后配套更新TEST API/worker/Web为`b9b2cc1`，数据库仍`mysql57_0012`；部署四阶段、30表/会话/附件保留及正式保护全部PASS。
- [x] 在线补人重检、直接提验、内容/设计/CAS阻塞、指定验收人确认及自动READY通过；保留版本25/26与需求27–31，未实际发布。首次自动化下拉遮挡及安全续跑记录见 `docs/version-submit-test-deployment-2026-11-04.md`。
- [ ] 等待用户验收TEST；不部署正式、不推送或合并。

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
