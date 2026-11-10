# UI 与发布覆盖 TEST 部署（2026-11-10）

## 结果与范围

用户授权部署到保留 TEST，并在宝塔登录失效后重新登录、打开终端。本轮已完成部署和在线验收，保留新版供用户验证。正式环境未切换，未连接正式数据库；没有推送、合并、tag 或 GitHub Release。

冻结产品源码 `097b2dd8fffce6edbf29ea08e9aee212cef1c092`，分支 `codex/multi-target-release`。后续文档提交不改变已部署源码。

本批包含：发布目标改为实际覆盖记录（正常发布时可选、发布后可多选补记，不阻塞版本上线）；此前 UI 基础、列表、详情、表单、首页与移动端优化；需求新建/编辑最大宽度 1040px、弹窗内容独立滚动及底栏防遮挡；选择器空 footer 按需隐藏；输入焦点仅保留外层 wrapper 蓝框。

| 项目 | 实际结果 |
| --- | --- |
| TEST | https://sx-kc.xyz:8444，HTTP 200、首页 SHA256 匹配候选 |
| 原 TEST | API/worker/Web `2b9fd16fca66253d0c7323e54cb00bdd66da3226` |
| 新 API/worker | `iterflow-api:ui-coverage-test-097b2dd`，config ID `sha256:b5e2a130860aecabfc88de5b3841375f7d75ee523fb850904c4efe9888e34e0e` |
| 新 Web | `iterflow-web:ui-coverage-test-097b2dd`，config ID `sha256:ed67b1b479baf8a0ac7419f239c86143c7d01a67011159c221d7b8fa57467843` |
| TEST 数据库 | 保持 `mysql57_0015`，35 张表、110 个触发器；无迁移、seed、权限修改、真实数据库恢复或降级 |
| 部署阶段 | preflight / prepare / deploy / verify 全部 PASS，无回退 |
| 正式保护 | 仍为 `5401215b845dfd09a2dd916fab9dfc37b2707b03` / `mysql57_0012`；容器、配置、恢复保护文件及公开首页保护通过；没有正式数据库连接 |

## 验证与冻结产物

部署准备本轮重新运行前端全量 509 项、构建（含 vue-tsc 类型检查）、产物预算及 diff 检查，均 PASS；amd64 镜像 pip check 与非 root 检查通过。

此前增量验证详见 `release-coverage-2026-11-10.md`、`ui-refinement-2026-11-10.md`、`ui-modal-form-fix-2026-11-10.md`：发布覆盖 PG 702 PASS / 1 S3 条件跳过及最终 36 项、双 MySQL 各 16 项、83 项相关浏览器和真实 Docker 主链；UI 226 项唯一分段浏览器及后续弹窗/宽度/footer/焦点专项。上述为既有开发证据，本轮没有重跑全部后端或远端八项 CI。

本地构建 linux/amd64 API 与 Web，逐项核对 API 171 文件、Web 138 文件和 23 个离线镜像层；明确 OCI ID 与经典 config ID 的映射。服务器加载后再次核对文件、镜像身份和运行配置。

正常文件上传包：`iterflow-ui-coverage-097b2dd-verified.tar`，117,032,960 字节；本地和服务器 SHA256 均为 `d4d89d1a2e69669c8b4d709be1048db0d66b8556b2c3f6ce09b1c9c171ddb520`。未用宝塔终端传输 Base64、文件块或长脚本，仅执行短控制命令。

新 Web 首页 SHA256：`0cfe287a047d3904dd4ba948c8ecc426d9f3176d3c41fc813d776b7b2adf30fc`。正式首页仍为 `6de008049443447852f98cefdc7312965ce81fb39ef34e45c42237a5fb8b1a4e`，验收后本机通过 HTTPS 再次验证两者 HTTP 200 及精确哈希。

## 切换与数据保护

1. 核对服务器身份、TEST/正式容器与配置、残留任务、目标目录和数据库名称。预检记录正式保护基线及逐服务 SMTP 指纹。
2. 保存旧 API/Web 镜像与配置，加载、校验冻结候选。此阶段旧 TEST 继续运行。
3. 仅 TEST 进入维护，停止 worker/API/Web；生成只读完整行与结构/索引/外键/触发器/routine/附件快照，备份 TEST SQL 和附件。备份后快照完全一致。
4. 启动新 API/Web，验证健康和实际运行账号查询。恢复 worker 前，35 张表完整数据（含账号会话、公告/已读、审计）及附件与停写快照完全一致。
5. 写入 worker 恢复标记，启动 worker，恢复原代理模板与 TEST 流量。逐服务配置/SMTP、公开首页与正式保护检查通过。
6. 在线验收后最终 verify PASS：新服务健康、readiness、运行账号查询、代理模板、schema/索引/外键/110 触发器/routine 和原附件保持；正式容器、配置与保护文件不变。正常登录、worker 和下列合成业务验收产生的行变化保留。

维护起止以服务器 `maintenance-attempted.json` / `deployed.json` 时间为准；本轮只观察到 TEST 维护期间 503、正式入口同时 200，不以工具耗时推算精确停服秒数。完整回执与备份位置保留于服务器。

## 在线验收

使用既有合成账号通过正常 TEST HTTPS API 创建需求 36（`REQ-20261110-0001`）及版本 29（`TEST-UI-COVERAGE-20261110`），无外部小程序/PC 发布行为。合成记录保留给用户查看。

| 场景 | 结果 |
| --- | --- |
| 需求主链 | 内容确认 → 开发 → 提交验收 → 验收通过，版本自动 READY，PASS |
| 发布时只选择目标 A | 版本 RELEASED、需求 ONLINE；未选择 B/C 不阻塞；产生唯一 Release 13 和一条目标记录，PASS |
| 发布后多选 B/C 补记 | 一次创建两条记录；合计三条，原 Release、实际上线时间和 ONLINE 状态保持，PASS |
| 并发与权限 | 重放旧 revision 返回 409；匿名补记 401；无权限成员补记 403；旧计划批次写入口 409，PASS |
| 历史兼容 | 既有合成版本 28、批次和三条成功目标记录与切换前读取结果完全一致，PASS |
| 桌面需求表单 | 1440px 视口下弹窗宽 1040px；内容与底栏分离、后续人员可展开；人员搜索单结果且无空 footer，PASS |
| 输入焦点 | 内层 input outline 为 none、boxShadow 为 none；外层 wrapper 保留蓝色焦点，PASS |
| 375px 需求表单 | 弹窗宽 343px，页面 scrollWidth 375；人员输入、选项和底部操作可见，PASS |
| 版本覆盖页面 | 展示三目标、两次记录、业务系统及最近操作；补记弹窗中已有目标已勾选/禁用；375px 无横向溢出，PASS |
| 需求摘要 | 展示需求编号、业务系统、内容、验收标准及最近操作，不展示进度步骤条，PASS |

桌面浏览器使用现有 TEST 管理员会话，只打开、搜索、查看和取消表单，没有额外提交。响应式视口已恢复。截图在稳定布局后保存和复查。

在线未新增 PC 类型目标、未接入外部发布平台或重跑 SMTP 收信测试；PC 类型和更多权限/竞争边界由既有本地隔离测试覆盖。邮箱配置按逐服务指纹保留，不把配置检查描述为本次邮件送达验证。

## 中断、修正与限制

- 宝塔会话最初失效，用户重新登录后继续；没有绕过安全校验或修改宝塔。
- 首次打包发现缓存 API 镜像是 arm64，在服务器切换前停止打包，保留 `stopped-arm64-precheck`，重新从冻结源码构建 amd64 后校验通过。
- 原生终端输入曾丢失首字符或拼接未执行的只读命令，失败仅涉及身份/哈希读取；改为短命令粘贴、观察文本后单独回车。正确校验归档后才解包执行。未重复执行 deploy。
- 在线脚本执行旧批次入口拒绝校验前，依据 schema 补齐必填 release_notes，确保测试真正命中旧入口门禁。无产品修改，无重复业务提交。
- 移动端切换视口后的首张截图处于过渡布局，等待后重新观察按钮实际边界与截图，两按钮无重叠；稳定截图覆盖临时截图。

## 回退边界与证据

本次没有 schema 迁移，但发布语义发生改变，不能据此认定旧应用无条件兼容。控制器只允许恢复 worker 之前、且所有行/附件仍完全匹配停写快照时自动回旧应用。worker 一旦尝试恢复，自动回退被阻止，须保留维护并前向修复，避免旧目标门禁重新解释新覆盖记录。

当前已完成新语义合成发布和补记，后续回退必须先单独审查数据语义兼容；优先使用保留新后端语义的修正版。旧 API/worker/Web `targets-test-2b9fd16` 镜像和原配置保留作为证据，不能直接重跑 deploy 或 restore_apps。禁止恢复旧数据库备份覆盖用户验收后的数据；任何后续线上变更按当次授权处理。

服务器证据：`/opt/iterflow/upgrade-evidence/ui-coverage-test-20261110/`，包含 manifest、镜像证明、旧镜像/配置、preflight/prepared、停写数据快照、data-backup、data-preserved、deployed、post-acceptance-data-observed、verified 及阶段日志。完整数据快照和备份只留服务器受限目录。

本地证据：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-10/ui-coverage-test/`，含测试/构建日志、amd64 镜像证明、verified-bundle-receipt、控制器及三项回退防护验证、online_qa.py、qa-*.json、public-final.json 和四张 TEST 页面截图。没有在仓库或本文写入密码、令牌或 SMTP 密钥。
