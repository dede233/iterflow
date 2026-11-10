# 支付宝、平台字段联动与反馈模块移除 TEST 部署 · 2026-11-10

## 授权及冻结

用户明确授权三项合并部署到保留 TEST 验收，正式环境不变。冻结源码 `80c322db82b26cd659dfe75b312ebb921ea80e9e`，API/worker/Web 配套更新，TEST MySQL 由 `mysql57_0015` 升到 `mysql57_0016`。无新增表、列或权限；不得 seed、恢复真实数据库、清理保留数据或修改正式环境。

前置 TEST：API/worker `097b2dd`、Web `0c12952`；正式 `5401215` / `mysql57_0012`。通过现有宝塔正常文件上传，终端仅短控制命令；无推送/合并/tag/Release。

## 准备与门禁

- 本地既有 509 前端、双数据库支付宝/迁移专项、6 平台浏览器及 8 反馈浏览器已通过，见两项开发记录。
- 本轮冻结 linux/amd64 镜像并逐文件对照 Git；离线归档 config、manifest、层 diff-ID 校验通过。
- 本轮部署控制器 2 项隔离 MySQL 测试通过：真实0015→0016、全行/附件保留、篡改拒绝、DDL后自动回退阻断、宿主Python3.6语法。
- 部署包 SHA256：`bc17bf79f95290d5dd40657535487360768d3a797a18f085ed883d12f18e5996`，117053440 bytes。
- 远端脚本目录：`/opt/iterflow/upgrade-evidence/alipay-feedback-test-20261110`。
- 本机证据：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-10/alipay-feedback-test/`。

## 执行

preflight、prepare 已 PASS：35表/0015旧基线、两环境保护、旧应用与配置备份、候选镜像完整文件和身份校验、非root读取证明、pip check通过。首轮 backup PASS；隔离演练在约束保留比较时 STOPPED，真实 TEST DDL 未开始，控制器恢复旧 TEST 应用并验证数据未变。

初次解包因网页终端漏掉 `mkdir` 首字符，命令未执行；随后预检因脚本尚未解包退出，未启动部署控制器、未停写。确认错误后重新解包并通过预检。

## 回退边界

真实DDL前失败可保留数据恢复原应用；DDL开始后禁止盲目重试/降级/旧应用自动回退，保留维护并前向处理。产生支付宝目录或历史快照后，旧应用无法读取新枚举，应使用保留支付宝兼容能力的前向补丁。任何真实数据库恢复另行明确授权。

## 首轮演练失败与修正

首轮 `rehearse` 于 2026-11-10 06:25:32Z 被保留证明拦下：`domain_rd_release_batch_target_insert` 的 ACTION_STATEMENT 除新增支付宝枚举外，布尔条件与平台条件的 OR 顺序也发生了等价交换。校验脚本只允许枚举差异，错误拒绝此已知迁移变化。真实 DDL 未开始，旧应用恢复 PASS；无数据库恢复或降级。

修正仅涉及外部部署校验：严格允许四个指定触发器中的精确 OR 条件交换，继续逐项比较其他 SQL、元数据、DEFINER、全行和附件。原本测试从0016降到0015，使用新helper生成了相同顺序，未覆盖原始0015；现改为隔离实例降至0014，再升至0015构造真实旧约束。修正测试夹具前的一次失败保留于 `deployment-gates-fixture-failure.log`，最终2项PASS（4.22秒）。产品代码及冻结镜像未变。

第二轮采用独立目录 `/opt/iterflow/upgrade-evidence/alipay-feedback-test-20261110-attempt2` 和独立隔离资源，保留首轮证据，重新预检、备份及演练。修正包112640 bytes，SHA256 `1d828bd769b0ce44492010301beaec46146bbc574e72ddfeb47da340f66f4981`；相同镜像归档复制后由manifest重新验证。第二轮preflight/prepare/backup/rehearse/deploy/verify全部PASS。

## 最终结果

TEST API/worker/Web 已配套更新到 `80c322db82b26cd659dfe75b312ebb921ea80e9e`，数据库 `mysql57_0016`，外部 HTTPS 已恢复。第二轮迁移前后35张表（包括迁移版本表，业务表逐行哈希）、110个触发器（106个完全不变，4个仅已批准差异）、附件、账号/会话、审计、公告、索引/外键/结构及安全定义保留检查通过。运行账号实际查询、API/Web/worker健康、恢复服务、逐服务SMTP指纹、代理与正式保护基线通过。

产品镜像经典Docker config ID：

- API/worker：`sha256:0cddbf5bfc8bbffbedd0e49724421035793ea9444a7da88f171ec681bbdc43c6`
- Web：`sha256:639abb1c419982f1bb3d84221b3467b2be7575a309b50a57b1c782c9ec8805c8`
- TEST首页 SHA256：`e4c091c43a19ea9a83461ab188bfebbcdb39500a94892ad2dddcae634e33d302`

正式应用/配置/首页保持 `5401215` 基线，未连接正式数据库。没有新增权限、seed、真实数据库恢复/降级、Git推送/合并/tag/GitHub Release。两轮隔离资源停止后保留受限证据；未删除已有TEST或用户资料。

## 在线验收

仅使用既有TEST管理员页面会话和合成测试账号 `ceshi002`，经正常UI/API完成：

| 验收项 | 结果 |
|---|---|
| PC Web / 微信小程序 / 支付宝小程序选项 | PASS |
| PC仅访问地址，小程序仅AppID | PASS |
| 新增切换后隐藏AppID/URL保存为null | PASS，API核对 |
| 已存PC目标编辑切换支付宝，保存AppID并清空URL | PASS |
| 支付宝A首次发布、需求正常ONLINE、版本RELEASED | PASS |
| 支付宝B后续补记，原发布时间/唯一Release/旧记录不变 | PASS |
| 旧revision补记409，无管理权限新增目标403 | PASS |
| 旧合成版本28/29及发布批次全响应与部署前一致 | PASS |
| 反馈筛选/新建/详情/编辑无所属模块入口 | PASS |
| 反馈保留系统和接收人，新建及编辑正常，module_id=null，revision=2 | PASS |
| 桌面发布覆盖、375px反馈编辑和覆盖卡片 | PASS，截图人工复查 |
| 最终verify健康/结构/附件/SMTP/正式保护 | PASS |

保留验收数据：发布目标 `TEST_ALIPAY_1110_A/B`，版本30 `TEST-ALIPAY-20261110`、需求37 `REQ-20261110-0002`、反馈24 `FB-20261110-0001`。目标均明确为合成记录，AppID为TEST字符串；仅记录覆盖范围，未向微信/支付宝平台提交应用。旧历史模块未清理；旧模块普通编辑保留及切换系统清空的边界由本地浏览器专项覆盖，本轮未改写旧反馈来重复测试。

在线JSON证据：`qa-target-fields-before-edit.json`、`qa-created.json`、`qa-published.json`、`qa-supplement.json`、`qa-verified.json`、`qa-feedback.json`。页面证据：`pc-web-fields.png`、`alipay-fields.png`、`feedback-no-module-form.png`、`feedback-mobile.png`、`alipay-version-desktop.png`、`alipay-version-mobile.png`；终态 `final-verify.png` 同时显示第二轮六阶段PASS。远端各阶段原始JSON/受限日志保存在attempt2目录。初轮的 `attempt2-preflight.png` / `attempt2-rehearsal.png` / `attempt2-deploy.png` 捕获于阶段运行中，不作为最终PASS证明。

当前等待用户TEST验收，不自动上线正式环境。
