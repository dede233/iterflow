# 多小程序发布 TEST 部署与验收（2026-11-09）

用户授权更新保留TEST并验证首次发布、后续补发和发布记录，正式环境不变。冻结产品`2b9fd16fca66253d0c7323e54cb00bdd66da3226`；TEST最近基线`de8ab75/mysql57_0014`，正式`5401215/mysql57_0012`。

本次配套API/worker/Web，测试库追加到mysql57_0015、补齐现有运行账号三张新业务表最小DML。先预检和冻结包校验，TEST停写备份数据库/附件/配置，隔离内部网络恢复演练及完整旧行/结构/触发器/账号/公告保留证明，通过后真实TEST只迁移一次；运行账号验证、应用健康及逐服务SMTP保留通过后开放。DDL后失败维持停写并前向处理，不自动降级、恢复数据库或重跑DDL。

验收仅合成TEST记录：首次选A/B，A成功仍待发布且冻结，B成功整体上线且只一条Release；之后补发C，原Release/上线状态保留，目标记录和筛选正确。验证旧数据未推断目标、权限/CAS阻断及桌面/375px。保留合成记录供用户验收，不触发外部小程序发布。

宝塔采用正常文件上传，终端仅短控制命令，不传文件/Base64或长脚本。不推送/合并/tag/Release，不连接正式数据库、不修改正式应用或配置。

实际结果见下文。证据目录：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-09/multi-target-release-test/`。

## 冻结包与切换前检查

- Linux AMD64 API/worker 与 Web 均从 `2b9fd16` 冻结源码构建；服务镜像名 `iterflow-api:targets-test-2b9fd16` / `iterflow-web:targets-test-2b9fd16`。逐层 OCI/classic 身份、171 个 API 文件、162 个 Web 文件校验通过。
- 上传包 `iterflow-targets-test-2b9fd16-verified.tar` 为 117,084,160 字节，SHA256 `a803035c588579a6c6e81d809df1e0cd178a422e21875bfc9b597a6eb3fa4834`；宝塔普通文件上传后服务器摘要一致。未通过终端传文件。
- 本地部署辅助测试最终 3 PASS：旧行/结构/触发器/文件保留、篡改拒绝、三表精确授权与重放拒绝、Python 3.6 语法和 DDL 前后失败边界。首次负向断言误将 `timestamp` 当作 `stamp` 命令，修正测试后通过，保留原失败日志；未改产品。
- 服务器身份 `iZ2zehrcw9x4jxbjd1mfqaZ`、两环境镜像和源标记、运行状态、公开首页、配置指纹与残留任务检查通过；正式应用仍为 `5401215`，未连接其数据库。
- 服务器 `preflight`、`prepare`、`backup`、`rehearse` 四阶段均 PASS。旧镜像/配置、TEST 停写数据库和附件已备份；在内部网络克隆恢复迁移，旧 32 表完整原列/行/索引/外键/97 个原触发器与附件保留，通过到新 35 表/110 触发器的证明。克隆无端口且 SMTP 关闭，完成后停止。真实 TEST 此时尚未迁移；后续结果见下文追加。

## 首次切换阻断与修正

首轮 `python3 deploy-test.py deploy` 在 DDL 前被残留任务检测拦下：检测仅排除控制器的完整路径，而相对路径启动的自身匹配 `deploy-test.py deploy`。`failure-deploy-20261109T103523Z-1258073` 保留 traceback 与 STOPPED 回执，`real_ddl_started=false`。原始数据与迁移头校验后自动恢复旧 API/worker/Web 和 TEST 代理，`rollback.json` PASS；未执行真实迁移、授权、数据库恢复或降级。

不修改冻结产品或原控制器。新增独立一次性 `resume-deploy.py`（1,663 字节，SHA256 `b76c7cd7e599748215c809451f5dd1ba72d10408c2ea56d0bf366c68bc22416a`），普通文件上传后摘要一致；Python 3.6 语法检查通过。以完整路径运行，沿用控制器独占锁、异常保护、正式保护和 DDL 单次标记；先检查旧应用健康，再停写，要求完整数据/结构/附件快照与已演练快照严格相等，重新备份后调用原 deploy。若恢复期间产生任何数据变化则中止，不能复用旧演练；DDL 后仍仅停写并前向修复。


## 实际切换和最终状态

续部署确认 TEST 停写全量快照与已演练快照严格相等，重新生成 `pre-resume` 数据库/附件备份，随后真实 TEST 迁移仅执行一次。`resume-deploy.log` 的 deploy 回执 PASS；`data-preserved.json`、`deployed.json` 和最终 `verify.log`/`verified.json` 均 PASS。

| 检查 | 结果 |
| --- | --- |
| 真实 TEST 迁移 | mysql57_0014 → mysql57_0015，35 表 / 110 触发器 |
| 旧数据与附件 | 原 32 表原列完整行、索引/外键、97 个原触发器、例程、安全配置和既有文件保留 |
| 新表权限 | 既有 accept_runtime@%，仅 sys_release_target、rd_release_batch、rd_release_batch_target 的 SELECT/INSERT/UPDATE/DELETE；无新增账号、角色或全库/全局授权 |
| 运行账号实际查询 | readiness、CURRENT_USER、三张新表 SELECT 均 PASS |
| 配套应用 | API/worker/Web 均 2b9fd16，API/Web/DB/Redis 健康，worker 运行 |
| 邮件和代理 | 原 API/worker 各自 SMTP 完整指纹保留，TEST 代理恢复且新首页校验通过 |
| 最终复核 | 验收后表结构/迁移头/索引/外键/触发器/配置及原有附件检查 PASS |
| 正式保护 | 5401215 应用容器、配置与公开首页保持原基线；未连接正式数据库 |

原镜像和配置、停写 SQL/附件备份、迁移后备份与克隆演练证据保留服务器受保护目录。控制目录 `/opt/iterflow/upgrade-evidence/multi-target-test-20261109` 中保留逐阶段 JSON、原失败/traceback/回退与续部署回执。克隆演练数据库已停止，无公开端口。未重启/修改宝塔，未操作其他站点；未 seed、真实回库/降级、推送、合并或创建 Git tag/Release。备份及控制材料不包含在产品镜像或公开 Web 中。

## 在线合成验收

只使用既有 TEST 超管浏览器会话维护三个合成目标，既有 `ceshi002`（ALL 业务范围）通过普通 HTTPS API 创建和推进合成数据；未扩展账号权限或绕过用户身份。

- 业务系统：中文验收系统（1）；目标 `TEST_MT_1109_A/B/C`（1/2/3），未填写真实 AppID/AppSecret 或调用微信平台。
- 需求 35 / `REQ-20261109-0001`，版本 28 / `TEST-MT-20261109`，首次批次 1、补发批次 2、整体 Release 12。
- 首次 A 完成后版本仍 READY、需求仍 DONE、两者 release_frozen=true；修改内容/人员、取消已有成功目标的首次批次、旧 revision 重复登记均 409。此时整体 Release 为 0。
- 首次 B 完成后批次 COMPLETED 2/2、版本 RELEASED、需求 ONLINE，整体 Release 恰好 1 条。
- 创建补发 C 时保持原上线状态；C 完成后整体 Release 的 ID、内容和时间完全不变，仍只有 1 条；目标实际记录总计 3 条，逐个 target_id 及 version_id 筛选正确。
- 未登录查询 401；产品负责人维护系统目标目录 403；无发布权限的既有成员创建批次 403。
- 旧合成已发布版本 15 的 `legacy_unrecorded=true` 且无批次，不自动推断历史目标。
- 页面验证：首次 2/2、补发 1/1、累计覆盖 3、实际时间/登记人/凭证展示，补发入口不提供已覆盖目标，显式重新发布列出 A/B/C 且要求原因；只打开后取消，未生成多余批次。
- 发布记录“目标实际记录”显示 3 条，选择 C 后显示 1 条；桌面和 375×812 布局无横向溢出（scrollWidth=375），检查后恢复原浏览器尺寸。

合成目标、需求、版本和记录全部保留供用户验证：

- 版本详情：https://sx-kc.xyz:8444/#/versions/28
- 发布记录：https://sx-kc.xyz:8444/#/releases （选择“目标实际记录”）

本轮验证登记的是 TEST 模拟实际上线结果，并未向外部小程序平台提交发布。线上仅有一个启用业务系统，跨系统及并发竞态由本地双数据库隔离测试覆盖；本轮不冒称重新执行远端八项 CI，前次 5d79a48 的 CI 不自动代表 2b9fd16。

## 验收脚本异常和证据

`qa-create.log` 首次错误假定普通产品账号可读取管理员目标目录，服务正确返回 403；当时无业务写入，改用版本允许的目标选项入口。`qa-create-final.log` 错误期望原创建需求接口为 201，实际为契约既有的 200；需求已创建。只读定位唯一合成需求 35 并核对 DRAFT/revision=1/系统/参与人后恢复继续，未重放创建。版本创建同样保留原 200 契约；新增目标/批次接口为 201。后续 `qa-create-resume.log`、`qa-initial.log`、`qa-supplement.log`、`qa-checks.log` 均通过，补充 `qa-legacy.json` 证明旧合成版本兼容。上述修正只涉及外部验收脚本，未改产品或冻结镜像。

部署辅助最终 3 项及续部署顺序/数据漂移拒绝 2 项本地检查通过；失败日志不删。在线详细 JSON 与以下截图位于交付证据目录：`version-desktop.png`、`version-mobile.png`、`records-desktop.png`、`records-mobile.png`、`records-filter-c.png`。服务器完整回执不公开下载、不复制运行凭据。

## 回退边界

首轮失败发生在 DDL 前，已按完整保留证明安全恢复旧应用，没有恢复数据库。成功迁移至 0015 后，尤其已产生目标实际记录和首次内容冻结后，不得自动切回缺少该语义的旧应用，不降级/回库、不改迁移版本号、不重跑 DDL；出现问题先保持或恢复 TEST 维护和停写，保留现场，以兼容 0015 的冻结候选前向修复。数据库恢复、降级或清理保留测试数据须有新的明确授权。正式环境保持不变，后续正式上线仍须单独授权和对应准备门禁。
