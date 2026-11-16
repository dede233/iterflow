# 三组前端改动上线准备（2026-11-16）

## 本轮授权与基线

用户已确认保留 TEST 体验无问题，要求将 UI 阅读与工作台、创建关闭确认、左侧标签筛选三组改动一起做上线准备，跑完八项 CI 并核对 master 无漂移，暂不切正式。本轮允许提交准备文档、非 force 推送当前分支及显式触发现有 CI；不合并 master、不创建 tag / Release、不部署任一环境、不操作服务器或真实数据库、不做业务录入或公告发布。

开始分支 `codex/ui-workspace-refinement`，HEAD 为 `27767133a052eeffc2d9e73d76d1a0a6464f877f`。本轮直接 `git ls-remote origin/gitee refs/heads/master` 的起始结果均为 `674d1d7d399140e0338125106f4c55a66c51044c`，与本地及缓存 master 一致，且为候选祖先。两端同名候选分支起始均不存在。完成时再直接读取两端 master；有漂移则停止交付无漂移结论并评估，不自动合并。

工作区已有根文档整理修改、删除和未跟踪归档，本轮已保留状态及内容 hash；不得暂存、覆盖或清理。准备提交仅包含本文及原先未跟踪的两份本轮相关 TEST 记录：[关闭确认 TEST](create-close-confirmation-test-deployment-2026-11-14.md)、[筛选布局 TEST](list-filter-test-deployment-2026-11-16.md)。分支中既已提交的规范与历史记录是已有候选内容，不等于把未提交根文档整理纳入本轮。

## 三组产品范围

| 改动组 / 产品提交 | 最终行为 | 既有验证记录 |
| --- | --- | --- |
| UI 阅读与工作台：`8633cb3`、`8b481bf` | 版本清单按需筛选；品牌矩阵与移动卡片；跨页实际发布覆盖及历史；需求容器响应式阅读、全屏编辑、字段首错和未保存保护；反馈/版本已应用筛选；首页本人参与待办 | [开发记录](ui-workspace-refinement-2026-11-11.md)、[补测与 TEST 部署](ui-workspace-test-deployment-2026-11-12.md) |
| 新增反馈/需求关闭确认：`6823606` | Esc、叉号、取消统一确认；连续 Esc 不绕过；继续编辑保留输入和附件；提交中禁止关闭及重复提交，失败保留输入 | [开发记录](create-dialog-close-protection-2026-11-12.md)、[TEST 部署](create-close-confirmation-test-deployment-2026-11-14.md) |
| 左侧标签筛选：`2776713` | 桌面/平板标签在控件左侧同排，按面板宽度自然换行，版本/参与人搜索提示和日期范围完整；移动抽屉保留上方标签，覆盖反馈、需求、版本与发布记录 | [开发记录](list-filter-layout-2026-11-16.md)、[TEST 部署](list-filter-test-deployment-2026-11-16.md) |

对既有正式源码 `d6cfb815d7e1a240b7e2842842cc45f25348056a`，产品差异仅在 `frontend/`（源码与测试共 50 文件）；`backend/`、`spec/`、`deploy/`、`tools/`、`scripts/`、`.github/` 无差异，无依赖锁升级或数据库迁移。不新增 API、权限、角色、持久化草稿或业务状态，不改变主链、CAS、RBAC / DataScope、发布事务及历史快照。

准备提交须逐路径证明产品与已验收 TEST Web 的冻结源码 `2776713` 完全一致。CI 如发现必须修复的实现或测试问题，先记录失败与根因、核对修复范围，再对新最终 HEAD 重新执行完整八项，不能复用旧 SHA 的通过结果。

## 环境与既有证据的层级

以下为既有部署记录，不是本轮重新访问服务器的结果：

- 最近 TEST 核验于 `2026-11-16T04:27:53Z` 完成：Web 来源 `2776713`，API/worker 来源 `af3445dc38ec64d1e4b65b7e2bb54593a49ca8df`，数据库沿用 `mysql57_0016`。仅 TEST Web 被替换。
- 正式受保护应用基线为 `mysql57-d6cfb815d7e1`，API `BUILD_SHA=d6cfb815d7e1a240b7e2842842cc45f25348056a`；旧正式 Web OCI 标签来源单独为 `eb142eabcc0a3e282aea6f1e5592cfe773e86321`，不能混用为 API 来源。正式首页既有 SHA256 为 `5e35b7aa395ad244496830eec9d3459987edba8b7a9884f446950cba473321e7`。未来正式执行前必须现场重新核对。
- UI 组既有补测含 136 项 Mock 浏览器、4 项真实隔离后端主链和 4 项布局回归；关闭确认既有 TEST 桌面实测与本机 375px / 提交失败 / 附件保留 Mock 证据；筛选既有最终镜像 32 项 Mock 浏览器及四列表 × 三视口 12 项布局检查。各自首次失败、修正和限制保留在对应记录，不当作本轮重跑。
- 最新 TEST 线上仅桌面 Safari 实测，未保存业务数据；移动端证据来自本机最终镜像与 Mock API。容器、配置和入口保护结果不等于全量数据库数据/结构逐项核验；UI/终端转录摘要不冒充下载的服务器原始收据。

已验收 TEST Web 镜像为 `iterflow-web:filter-layout-1116`（linux/amd64），OCI index `sha256:f20ef4c47f6373af51529b0286005b6c4805ee2b4ef16eb222c324a5b8af6705`，classic config `sha256:793a571156066b07ff9fe86b81af8885dda583dd1c52d0bdbfe4fd6e3051525a`，首页 SHA256 `e7e670e68b7455921d3150d6c35468c5b343a4ee49ac9320a55c098d5fb0e741`。原 TEST 包 SHA256 为 `544d795aef80641d3061ba33755ad72cee55adcf5a5165d462deb9a9622593b8`，其 TEST 专用控制器不得直接用于正式。后续正式包须按当时正式基线生成控制器，证明产品与冻结候选相同，禁止复制 TEST 路径、配置或数据。

## 同 SHA 八项 CI 与最终回执

当前 `.github/workflows/ci.yml` 展开为八项：`backend`、`frontend`、`docker_smoke`、`s3`、`browser_smoke`、`backup_restore`、`mysql57 (standard)`、`mysql57 (portable)`。完整候选须八项均为 `success`；不得以历史 TEST、本机局部验证、另一 SHA 或未展开矩阵的六项替代。CI 使用 GitHub 一次性 runner 上的隔离服务，本轮不启动本机重型测试、数据库或浏览器。

本分支不在 push 自动触发列表内。推送候选后，使用已配置 `gh workflow run ci.yml --ref codex/ui-workspace-refinement` 显式 dispatch；现有 GitHub 连接器无 dispatch 能力，协调者另经连接器复核结果。先检查同候选是否已有活动 CI，本轮最多一个完整 CI run 活动；每个 run 必须核对 `head_sha` 等于最终候选，并归档 job JSON 与原日志。失败先分类，保留首轮日志；不弱化断言、跳过失败或修改发布门禁。

本轮证据根：

`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-16/ui-production-preparation/`

其中 `commands.json` 和原始命令日志记录 UTC 起止时间、退出码、Git 起止核查、源码范围与无关工作区保留；最终候选、远端分支一致性、run / job URL、八项结论及失败处理写入外部 `readiness-result.json`、`readiness-report.md`。本文不嵌入自身提交 SHA，避免为记录结果继续提交而使 CI SHA 失效。准备提交后不得仅为补记 CI 结果改变 HEAD；若 HEAD 再变，须重跑新 HEAD 的完整八项。

## 后续正式 Web 升级清单（本轮不执行）

1. 取得对应正式执行授权后，重新核对最终候选、完整八项与双远端 master；合并/同步如在授权内执行，须完成最终 master 自身完整八项。现场核对主机、正式与 TEST 各服务、残留任务、镜像、配置、健康、资源和恢复条件，不从本文件推断实时状态。
2. 冻结正式 Web 产物与 SHA，按现场正式基线准备并审查独立控制器，保留 TEST。备份旧正式 Web 镜像、Compose / 环境 / 代理 / 恢复配置，核对既有数据库与附件备份及保留要求；不输出 SMTP、JWT、数据库密钥等明文。只能正常上传文件或使用已核验身份的 SSH/SFTP，网页终端只运行短控制命令。
3. 本批只替换正式 Web，保持 API/worker、数据库、Redis、卷和附件，不迁移、不 seed、不 GRANT、不恢复数据库、不导入 TEST 数据；逐服务 SMTP/JWT、账号/会话、公告/已读、审计和历史 Release 全部保留。切换使用原 Compose 项目的 Web 服务，限定 `--no-deps --no-build --pull never`，健康后只 reload 对应正式代理。
4. 切换前后对比正式非 Web 与整个 TEST 的容器身份、启动时间、挂载、环境/配置指纹和入口；验证新 Web 镜像来源、静态文件 HTTP/hash、健康和缓存资源可加载。沿用真实账号只读验收三组页面，不创建合成业务数据、不模拟发布、不群发邮件或发布更新公告。
5. 本轮不需要真实库备份或恢复演练，也未执行；真实环境现场核对、备份与任何正式切换均留待后续对应授权。Web 准备的 CI 隔离备份恢复作业不能冒称正式真实数据备份或演练。

## 回退边界

- 本批没有后端、契约、依赖或数据结构变化。正式 Web 切换失败时，仅在旧 Web 镜像、当次配置备份和非 Web / TEST 保护指纹均仍一致的条件下，恢复本次备份的旧正式 Web 与原入口配置，再核对健康、旧首页和受保护环境。
- 回退只涉及 Web，不停止/重建 API、worker、数据库或 Redis，不删除数据、附件、会话、公告/已读或审计，不恢复数据库。保护失败或出现他人配置漂移则保留现场，先评估再继续，不能无条件覆盖。
- 旧 Web 回退会撤去本批阅读、关闭确认与筛选体验，不把这一展示变化误称为数据丢失；既有品牌/平台、实际发布覆盖、唯一 Release、原上线时间及通知规则仍由保留后端维持。不能借回退恢复已废止业务语义。

准备通过表示三组前端改动可进入后续上线流程；本轮不代表已合并、已发布或已切换正式。
