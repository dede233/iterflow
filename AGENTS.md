# AGENTS.md

2026-11-10 用户确认按视觉基础、需求、版本、表单/移动端、首页顺序实施 UI 优化，本地已完成。前端 509 项、226 项唯一分段浏览器、构建/类型/产物预算/契约生成检查及真实页面 8 组表单布局通过；保留业务流程、权限、CAS 和发布语义，无 API/迁移变更。仅本机登录及已有合成数据只读验收，未部署 TEST/正式、推送或合并；失败、修正及证据见 `docs/ui-refinement-2026-11-10.md`。

2026-11-10 用户授权修复本机登录并重置本机 admin、密码存本机凭据文件。本机 ServBay PostgreSQL/Redis 已恢复，专用 schema 经备份及隔离恢复演练由 0004_integrity 升级至 0017_target_releases；原 21 表数据及附件保留、旧活动会话撤销。启动脚本改为当前 head 校验并关闭本地 SMTP；真实登录及 1440px/375px 发布时勾选和发布后补记小程序/PC 通过，合成版本 2/3 留供查看。仅本机变更，未连接 TEST/正式或推送合并；详细失败、修正、验证及回退边界见 docs/local-login-repair-2026-11-10.md。


2026-11-10 发布覆盖调整本地完成：恢复正常版本发布，发布时可选已发布小程序/PC、发布后多选补记；目标不作为上线门槛，原Release/上线时间/通知及旧实际记录保留。无新增迁移/权限。PG全量702 PASS/1 S3条件跳过及最终36项，前端507，双MySQL各16，83个相关浏览器及真实Docker双宽度主链PASS；失败/修正见docs/release-coverage-2026-11-10.md。本轮未部署/推送/合并/tag/Release或访问真实数据库，TEST仍2b9fd16/mysql57_0015、正式5401215/mysql57_0012（既有记录，未重查）。


2026-11-10 用户确认发布目标仅用于记录发布覆盖范围：版本仍通过原需求验收/系统/权限/CAS检查正常发布；发布时可选已发布小程序或PC，发布后可多选补记，不再以目标全部完成为上线门槛。授权本地调整开发契约、前后端和隔离测试；既有成功记录、原Release/上线时间/通知保留，旧未完成计划不推断已发布。无自动部署、推送、合并或真实数据库操作。本轮记录见docs/release-coverage-2026-11-10.md。此规则替代2026-11-09目标计划门禁。


2026-11-09 多小程序发布已部署保留TEST：API/worker/Web冻结源码2b9fd16，数据库mysql57_0014→0015（35表/110触发器），现有运行账号仅新增三表最小DML。预检/镜像/停写备份/隔离恢复迁移/原32表完整数据结构与附件保留/逐服务SMTP及正式保护PASS；首次相对路径误判自身任务在DDL前自动恢复原应用，独立续部署同快照重备份后成功，无真实数据库恢复或降级。合成需求35/版本28完成首次A/B、补发C、唯一Release12、三条目标记录及筛选，权限/CAS、旧版本15未推断目标、桌面/375px通过；最终verify PASS。正式5401215/mysql57_0012未变且未连接正式数据库，无推送/合并/tag/Release。执行、异常、限制与DDL后前向处置见docs/multi-target-release-test-2026-11-09.md，等待用户验收。

2026-11-09 用户授权将多小程序发布部署保留TEST，验收首次发布、后续补发和发布记录，正式环境不变。冻结产品2b9fd16，配套API/worker/Web及mysql57_0014→0015、既有运行账号三张新增业务表最小DML。先核对两环境和残留任务、备份旧应用/数据库/附件/配置，隔离恢复迁移并证明全部旧数据保留，再短暂TEST维护切换和合成账号验收。保留现有账号、公告/已读、审计、附件与逐服务SMTP；不seed、不恢复/降级真实数据库、不推送/合并/tag/Release。DDL启动后失败停写前向处理，不盲目回旧应用。宝塔仅正常文件上传与短控制命令。执行见docs/multi-target-release-test-2026-11-09.md。

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

## 当前开发授权 2026-10-31

2026-11-05 下一版本准备已完成代码绑定审查，并在本地隐藏业务系统管理页面的模块入口；构建/类型检查及 5 项合成浏览器测试 PASS，历史模块与反馈选择保留。需求系统交互/校验、版本系统归属仍待补齐；用户已明确一个版本归属一个业务系统、只关联同系统需求；创建、关联、迁移及编辑防绕过校验已纳入准备方案，尚未实现。见 `docs/business-system-binding-audit-2026-11-05.md`。该增量未推送、合并或部署，不修改线上数据。

2026-11-05 本批正式升级完成：master 564916b 双远端一致，冻结源码 5401215 的候选/master 八项 CI 全通过；正式 API/worker/Web 已更新到 5401215，数据库 mysql57_0012。用户授权演练通过后立即短暂维护，并允许为演练短暂停止 TEST；隔离演练、TEST 数据保留恢复、正式停写备份和迁移均 PASS。正式维护 116.47 秒（13:11:38–13:13:34），迁移 6.45 秒；29 张旧表原数据、91 个触发器、附件、邮箱/JWT 配置保留，健康/日志/公开入口及恢复基线更新 PASS。未恢复或降级数据库、未创建 tag/Release。执行及回退边界见 docs/production-deployment-2026-11-05.md。用户授权上线后准备下一版本，先审查业务系统与反馈/需求/版本绑定并隐藏业务系统内模块入口；在 codex/business-system-bindings 本地开展，不自动部署下一版本或修改线上数据。

2026-11-05 用户确认 TEST 需求图片验收通过，要求移除“复制编号”按钮、保留需求编号展示，并把此前尚未上正式环境的改动一起做上线准备。授权推送当前开发分支以运行八项 CI、修复门禁问题并核对 master 无漂移；本轮不合并 master、不创建 tag/Release、不切正式环境、不修改正式数据库。正式基线仍以已部署 `96ba96e` / `mysql57_0011` 为准；准备范围、迁移及回退边界见 `docs/production-preparation-2026-11-05.md`。既有部署记录保留历史事实，不代表移除按钮已部署 TEST。

2026-11-04 用户明确授权将版本集中提交验收增量部署保留TEST，验证直接提验、人员补齐与验收流程，正式环境不变。产品冻结`b9b2cc1088a2d8bc335c72153212ef31cb0dd5a1`，配套更新TEST API/worker/Web；数据库保持`mysql57_0012`，不执行migration、seed或数据库恢复，保留账号/会话、数据、附件、逐服务SMTP与恢复配置。先预检保护基线、备份旧应用及TEST数据，再短暂切换及合成账号在线验收；只回退应用，不回库。宝塔继续仅正常文件上传及短控制命令，不传Base64/长脚本；不推送、合并或创建tag/Release。执行见`docs/version-submit-test-deployment-2026-11-04.md`。

2026-11-04 集中提验增量已部署保留TEST：API/worker/Web冻结源码`b9b2cc1`，数据库仍`mysql57_0012`。preflight/prepare/deploy/verify均PASS，30表完整行（含会话）、结构及附件切换保留、逐服务SMTP及正式保护通过；维护尝试至部署PASS记录窗口23:05:30–23:06:29，未回退。合成账号完成缺人补齐重检、2条待开发直接提验、内容/设计/CAS阻塞、开发人验收403及指定验收人通过，版本25自动READY、版本26保留阻塞案例，均无实际发布；桌面/375px验收通过。首轮多选下拉遮挡导致自动化STOPPED，只读核对后仅续跑未执行步骤，无重复写入。正式`96ba96e`容器/配置未变，不连接正式数据库，无迁移、恢复、推送、合并或tag/Release。详细结果及应用回退见`docs/version-submit-test-deployment-2026-11-04.md`；等待用户验收。

2026-11-04 用户追加版本集中控制进度，并明确选择“省去逐步点击：已确认需求可直接提交验收，仍由验收人确认通过”。授权本地实现版本清单集中提验与缺人补齐后重检：允许CONFIRMED/DEVELOPING进入TESTING，CONFIRMED直提须填写说明；当前内容确认、有效开发/验收人员、设计已完成/不需要、实际操作者资格与既有管理员代操作原因继续强制。新增专用版本清单提验接口及开发契约，按版本/需求revision与有效关联逐项事务执行；普通状态与原批量接口保持相邻流转，版本仍自动汇总，不自动验收或发布，不伪造中间步骤。本次无新migration/permission，仅新建隔离数据库测试；不部署、推送、合并或操作真实数据库。执行见 `docs/version-submit-acceptance-2026-11-04.md`。

2026-11-04 该集中提验增量本地验证完成：491前端单测、19新增/43相关浏览器、PG全量659项（S3集成1项未配置跳过）、MySQL双配置各60项、22文档契约及静态/构建检查通过；最终Docker实际页面链验证CONFIRMED→TESTING→验收人DONE、版本自动READY且Release=0，服务健康与源码哈希核验通过。本轮隔离资源已定点清理，失败与修正证据保留于上述执行记录。尚未部署或推送，TEST及正式环境不变。

2026-11-04 用户明确授权将批量操作与指引优化部署到保留 TEST 验收，正式环境不变。产品冻结 `8d12acff1043d8ff0da3fa46e7c13552408be794`，仅更新 TEST Web；API/worker、数据库、附件和邮箱配置保留，不执行迁移或数据库恢复。先核对两环境基线与残留任务、备份旧Web镜像和配置，再切换、验收及验证正式保护。宝塔只使用正常文件上传与短控制命令；本轮不推送、合并或创建tag/Release。执行见 `docs/batch-guidance-test-deployment-2026-11-04.md`。

2026-11-04 该批量指引增量已部署 TEST：Web `8d12acf`，API/worker仍为`c0f68e1`、数据库沿用`mysql57_0012`。预检、旧Web备份、新镜像151文件校验、切换及验收后保护复核均PASS；19:00:24–19:00:39完成切换检查，无回退。合成账号需求25确认/26缺人跳过、反馈22受理/23带原因关闭、版本24清单范围和零可执行指引、桌面/375px页面及API revision核对通过，数据保留供用户验收。正式容器/配置/首页保持`96ba96e`基线；无数据库命令、迁移、恢复、正式升级、推送或合并。详细证据与回退方式见上述部署记录。

2026-11-04 用户反馈批量操作不清晰、指引不明确，授权优化现有反馈/需求列表及版本需求清单的批量操作交互。范围为明确范围与选中数、动作说明、分步核对、具体阻塞指引和成功/失败/跳过结果；保留原权限、人员门禁、revision、逐项事务和不自动重试，不改后端契约或数据库。本次先本地实现与合成 API 验证，不自动部署、推送、合并或修改真实数据；执行见 `docs/batch-operation-guidance-2026-11-04.md`。

2026-11-04 用户明确授权将本轮 Issue #4、需求创建版本、重复版本号提示及版本自动进度部署到保留 TEST 验收，随后追加需求列表的版本/参与人、版本列表的负责人由 ID 输入改为选择。允许补充遵守原查看权限和 DataScope 的筛选选项接口，更新开发契约及必要前后端实现，无新增迁移；保留测试环境需从 mysql57_0011 升级既有 mysql57_0012，先完成备份、隔离恢复迁移演练和数据保留检查。仅更新 TEST API/worker/Web，保留账号、业务数据、附件、SMTP及恢复配置；正式环境不变，不推送、合并或发布。迁移 DDL 启动后失败不得盲目恢复旧应用或自动降级/恢复数据库，须保留停写现场并前向处置；宝塔继续仅允许正常文件上传及短控制命令。执行见 `docs/version-flow-test-deployment-2026-11-04.md`。

2026-11-04 本轮已部署保留 TEST：API/worker/Web 冻结源码 `c0f68e131b5fd8232c70e4b237b78bfd93d8f72b`，MySQL 从 `mysql57_0011` 升级既有 `mysql57_0012`。备份、隔离恢复迁移演练、29 张旧表原列/91 个触发器/附件保留、逐服务 SMTP 完整指纹、在线 API 和桌面/375px 页面验收及最终 verify 均 PASS；维护标记至部署 PASS 的记录窗口为 17:40:33–17:44:12（219.43 秒）。两次部署主控 guard 失败与在线验收脚本两次误断言 STOPPED 均保留，修正仅涉及外部控制/验收脚本，不改产品。线上仅使用合成账号 `ceshi002` 创建需求 23/24、版本 22/23，未实际 publish。正式仍为 `96ba96e` / `mysql57_0011`，容器及配置未变；未推送、合并或创建 tag/Release，未降级或恢复真实数据库。执行见 `docs/version-flow-test-deployment-2026-11-04.md`；下述本地阶段“未部署”和此前 TEST 来源为当时历史记录，不代表当前环境。

2026-11-04 用户追加三项反馈并明确确认：从需求仅创建版本并关联，稍后发布；版本号重复给出精确提示；开发/提交验收/验收只在需求操作，版本自动汇总进度。允许在本地实现原子创建关联、开发契约及派生进度；版本非终态手动推进改为自动汇总，READY作为可发布提示但清单可通过原双revision接口调整，仅RELEASED/CANCELED冻结。此规则替代历史手动版本开发/提测/READY及READY名单冻结；发布仍保留全部需求和内容确认检查、权限、CAS、锁与原子事务，ONLINE仅由实际发布产生。不部署、推送、合并或访问真实数据库，隔离测试完成后本地提交；实施见 `docs/version-workflow-simplification-2026-11-04.md`。

2026-11-04 上述版本精简已完成本地实现：前端453单测/303合成浏览器、契约文档20项、PG593项及补充主链5项、双MySQL各102项、最终Docker真实主链2项通过；既有S3条件用例本轮未配置端点而跳过。首轮夹具/基础设施失败及修正均保留，portable使用同镜像同配置直接mysqld通过连续3次重启/备份恢复。相对4912afb不加迁移；TEST/正式未动，未推送或合并，任务临时资源定点清理，最终镜像与证据保留。

2026-11-04 用户明确选择先开发 Issue #4（1103需求反馈），本轮实施需求富文本、反馈/需求软删除、取消需求重开、多人需求确认、折叠进度快捷操作、上线后隐藏写操作、列表批量流转。按讨论建议实施，允许更新开发契约与必要的双数据库追加迁移，仅使用本任务新建隔离实例测试；不部署、推送、合并或修改真实数据库。取消重开及多人确认替代下文历史“终态不重开/CONFIRM 单人”限制，其他主链、权限、revision、事务和审计规则不变。实施计划及实际结果见 `docs/issue-4-improvements.md`。

2026-11-04 Issue #4 七项及用户追加的空需求防护已完成本地开发：443前端单测、275合成浏览器、79契约/内容、PostgreSQL完整后端、MySQL双配置各91项、最终Docker真实主链2项和NUL拒绝6项通过。旧PLAIN仅改标题保留原描述/确认；空内容和NUL禁止写入。生产源码96ba96e可复现空编辑缺口，但未读取REQ-20261103-0002正式审计或修改原记录。迁移目标0014_issue4/mysql57_0012仅隔离测试；本轮未推送、合并、部署或访问真实数据库，临时资源定点清理，证据见上述文档。

2026-11-03 用户授权补充当前账号取消绑定通知邮箱，按已讨论规则清空邮箱及验证状态、作废未完成验证码，保留站内通知、邮件偏好及账号知晓记录；测试通过后部署 TEST 供用户验收，禁止动正式环境。允许更新开发契约和必要前后端实现，无需 schema 迁移；只在新建隔离数据库运行本地测试，TEST 仅以合成测试账号通过正常 API 验收。本轮不推送、合并或发布。执行见 `docs/email-unbind-test-2026-11-03.md`。

2026-11-03 该解绑增量已部署保留 TEST：API/worker/Web 冻结源码 `f879eaa`，数据库仍 `mysql57_0011`。本地 399 前端单测、18 浏览器用例、PostgreSQL 24 / MySQL 22 项、契约文档 20 项及构建类型检查通过；TEST 29 表和附件切换保留、页面解绑、独立会话、旧验证码和 revision、3 条邮件跳过及 2 条站内通知送达验收通过。首次会话轮换触发数据保护回退，第二次因部署顺序与既有代理恢复前置条件冲突回退，均无数据库恢复；修正部署顺序后于 13:20:38 完成，最终健康及正式环境保护基线通过。正式容器与配置未变，不执行迁移、推送、合并或发布。详细失败、修正和回退方式见上述执行文档。

2026-11-03 流程入口补丁已按用户原 TEST 部署授权完成：恢复后确认目标目录及相关部署／构建任务不存在，两环境仍为原基线；改用宝塔文件管理正常上传并校验归档，仅更新 TEST Web 为 `iterflow-web:workflow-entry-ba5d46e`（源码 `ba5d46e`）。备份、切换前后数据哈希、九组在线 HTTPS 检查及桌面／375px 页面验收通过。正式容器与配置、TEST API/worker/DB/Redis 保持不变，数据库仍 `mysql57_0011`；无迁移、恢复、正式升级、推送或合并。实际结果见 `docs/workflow-fix-test-2026-11-03.md`。宝塔永久修复未在本次执行。

2026-11-03 运维传输约束：本会话通过宝塔网页终端传输的首条 Base64 命令为 60,192 字节，与用户事故复盘中的阻塞 PTY write 长度完全一致，高度支持该操作触发面板阻塞。后续禁止通过宝塔网页终端传输文件、Base64 数据块或长脚本，也不得尝试缩小分块来继续该方式。部署改用现有独立 SSH/SFTP 或正常文件上传，脚本以文件上传后执行；连接需核验服务器身份，不绕过主机密钥检查。先核对残留上传、构建任务和两环境基线再继续 TEST；不擅自修改、升级或重启宝塔，不把附件复盘中的建议当成操作授权。事实与处置见 `docs/bt-terminal-incident-2026-11-03.md`。

2026-11-03 用户授权修复 `docs/workflow-audit-2026-11-03.md` 中的流程入口问题，并部署到保留 TEST 环境测试。范围为前置条件与缺人指引、管理员代操作原因、反馈代受理和具体错误说明；保留现有后端门禁、CAS、权限及审计。本次不变更数据库或发布契约，不部署正式环境、不自动合并或发布。执行记录见 `docs/workflow-fix-test-2026-11-03.md`。

2026-11-02 用户确认邮件引导测试验收没有问题，并要求准备上线正式环境。本轮已完成分支/最终 master 八项 CI、无漂移合并与双远端同步（master `5f5d74e`），正式备份、隔离演练及短暂维护升级。当前正式 API/worker/Web 源码 `96ba96e`，MySQL `mysql57_0011`；维护 105.64 秒，数据保留、服务健康及页面只读验收 PASS。TEST、正式邮箱配置和业务数据保留，未创建 tag/Release、未降级或恢复数据库。实施及操作异常记录见 `docs/mail-notice-production-2026-11-02.md`。下述“正式仍为 2c503bf / 0010”等为此前阶段历史；不自动授权后续升级或业务写入。

2026-11-02 用户随后明确授权将邮件通知引导弹窗部署到保留测试环境，验证弹出条件及账号跨设备知晓；不动正式环境。本次冻结源码 `96ba96e` 已更新 TEST 8444 的 API/worker/Web，测试库追加迁移到 `mysql57_0011`，备份、隔离恢复迁移演练及在线检查通过。正式仍为 `2c503bf` / `mysql57_0010`；未推送、合并或创建 tag/Release。记录见 `docs/mail-notice-test-deployment-2026-11-02.md`。

2026-11-02 用户追加邮件通知引导弹窗，并明确“我已知晓”按账号保存、跨设备不再提醒。允许实现当前账号知晓接口、双数据库追加迁移及前端提醒规则；只在本任务新建隔离实例验证。此增量不自动授权部署、远端合并或修改真实数据库；实施与验证见 `docs/mail-setup-notice-2026-11-02.md`。

2026-11-02 用户后续明确要求“走上线流程，确保不会影响到正常使用”，并选择“演练通过后立即短暂维护”，授权本次正式升级及必要的备份、隔离演练和迁移，替代上一阶段不得部署正式环境的限制。正式环境已升级到 master a1c90dd 对应的冻结产物 2c503bf、mysql57_0010，健康/数据保留/页面只读验收通过；保留测试环境及其他站点，不创建 tag/Release。执行及首次重载探测 503 处理记录见 `docs/production-deployment-2026-11-02.md`。不自动授权后续新版本部署、数据库恢复或业务写入。

2026-11-02 最新上线准备授权：将最新修改部署保留测试环境并验收，完成八项 CI，通过后核对 master 无漂移再合并并同步 GitHub/Gitee；更新升级与回退文档。不部署正式环境、不修改正式数据库、不创建 tag/Release。执行证据见 `docs/production-preparation-2026-11-02.md`。

2026-11-02 用户追加：验收人员可多选，任意一名有权限的有效验收人确认即可进入待发布；需求确认成功进入待开发后自动弹出设计／开发／验收人员选择窗口。保留需求确认人单人、RBAC、revision CAS 和实际操作记录。允许追加双数据库兼容迁移并仅在新建隔离实例验证；此记录不授权部署或修改真实数据库。

本轮合并结果：已在确认 master 10f6bfa 无漂移后 no-ff 合并并推送 69c2c87；其八项 CI 全部通过，见 `docs/collaboration-workflow-master-merge.md`。下文更早的“不得合并”是原阶段限制，已由用户本轮明确合并授权替代；不发布、不部署、不修改真实数据库的限制继续有效。

最新授权：核对 master 无漂移后合并并推送，跑完原六项及既有双 MySQL 配置 CI，修复并记录结果；不发布、不部署、不修改真实数据库。用户明确确认取消逐人开发完成门禁，改由开发人员提交验收、验收人确认。此规则替代下文历史逐人确认／总负责人／DESIGNING 主阶段规则；旧记录保留，双数据库及其他主链约束不变。

用户已批准按 `docs/collaboration-workflow-improvement-plan.md` 开工，范围为反馈表单精简、多人接收单人受理、需求六阶段与环节人员、邮件通知、版本批量关联及摘要弹窗。按方案推荐默认值实施；反馈接收人暂不自动扩展 DataScope，不新增系统角色或 permission。允许为该范围更新开发契约、实现必要 Alembic migration 并在隔离测试数据库验证；不得对真实数据执行迁移。

该授权替代下文历史版本授权中针对本轮范围的“不开发新功能／不新增 migration／不调整需求状态”限制；其他主链、事务、revision、RBAC 和技术栈规则不变。取消需求总负责人须保留历史读取兼容；版本负责人保留。仅更新 `spec/openapi-development.yaml`，已发布契约不变。

本轮按阶段实施、验证并记录实际结果；不沿用历史自动 merge/tag/Release/Preview 授权。正式发布、远端合并和真实环境升级另行处理。执行记录见 `docs/collaboration-workflow-execution-log.md`。

用户进一步授权：后续各阶段测试通过并记录结果后直接进入下一阶段，无需逐次确认；不部署，不修改真实数据库。测试只连接本任务新建的隔离数据库实例。

本轮后续授权：推送当前 `codex/collaboration-workflow` 分支到远端并跑完六项 CI，发现问题直接修复并记录结果；不得合并、发布、部署或修改真实数据库。CI 数据库与恢复演练仅在一次性 runner 内执行。


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

2026-10-23 用户明确批准开发人员、产品负责人、研发负责人具备完整版本流程：创建、安排需求、推进版本状态、检查及发布。允许补齐已有权限及双数据库追加迁移；不扩展 DataScope 或需求分工管理权限，不放松发布门禁。实施与验收见 `docs/version-role-permissions.md`，2026-10-23 已按测试先行顺序完成双环境部署，凭据见 `docs/version-role-deployment-2026-10-23.md`，既有历史发布授权保持为历史记录。


本文件是“需求与版本管理系统”仓库内所有开发 Agent、代码生成工具和人工开发者的最高优先级工程说明之一。
进入仓库后应先阅读本文件，再阅读 `DEVELOPMENT.md`、`TASKS.md`、`docs/` 与 `spec/`。

2026-10-12 用户进一步授权合并反馈名称分支并配置保留测试环境的开机恢复。no-ff合并及后续恢复配置见 `docs/master-merge-and-autorecovery-2026-10-12.md`，最终master需自身八项CI和双远端SHA核验通过。本次不新增tag/Release，不再次更新正式应用或重启整台服务器；历史部署与发布记录保留。

2026-10-12 用户确认后续部署顺序：保留 `https://sx-kc.xyz:8444` 独立测试环境，后续更新先在该环境完成验收，通过后再按当次更新授权范围更新 `https://sx-kc.xyz:8443` 正式环境。必要门禁或测试验收未通过时不得更新正式环境。测试账号、数据库及附件与正式环境隔离，不导入生产；未经用户新的明确移除指令不得清理测试环境。流程和当前基础设施限制见 `docs/test-environment-workflow.md`；本次记录不构成立即部署正式环境或新的 tag/Release 授权。

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
