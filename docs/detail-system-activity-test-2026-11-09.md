# 详情归属与最近操作 TEST 部署（2026-11-09）

## 授权与范围

用户明确授权将业务系统归属展示与最近操作记录部署保留TEST验收，正式环境不变。本次配套更新TEST API/worker/Web，不推送、合并或创建tag/Release。数据库保持mysql57_0014，不执行迁移、seed、数据库恢复或权限修改。

先核对残留任务和两环境基线，正常文件上传离线包，校验冻结源码、镜像内容和归档；备份旧应用/配置/TEST数据与附件后短暂维护切换。恢复流量前验证新应用健康、运行账号实际查询与完整数据保留，再用合成账号通过正常API和桌面/375px页面验收。失败仅回退应用，不回库。

历史基线：TEST8f4e7db/mysql57_0014；正式5401215/mysql57_0012。实际检查、候选冻结SHA、备份及验收结论在执行后追加，不提前记录成功。

## 实际结果

已部署并保留 TEST，等待用户验收。冻结产品源码为 `de8ab759cce7b39e1c9e370960a383d307c1f9a3`，分支 `codex/business-system-bindings`。本地后续文档提交不改变部署产物。正式环境仍为 `5401215b845dfd09a2dd916fab9dfc37b2707b03`，未连接正式数据库。

| 项目 | 部署后结果 |
| --- | --- |
| TEST 地址 | `https://sx-kc.xyz:8444`，公开首页 HTTP 200 且内容哈希匹配候选 |
| API / worker | `iterflow-api:detail-activity-de8ab75`，config ID `sha256:dd2d6a5e02bd77f5c5ea5191e5d21c78950814ccb11dcc8a4f1d5e5e4e73e3c0` |
| Web | `iterflow-web:detail-activity-de8ab75`，config ID `sha256:bb636f16b76c578b32dc4ffaba2b514ff044d24da454e1f96d06b1fa9808ca98` |
| TEST 数据库 | `mysql57_0014`，32 张表、97 个触发器；没有迁移、seed、恢复或授权修改 |
| 部署四阶段 | `preflight`、`prepare`、`deploy`、`verify` 全部 PASS，无应用回退 |
| 正式保护 | 容器、配置、恢复保护文件及公开首页保护检查 PASS；正式数据库不连接、不写入 |

## 冻结、构建与上传

本地开发及原始验证见 `docs/detail-system-activity-2026-11-06.md`：前端全量 500 项、23 项相关浏览器用例与截图复查、PG 12 项、双 MySQL 各 1 项及静态/构建/契约均通过。部署准备再次执行 37 项相关前端测试、6 项契约测试、生成类型检查及 Web 构建，全部 PASS。既有 JSDOM 网络告警仍留在测试日志中。

按原 Dockerfile 构建 linux/amd64 API 和 Web，冻结源码与镜像标签一致；校验 API 165 个文件和 Web 162 个文件、离线归档 23 个镜像层，以及 OCI 索引与经典镜像 config ID 的对应关系。候选在服务器加载后再次逐文件校验，并验证 pip check、非 root 运行和数据检查脚本可读性。

通过宝塔文件管理正常上传 `iterflow-detail-activity-de8ab75-verified.tar`，117,340,160 字节；本地和服务器 SHA256 一致：

```text
905742de8fad74c98ba3fdafe3cc2e26a35689a2cb7dba4d0d93bea8c59233ef
```

配套 manifest SHA256 为 `57a25bfbc979ccc7e0122265c2993dc58de814bcaecf9325d6ed11a296610c24`。上传包包含镜像、manifest、镜像证明、控制与数据检查文件，不包含运行凭据。宝塔终端仅执行短控制命令，未用于文件或 Base64 传输。

## 部署与数据保留

1. 用户重新登录宝塔后，核对服务器身份、保留 TEST 项目、目标路径与数据库名称。此前公告部署保护检查 `BASELINE_PASS`，两环境基线、残留部署/构建任务检查通过。
2. `preflight` 记录旧应用、运行配置、逐服务 SMTP 指纹、TEST 数据结构与正式保护基线。`prepare` 保存旧 API/Web 镜像和配置、加载候选；此阶段 TEST 保持旧应用正常运行。
3. 仅 TEST 代理进入维护，停止 TEST worker/API/Web；对完整数据和附件生成只读快照，完成 SQL 与附件备份并校验归档。备份实际目录和 SHA256 记录在服务器 `data-backup.json`，目录格式为 `/opt/iterflow/backups/detail-activity-pre-<UTC>/`。
4. 只修改 TEST 镜像配置并启动新 API/Web。用应用实际运行账号验证 readiness 及 `sys_operation_log` / `sys_user` 联表读取，不修改账号权限。恢复 worker 前，32 张表完整行、账号会话、公告及已读、审计、结构/索引/外键/触发器和附件与停写快照完全一致。
5. 恢复 worker，核对每项服务运行配置、SMTP 指纹和健康；还原原 TEST 代理模板，使用已运行代理串行重载恢复流量。候选首页及正式保护复核通过，`deployed.json` 为 PASS。
6. 在线验收后执行 `verify`：新应用健康、运行账号查询、候选首页和原代理模板均通过；schema、索引、外键、97 个触发器、routine 及原附件继续保留。正式保护通过，`verified.json` 为 PASS。恢复流量后的正常登录会话及 worker 处理允许产生正常行变化，不以全库行哈希不变作为验收断言。

无数据库恢复或降级，无正式应用切换、重启服务器、宝塔修改、Git 推送/合并或 tag/Release。

## 在线验收

使用既有合成账号 `ceshi002` / `ceshi012`，通过正常 HTTPS API 和页面读取已有 TEST 对象。没有新增、编辑、删除、流转或发布业务对象，没有主动发送邮件；正常登录会写入账号会话。

| 场景 | 实际结果 |
| --- | --- |
| 反馈 23 | 业务系统保持空归属，展示“未指定”；最近操作人正确，3 条摘要与完整审计一致，revision 2 不变 |
| 需求 1 | 返回并渲染最近 10 条，完整审计仍有 17 条，revision 16 不变；时间相同时按日志 ID 倒序 |
| 需求 34 | 详情、列表抽屉和版本中的需求摘要均展示“中文验收系统”；最近操作展开/收起正常，摘要不展示需求进度 |
| 版本 27 | 展示“中文验收系统”和最近操作人；3 条摘要与完整审计一致，revision 3 不变 |
| 返回字段 | 仅日志 id、动作、操作者最小摘要和时间，无审计原始 payload；操作者与完整审计一致 |
| 访问控制 | 三类匿名请求 401，不存在对象 404；无审计中心权限成员访问 `/audits` 为 403，按其已有业务查看权限和范围读取对象摘要正常 |
| 桌面 | 反馈/需求/版本详情、需求抽屉和需求摘要的系统归属、最近操作及折叠交互通过 |
| 375px | 需求十条记录、版本记录和需求摘要布局通过；页面宽度 375、scrollWidth 375，无横向溢出；临时视口已恢复 |

页面截图已复查。旧空归属保持“未指定”，没有自动回填；“仅展示十条”不删除或截断完整审计。在线未为本次只读展示增量重跑完整发布链、删除对象或构造新操作；这些边界由既有隔离测试覆盖。本轮未运行远端八项 CI，没有推送授权。

## 中断与修正

- 开始时 Safari 宝塔登录失效；用户通过原安全入口重新登录后继续，未绕过安全校验。
- 原生文件选择器首次粘贴未切换目录，旧归档仍被选中；在确认前改为设置路径并选择本轮准确文件，未上传旧包。
- 终端首次连接时目录切换未执行，随后在 root 主目录读取归档报不存在；只读确认工作目录后重做 SHA256，成功后才解包/执行控制文件。
- OCI 索引 ID 与 `docker load` 后 config ID 的差异在本地打包阶段明确映射并重新封装，保留原 manifest 和证明，没有修改产品代码。
- 切换及验收没有产品失败或回退；未以重复部署处理终端输出延迟。

## 回退与证据

本次未加迁移，可仅回退应用至旧 API/worker `iterflow-api:announcements-test-8f4e7db` 和 Web `iterflow-web:announcements-test-8f4e7db`，源码 `8f4e7db498736778e790e10ff8f95ef92f03c55a`。旧镜像、镜像 SHA256、原配置、代理模板、数据快照与备份回执保存在本次服务器证据目录。

如后续授权回退，须先核对当前 TEST/正式基线，进入 TEST 维护并停三个应用服务；保留回退当时完整数据快照，校验并恢复上述旧镜像配置。先启动 API/Web、证明当前数据未改变，再恢复 worker、原代理模板与流量，最后复核健康、SMTP 和正式保护。数据库保持 `mysql57_0014`，保留当前数据与附件；不得恢复本次备份覆盖验收后的数据。一次性 `deploy` 阶段不能当作回退入口或直接重跑。

服务器证据：`/opt/iterflow/upgrade-evidence/detail-activity-test-20261109/`。关键回执包括 `preflight.json`、`prepared.json`、`data-backup.json`、`data-before.json`、`data-preserved.json`、`deployed.json`、`post-acceptance-data-observed.json`、`verified.json` 及四阶段日志；维护起止时间以服务器维护/完成回执为准。

本地证据：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-09/detail-activity-test/`。包含构建/测试原日志、`verified-bundle-receipt.json`、镜像内容证明、控制文件、`online-after-qa.json`、`online-qa-details.json` 和桌面/窄屏实际 TEST 截图。完整服务器回执保留于服务器。
