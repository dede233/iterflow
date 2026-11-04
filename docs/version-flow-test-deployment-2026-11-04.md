# 2026-11-04 版本流程及筛选选择 TEST 部署

## 范围与当前状态

用户授权将本轮修改部署保留 TEST，验证需求创建版本、重复版本号提示、版本自动进度；追加需求管理的版本/参与人及版本管理的负责人改为选择框。正式环境不变，不推送、合并或创建 tag/Release。

TEST 已完成备份、隔离恢复迁移演练及实际升级，API/worker/Web 配套运行 `c0f68e1`，数据库为 `mysql57_0012`。在线 API、桌面/375px 页面及最终健康核对通过；正式环境未变。本地上一阶段冻结源码为 `f28653d`，筛选选择增量完成后重新冻结配套产物。既有本地验证见 `version-workflow-simplification-2026-11-04.md` 与 `issue-4-improvements.md`。

最终产品冻结 `c0f68e131b5fd8232c70e4b237b78bfd93d8f72b`。本地 Docker 的 amd64 API OCI index ID 为 `sha256:0e7672179341ba6cd5eb70e9e232a91e9df1e4cfaa5ae9387a1f4ec2883e8628`，Web OCI index ID 为 `sha256:2d18f159a81991a54129840fb19b40c507162c6a209b07eab581b79bd7deceed`，均带相同源码标签；服务器 classic config ID 见下文，不混用两类标识。最终镜像在全新隔离库的2项真实浏览器主链首次运行通过（1.3分钟），包括创建版本并关联、自动进度、发布CAS/竞争、ONLINE同步、审计/站内通知和5视口；SMTP关闭。本轮本地临时数据库、容器、卷及网络已按manifest精确清理，其他容器未变。

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

第二次只读预检读取到0011、30张表、0个触发器；运行账号对触发器元数据不可见，不能把0解释为触发器缺失。改用既有迁移配置在临时容器执行只读事务核对，不新增权限；断言前保存元数据证据。此时仍未停止服务或迁移。短诊断命令首次键入丢失标点，Python语法报错且未执行；改为粘贴同一短控制命令成功，未通过终端传输文件内容。

最终只读预检于 `20261104T091542Z` 通过：原head0011、29张业务表、91个触发器，两环境来源和健康、配置、残留任务及空间检查通过。证据目录 `/opt/iterflow/upgrade-evidence/version-flow-preflight-20261104T091542Z`。

打包审查发现统一0600导致非root容器无法读取无凭据的证明脚本，未上传的首包标记 `DO-NOT-DEPLOY`。最终包仅该脚本0644，其余0600，已用最终镜像非root用户实际导入通过。归档 `iterflow-version-flow-test-c0f68e1.tar` 共117,248,000字节，SHA256 `1797e986d46acbf43e780d2ab0b92858ea320002a4f97c84006ee90a15792e9b`；正常文件上传35.41秒，服务器完整哈希一致，解包保留权限及前两次原始预检文件。

镜像加载后首轮主控预检在ID检查处安全停止（`preflight-failure-20261104T091636Z-1737802`），未进入维护或DDL。本机Docker返回OCI index ID，服务器返回config ID；归档原始config字节SHA、index→manifest→config链和RootFS层确认同一产物。服务器API ID为 `sha256:9bf91c170c9711049ce4248476eaa78da4e6ac4cd8675bd3bc7cb319ac020654`，Web ID为 `sha256:225f551c84d550737a2e796f676c495427437a03b38887dc1e71257ec76d7bb9`；均linux/amd64，源码标签一致。兼容修正保留原清单及失败证据，禁止将任意镜像ID当作可接受替代。

清单兼容修正包 `iterflow-image-identity-correction-c0f68e1.tar` 为71,680字节，SHA256 `ba459e34f51d737622a029c5af9a8f7358c350a1251d15e86ee52513c3db6115`，已正常上传并核对一致。离线验证两镜像全部23层压缩SHA及解压diffID通过，7项清单/篡改拒绝检查通过；仅修正manifest标识，镜像及主控文件不变。执行器要求原基线未漂移且未进入维护/DDL，先保存原清单和失败证据；现场结果见下文。

镜像清单修正现场成功，原清单/controller/基线及首失败记录备份于 `image-identity-original`。随后主控预检已通过镜像、文件、非root脚本读取和数据库结构检查，但在API/worker邮件配置横向相等断言停止（`preflight-failure-20261104T093006Z-1752690`）。只读比较确认唯一SMTP差异为端口：API465、worker1465，运行值与Compose值相同；这是既有Brevo TLS中继配置。需按已知端口分工核验，继续保留升级前后逐服务完整指纹，不能统一端口或更改邮箱配置。仍无维护、DDL或应用切换。

邮件校验修正包 `iterflow-mail-compat-correction-c0f68e1.tar` 为92,160字节，SHA256 `31a7e81a9f22bc0e173fcc2fdd594a25df109d1422c4c604392d394facee5e2e`，正常上传及现场哈希一致。45项控制门禁和5项安装包校验通过，另一Agent只读复查无阻断；仅更新主控校验及其manifest哈希，保留镜像不变，原基线重试只核对不覆写。

现场执行返回 `MAIL_GUARD_CORRECTED`，原主控、清单、基线和失败凭据保存在 `mail-compat-original/`。最终主控 SHA256 为 `e2af2b42ef4f471edc6fdeefae5d3668aeb67ce731aa295d12f1cff4e87d9555`，manifest SHA256 为 `55e2aa79a3a722efeb161be165e7ec5380de855caa02ddbade9173a42a65d075`。未更改应用邮件配置。

## 回退边界

MySQL DDL 非原子。首条 DROP INDEX 执行后失败时，head仍可能为0011但结构已变；禁止盲重跑、stamp、自动恢复旧应用、降级或恢复数据库。保留 TEST 停写及完整失败证据，核对实际结构后前向修复。旧 f879eaa API/worker不兼容0012，不能直接回退；新数据产生后迁移降级亦可能拒绝。正式环境和真实正式数据不得触碰。

## 实际结果

- 最终 `preflight`、`backup`、`rehearse`、`deploy` 及在线验收后的 `verify` 均返回 PASS。服务器证据目录：`/opt/iterflow/upgrade-evidence/version-flow-test-20261104`，分别保留 `preflight-run-mail-fixed.log`、`backup-run.log`、`rehearse-run.log`、`deploy-run.log`、`verify-final-run.log` 及 JSON 回执。
- TEST 维护标记时间 `2026-11-04 17:40:33.024 +08:00`，部署完成 `17:44:12.450 +08:00`，两标记间约219.43秒，包含恢复访问后的验证。维护期间 TEST8444返回503，正式8443持续读探测返回200且首页哈希与原基线一致。
- 升级前备份：`/opt/iterflow/backups/version-flow-test-pre-20261104T094040Z`，数据库 dump 642,907字节、附件归档10,240字节，同时保留配置备份。隔离克隆恢复和0012迁移通过，SMTP关闭、无公开端口；克隆 `iterflow-version-flow-test-20261104-db` 在演练后已停止，演练卷/网络保留，精确标识见 `rehearsal-resources.json`，没有清理保留 TEST 的卷。
- 实际 TEST 迁移到 `mysql57_0012`，29张旧业务表的原行/列/内容、revision、关系、91个触发器及附件通过保留证明；新增列默认值和结构符合迁移。API/Web启动后、worker启动前再次证明数据无变化。无降级、stamp 或真实库恢复。
- 迁移后、恢复业务写入前备份：`/opt/iterflow/backups/version-flow-test-post-migration-20261104T094319Z`，数据库 dump 643,735字节，附件归档与迁移前相同（SHA256 `c1808d390ca3f0cfa39f8329ce987fc90ceceab9cecc066f2527e32b2c24ccfc`）。
- TEST API/worker 为 `iterflow-api:version-flow-test-c0f68e1`，Web 为 `iterflow-web:version-flow-test-c0f68e1`。API健康/ready、Web健康、worker运行、镜像ID/源码标签、原挂载和逐服务SMTP完整指纹核对通过。TEST 首页 SHA256 `f9a0d110c8a8079e09966afae630a88bb6004b0d290868e9aa18e13aea0cd7cd` 匹配冻结产物。
- 正式 API/worker/Web 保持 `96ba96e` / `mysql57_0011`，容器身份、配置文件和既有链接/目标哈希均未变；首页 SHA256 `69c02cd420cef46f7d11141992b1fc2161ad1d88be04d245c37b46e2f25a3e9a` 与原基线一致。未执行正式部署、正式迁移或正式业务写入。

## 在线业务与页面验收

只使用既有合成账号 `ceshi002`，验收前确认未绑定/待绑定通知邮箱。通过正常 API 和页面写入两条明确标注 TEST 的需求及两个版本，保留供用户查看；未实际发布，未对旧业务数据执行编辑或清理。

| 验收项 | 实际结果 |
| --- | --- |
| 创建版本并关联 | API 原子创建/关联、需求 revision 更新；页面标题自动带入，成功后当前版本链接显示新版本；均未发布 |
| 重复版本号 | HTTP409/code40934，页面字段提示“版本号「…」已存在，请更换版本号；如需添加需求，请使用已有版本。”；表单保留，无额外版本 |
| 自动进度 | 需求流转驱动 PLANNING → DEVELOPING → TESTING → READY；列表按派生状态筛选正确，拒绝手动推进版本 |
| 修改已验收内容 | 需求仍DONE但待重新确认，版本自动TESTING；发布检查HTTP409/code40923，明确阻塞需求，检查不改revision；重新确认后READY，版本revision仍为2 |
| 三个候选接口 | 版本/参与人/负责人按名称搜索及selected_id回显通过，组合ID筛选正确 |
| 桌面页面 | 三个选择框显示名称，版本/参与人组合筛选返回唯一需求；刷新后名称与参数保留，重置恢复全部列表；负责人+关键词筛选正确 |
| 375px 页面 | 筛选进入抽屉，人员下拉可读可选，版本负责人组合查询返回唯一版本；临时视口已恢复 |
| 操作精简 | 版本详情显示“进度由关联需求自动汇总；开发和验收在需求中完成。”，保留编辑、发布检查、取消及清单管理；无重复开发/验收操作 |

验收记录：需求23（`REQ-20261104-0001`）/版本22（`TEST-VF-20261104-094730`）最终DONE/READY、未发布；页面创建需求24（`REQ-20261104-0002`）/版本23（`TEST-UI-VF-20261104-0956`）为DRAFT/PLANNING、未发布。

验收脚本异常如实保留：首次 `online-qa.py` 已通过9条记录，在发布检查阻塞处错误预期200而收到符合契约的409，保存 `online-acceptance.json` STOPPED。首次恢复脚本把版本需求清单误当带total的分页DTO，在任何恢复写入前停止，保存 `online-acceptance-resumed.json`。复核契约并以真实DTO形状通过完整合成测试后，`online-qa-resume-v2.py` 从原需求23/版本22继续，6项检查于 `2026-11-04T09:55:05Z` 全部PASS；保护前两次凭据SHA，没有重建数据或重复发送确认，未为迁就脚本更改产品。恢复阶段前后邮箱偏好完全一致，未绑定邮箱、未改变知晓状态。

本地凭据为同证据目录下 `online-acceptance*.json`、`online-requirement-filters.jpg`、`online-duplicate-version.jpg`、`online-created-version.jpg`、`online-mobile-filters.jpg`。本轮未运行远端CI、未推送/合并、未创建tag/Release；用户可在 `https://sx-kc.xyz:8444` 验收。
