# AGENTS 历史索引

本目录保存根工程入口整理前的原始记录，供追溯规则来源、阶段授权、验证与部署证据。**历史内容不是当前指令或本次操作授权，也不证明当前环境状态。** 其中“最新授权”“当前开发”“自主执行”“已部署”等表述均指写入当时；执行任务先读 [当前 AGENTS](../../AGENTS.md) 与 [Agent 工作流](../agent-workflow.md)，再按任务定位证据。

## 原文与完整性

| 项目 | 值 |
| --- | --- |
| 原始位置 | 仓库根 `AGENTS.md` |
| 完整归档 | [agents-before-workflow-2026-11-12.md](agents-before-workflow-2026-11-12.md) |
| 源 commit | `6823606ea8b7fe78f27150c4b483d84426c1ed51` |
| 源 Git blob | `e6fc62ea07857e898b206a5c2bfa5519de8e37ea` |
| SHA-256 | `534e9aa232e0751df1dbaceaff41a55a21b43fbf10b6bf18fc09585d435e708b` |
| 大小 / 行数 | 63,309 字节 / 524 行 |
| 核对方式 | 归档字节与 `git show 6823606ea8b7fe78f27150c4b483d84426c1ed51:AGENTS.md` 完全一致 |

归档不添加说明头、不改字、不重排行。原文中的 `docs/...`、`spec/...` 等相对路径仍按**仓库根**解释，不按 `docs/history/` 解释；原绝对路径也保持当时记录。下列行号指归档原文，链接采用仓库代码行定位格式。

## 按主题定位

| 主题 | 原文行号 |
| --- | --- |
| 11 月 12 日关闭确认、UI TEST 部署、本机 admin 恢复、UI 本地验证 | [L3–L13](agents-before-workflow-2026-11-12.md#L3-L13) |
| 小程序品牌管理：纠正模型、开发、TEST、上线准备及正式部署授权 | [L15–L23](agents-before-workflow-2026-11-12.md#L15-L23) |
| 11 月 10 日累计上线、支付宝和反馈模块移除、按钮布局及 TEST | [L25–L46](agents-before-workflow-2026-11-12.md#L25-L46) |
| 弹窗/筛选/焦点/底栏修复、UI 优化及本机登录修复 | [L48–L58](agents-before-workflow-2026-11-12.md#L48-L58) |
| 发布覆盖记录替代目标计划门禁 | [L61–L64](agents-before-workflow-2026-11-12.md#L61-L64) |
| 旧多目标发布方案、开发、TEST 与后续上线准备 | [L67–L75](agents-before-workflow-2026-11-12.md#L67-L75) |
| 详情系统归属/最近操作、更新公告与业务系统绑定 | [L77–L99](agents-before-workflow-2026-11-12.md#L77-L99) |
| 版本集中提验、批量指引、版本流转及 TEST | [L101–L121](agents-before-workflow-2026-11-12.md#L101-L121) |
| Issue #4：软删除、重开、多人确认、富文本及空内容防护 | [L123–L125](agents-before-workflow-2026-11-12.md#L123-L125) |
| 邮箱解绑、流程入口补丁与宝塔传输事故长期约束 | [L127–L135](agents-before-workflow-2026-11-12.md#L127-L135) |
| 邮件通知引导、11 月 2 日上线与多人验收 | [L137–L147](agents-before-workflow-2026-11-12.md#L137-L147) |
| 协作工作流授权：六阶段/环节人员、取消逐人开发确认、双数据库 | [L149–L161](agents-before-workflow-2026-11-12.md#L149-L161) |
| 产品命名、适用范围、TEST 保留顺序、旧规格优先级 | [L164–L222](agents-before-workflow-2026-11-12.md#L164-L222) |
| 核心主链、技术栈、StorageService、CAS | [L224–L299](agents-before-workflow-2026-11-12.md#L224-L299) |
| 旧需求总负责人/逐人确认规则与集中状态机要求 | [L301–L319](agents-before-workflow-2026-11-12.md#L301-L319) |
| 反馈转换、需求迁移、版本发布的原子事务 | [L321–L348](agents-before-workflow-2026-11-12.md#L321-L348) |
| 权限、安全、PC/移动、OpenAPI 与数据库 | [L350–L416](agents-before-workflow-2026-11-12.md#L350-L416) |
| 代码分层、工作方式、测试门禁、旧验收主链及禁止事项 | [L418–L505](agents-before-workflow-2026-11-12.md#L418-L505) |
| V1.7/V1.8/V1.8.1 历史 merge/tag/Release/Preview 执行授权 | [L507–L524](agents-before-workflow-2026-11-12.md#L507-L524) |

## 已被后续规则替代的内容

归档保留矛盾的先后记录用于审计；不能因旧段落更靠后或称“非协商规则”，恢复已被用户替代的行为。当前状态细节按 [状态机](../../spec/status-machines.md)及 [开发契约](../../spec/openapi-development.yaml)读取。

| 历史内容 | 后续依据与当前处理 |
| --- | --- |
| AGENTS 自称最高优先级、强制通读全部文档（L195–L221） | 当前根入口明确高层指令及用户当前有效指示优先，按任务读取，不将本地文件置于用户之上。 |
| 需求总负责人、DESIGNING 主阶段、每名开发者本人确认后才 DONE/发布（L303–L307） | [L151–L155](agents-before-workflow-2026-11-12.md#L151-L155)取消旧规则；当前按六阶段和环节人员，由开发提验、有效验收人确认。 |
| 单 CONFIRM、取消后不得重开 | [L123–L125](agents-before-workflow-2026-11-12.md#L123-L125)的 Issue #4 扩展多人确认与 CANCELED→DRAFT；ONLINE 仍不可重开。 |
| 手动推进/退回版本阶段、READY 冻结清单（含 L192、L316） | [L119–L121](agents-before-workflow-2026-11-12.md#L119-L121)改为只读派生进度；READY 可按原门禁改清单。RELEASED/CANCELED 冻结状态及清单，基础信息编辑按当前状态机保留。 |
| 目标全部完成才整体上线、首次部分成功冻结（L67–L73、L87） | [L61–L64](agents-before-workflow-2026-11-12.md#L61-L64)改为实际覆盖记录；不恢复目标门禁，不把旧未完成计划推断为已发布。 |
| 当前开发入口为 openapi-v1.8.1.yaml（L204、L400、L522） | [L202–L213](agents-before-workflow-2026-11-12.md#L202-L213)与 [L398](agents-before-workflow-2026-11-12.md#L398)指定 openapi-development.yaml；已发布快照冻结。 |
| V1.7/V1.8/V1.8.1 自动合并、打 tag、Release、Preview 授权 | [L157](agents-before-workflow-2026-11-12.md#L157)已明确不沿用；归档与当前入口均不产生新的 Git/环境操作许可。 |
| 某轮不得部署/已部署、旧 SHA/迁移号及测试计数 | 均是阶段事实；不能限制之后用户已明确授权的工作，也不能充当本轮已执行证明。查对应专题结果，执行前核验。 |

## 后续维护

- 根 AGENTS 只更新长期规则和已批准业务的简洁入口；任务执行、故障修复、验证与部署结果写对应专题文档。
- 本次归档为不可改写的来源快照；后续索引可追加新的档案，注明各自来源 commit、哈希与适用范围。
- 原始历史的保留不意味着长期规则只能留在历史：主链、CAS、事务、权限/范围、存储安全、双数据库、响应式、测试门禁、部署数据保留和宝塔事故约束均已提炼到当前 AGENTS。
