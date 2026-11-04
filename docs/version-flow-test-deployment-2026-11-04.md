# 2026-11-04 版本流程及筛选选择 TEST 部署

## 范围与当前状态

用户授权将本轮修改部署保留 TEST，验证需求创建版本、重复版本号提示、版本自动进度；追加需求管理的版本/参与人及版本管理的负责人改为选择框。正式环境不变，不推送、合并或创建 tag/Release。

当前准备中，尚未切换应用或执行 TEST 迁移。本地上一阶段冻结源码为 `f28653d`，筛选选择增量完成后重新冻结配套 API/worker/Web。既有本地验证见 `version-workflow-simplification-2026-11-04.md` 与 `issue-4-improvements.md`。

## 只读连接核对

- 2026-11-04 08:36:37 UTC，Safari 已登录宝塔终端并正常显示 root 提示符。
- 服务器 `39.96.68.171`，hostname `iZ2zehrcw9x4jxbjd1mfqaZ`。
- TEST API/worker/Web 为 `email-unbind-f879eaa`，运行约27小时，API/Web健康。
- 正式 API/worker/Web 为 `mail-notice-96ba96e`，运行约46小时，API/Web健康。
- TEST DB/Redis及正式 Redis运行约3周；根盘可用22G。
- 本机 SSH config 仅包含 Colima，未发现既有目标服务器配置。后续通过宝塔正常文件上传传送归档和脚本；终端只执行短控制命令，不传 Base64、文件内容或长脚本。

## 升级与保留检查

1. 核对残留部署任务、两环境容器/配置和 TEST schema 基线；记录正式保护哈希。
2. 完成最终源码与镜像一致性验证，正常上传并校验归档 SHA。
3. TEST 专用维护隔离写入，停止 API/worker；备份数据库、附件和配置，不清库、不 seed。
4. 隔离恢复 TEST 备份并演练 `mysql57_0011 → mysql57_0012`，检查全部旧业务列及附件保留。
5. 实际迁移只在演练通过后执行；API/worker/Web配套更新。
6. schema/preflight、原列内容和新增列默认值全部核对通过后恢复 worker，再按既有要求恢复 TEST 代理。
7. 合成测试账号通过正常 API 和页面验证新流程及筛选，记录最终健康和正式保护结果。

比较规则：需求排除新增 description_format/deleted_at/deleted_by，反馈排除新增 deleted_at/deleted_by，actor 排除被删除的计算列 single_actor_role；其余原列、行数、revision、人员、关系、确认、邮件状态均应一致。alembic_version 仅允许0011到0012；新列应为 PLAIN/NULL。额外核验列类型、默认值和 deleted_by 外键。

## 筛选增量与本地验证

三处数字输入改为可搜索、分页和清空的选择框，URL 仍保留原 ID 参数。新增三个只读候选接口，仅查询当前可见需求/版本的实际关联人员和版本，不要求人员管理权限。无权查看版本详情时仅显示安全编号，不返回名称；停用人员保留历史筛选能力。

- 后端筛选、已有列表与契约文档回归合计84项通过；三套本任务新建隔离数据库（PostgreSQL、MySQL standard、portable）各1项综合验收通过。
- 前端467单测、309合成浏览器通过，包含375/1440px新增6项选择、搜索、分页、回显、清空和权限验证。
- Ruff check/format（210文件）、mypy（118源文件）、类型、构建、包大小与API类型一致性通过；最大chunk387.9 KiB。
- 首轮回归发现静态候选路由被动态ID路由遮挡，调整注册顺序；浏览器发现首次下拉候选不可见及异步标签不更新，修正选择器过滤方式。旧列表测试夹具同步为选择操作后全量通过。失败日志保留。
- 前端全套单测既有14条jsdom AggregateError噪音与上一轮相同；新增及适配列表测试独立运行无噪音。首次Ruff扩大扫描历史迁移失败已保留，CI范围复核通过。

证据目录：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-04/version-flow-test/`，含 `frontend-filter-delivery.json` 与 `local-gates/filter-gates-summary.json`。

## 预检异常记录

首次只读预检因既有正式配置使用符号链接、脚本预期普通文件而安全停止；没有停止服务、导入镜像或修改数据库。已核实仅三个固定链接指向既有 shared 目录的 root:root 0600 普通文件；修正为同时保护链接及目标元数据/哈希，不修改正式配置。原始日志保留在服务器受保护证据目录。

## 回退边界

MySQL DDL 非原子。首条 DROP INDEX 执行后失败时，head仍可能为0011但结构已变；禁止盲重跑、stamp、自动恢复旧应用、降级或恢复数据库。保留 TEST 停写及完整失败证据，核对实际结构后前向修复。旧 f879eaa API/worker不兼容0012，不能直接回退；新数据产生后迁移降级亦可能拒绝。正式环境和真实正式数据不得触碰。

## 实际结果

待执行，尚无部署成功结论。
