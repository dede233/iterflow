# 哈希导航确认修复 TEST 部署（2026-11-16）

## 授权与冻结范围

用户授权将确认框修复部署到保留 TEST `https://sx-kc.xyz:8444`，补验“继续编辑 / 放弃修改”，正式 `https://sx-kc.xyz:8443` 不动。本轮仅替换 TEST Web；API/worker、数据库、Redis、数据卷、附件、SMTP/JWT、账号/会话、公告/已读、审计与历史保留。不执行数据库命令、迁移、seed、GRANT、恢复或真实业务录入。

冻结源码 `13e2c67cc00839fe94bbc9e323c5984588338fed` 包含已验收三组 UI 与 `closeOnHashChange: false` 一行运行修正。后者防止 Element Plus 在哈希返回时自动隐藏确认框、留下未完成导航；相应单测与 E2E 保留继续编辑、草稿/URL 和明确放弃的断言，详见 [上线准备及失败记录](ui-production-preparation-2026-11-16.md)。本轮不提交、推送、合并或创建 tag / Release。

使用全新 `git archive`，SHA256 `20f0fc5ddd831b938a202c6e43a0fbb20b1349f8e62779cf6e07c9253e1438df`，与此前冻结归档一致；条目仅普通文件/目录，无绝对路径、穿越或链接。原工作区根文档整理不纳入。原样提取文件在本机门禁后逐字节重核；native 依赖在 lockfile 完全相同后 APFS 克隆，Docker 另按冻结 Dockerfile 的 `npm ci` 构建。

本机 owner `ui_readiness_gate`（6.1 Sol / xhigh）仅有一个临时 `hash-confirm-1116-static` 容器与随机 loopback 端口；构建、浏览器串行，单浏览器进程最多 2 workers。原 18 容器先后快照；没有启动或访问本机数据库、保留容器服务或邮件。服务器/CUA 由独立 UI owner 负责，本机 owner 未访问 Safari 或服务器。

本机证据根：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-16/hash-confirm-test/`；服务器证据根：`/opt/iterflow/upgrade-evidence/hash-confirm-1116/`。

## 预期环境与本机验证

旧 TEST Web 预期 `iterflow-web:filter-layout-1116`，来源 `27767133a052eeffc2d9e73d76d1a0a6464f877f`，classic ID `sha256:793a571156066b07ff9fe86b81af8885dda583dd1c52d0bdbfe4fd6e3051525a`，首页 `e7e670e68b7455921d3150d6c35468c5b343a4ee49ac9320a55c098d5fb0e741`。TEST API/worker 继续 `iterflow-api:grouped-mini-test-af3445d` / `af3445dc38ec64d1e4b65b7e2bb54593a49ca8df`；正式保持既有 `mysql57-d6cfb815d7e1` / API `d6cfb815d7e1a240b7e2842842cc45f25348056a`。这些常量是服务器实时复核门禁，不能用本机记录代替现场证明。

以下本轮结果绑定冻结 `13e2c67cc00839fe94bbc9e323c5984588338fed`，命令 UTC、退出状态见 `commands.json`，均通过：

| 层级 | 实际执行 | 结果 / 原始证据 |
| --- | --- | --- |
| 契约生成 | `npm run check:api-types` | PASS，`api-types.log` |
| 类型与冻结生产构建 | `npm run build` | PASS，`build.log` |
| 产物预算 | `npm run check:bundle` | PASS，最大 JS 400.0 KiB，`bundle.log` |
| 最终镜像 | 冻结源码 `docker build --platform linux/amd64 --label org.opencontainers.image.revision=13e2c67cc00839fe94bbc9e323c5984588338fed --tag iterflow-web:hash-confirm-1116 .` | PASS，`image-build.log` |
| 镜像静态内容 | `python3 verify-running-image.py` | 141 文件 HTTP/hash 全过；140 个冻结 dist 文件逐字节相同，唯一基础 `50x.html` 与前次固定镜像文件 hash 相同；Nginx 配置一致、uid 101，`image-http.log`、`final-image-http.json` |
| 最终镜像 / Mock 浏览器 | 三文件 `create-form-layout.spec.ts`、`system-catalog.spec.ts`、`create-close-protection.spec.ts`，`--workers=2` | 32 PASS，0 skip/flaky/unexpected；含 1440/375px 真实 UI 历史浏览器后退的继续编辑与放弃两分支，`browser.log`、`browser-results.json`、`browser-artifacts/` |
| 离线镜像证明 | `save-image.py`、`build-image-proof.py` | 所有 blob、压缩层 diff ID、amd64 manifest/config、OCI/classic 身份一致，`image-save.log`、`image-proof.log` |
| 控制器安全 / 离线 Mock | 原样 `python3 test_controller.py` | 20 PASS，`controller-tests.log`；无 Docker/systemd/数据库命令执行 |
| 资源清理 | `python3 cleanup-static.py` | 仅定点移除本任务容器，原 18 容器身份/镜像/启动时间/状态/重启次数不变，端口已关闭，`cleanup-result.json` |

浏览器访问最终镜像，业务 API 全为内存 Mock；trace HTTP host 仅 `127.0.0.1:32770`，没有访问真实后端、保留环境、数据库、上传附件或发邮件。这不冒充真实 TEST 线上验收、主链写入或全量数据审计。

已有同 SHA [完整八项 CI run 43812420717](https://github.com/dede233/iterflow/actions/runs/43812420717) 均成功，本轮引用、不重跑；身份及原始证据引用见 `reused-ci-evidence.json`。本轮没有以新镜像局部回归冒称重新运行完整 CI。

## 冻结上传包与控制器

- 包：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-16/hash-confirm-test/iterflow-hash-confirm-1116.tar`，23,214,080 字节，SHA256 `ec0b57e140fc6c1f7c200fd02d35d160711308239fbd8d32286b53fb46d3f51d`。
- manifest SHA256 `e75aa03d5bad05fdd09a5fc21ea387f57d068872932dfa0eea0aa77d2fb7083a`；controller SHA256 `def32f1870071863c500f0934d8e0c526c318402c92f85f4dff0f12fbfb6832e`。
- 外层严格只有 `deploy-web.py`、`manifest.json`、`image-identity-proof.json`、`web-image.tar.gz`；重新打开 tar 逐文件与冻结 package 字节核对。
- 新镜像 `iterflow-web:hash-confirm-1116`（linux/amd64）；OCI index `sha256:bc32b1312cb4963c30c79164c9391b2e14c96409f69ef7b36a0b34130b23ca34`，classic config `sha256:3e098d4d5db201a50bf8a90f6444cd66313579e9b96667c7a908c9cf7ac04993`，platform manifest `sha256:dec3a24f741aeccc9a09bd3e7f104951f64a6baff1f323230aab0e53e36285d7`。全部 RootFS diff ID 见冻结证明，控制器仅接受已证明两种身份并检查来源/架构/全部层。
- 新首页 SHA256 `9ac225e54dc566459979b3c42bc4321e7a3da4194aab265cfeb211f88097da51`。汇总 `package-result.json`、`local-preparation-result.json`；镜像、冻结源码与证据保留。

复用上一轮 guarded 控制器，仅改 `BASE / SOURCE / OLD_WEB_SOURCE / WEB / OLD_WEB / OLD_WEB_ID / OLD_INDEX` 七个常量。归一这些常量后 AST 与原版完全一致，Python 3.6 语法解析通过，原 20 安全测试原样运行。`controller-adaptation.diff`、原日志、tar/hash/四文件一致性已由主协调者独立核对；这是包与控制器复核，不称为本轮重新做全面产品审查。

只能正常文件上传，不能网页终端传文件、脚本、Base64 或缩小分块。服务器单独核对完整包 SHA256 后解包。控制命令使用绝对路径 `python3 /opt/iterflow/upgrade-evidence/hash-confirm-1116/deploy-web.py <phase>`，依次 `preflight -> prepare -> deploy -> verify`，每阶段读取真实日志/收据再继续；不得用相对路径触发残留检查自身误判或放宽 guard。

只修改 TEST `WEB_IMAGE`，原 Compose 限定 `web --no-deps --no-build --pull never`，健康后只 reload TEST 代理。失败仅允许在旧镜像、当次配置备份、正式及 TEST 非 Web 保护指纹不变时恢复本次旧 `filter-layout-1116` Web 和 `images.env.before`；不恢复数据库，不停/重建后端。`rollback()` 是内部失败路径，没有公开 rollback CLI；保护失败保留现场。

## 服务器执行与线上验收

服务器 UI owner `hash_confirm_test_ui`（6.1 Sol / xhigh）独占 Safari。实时核对 hostname、两环境镜像/来源及首页 hash 均与上述基线一致，无遗留部署/构建/载入进程；新证据目录原不存在。通过宝塔正常文件管理上传包，服务器完整 SHA256 与冻结包一致，核对四个普通文件后使用不覆盖已有文件的方式解包。未通过终端传文件、脚本或 Base64。

| 阶段 | 实际 UTC 时间 | 结果 |
| --- | --- | --- |
| preflight | 2026-11-16 06:22:58 | PASS，manifest/source 匹配，两环境首页 HTTP 200 及 hash 一致 |
| prepare | 2026-11-16 06:23:24 | PASS，旧 Web 已备份，新镜像身份及 141 文件校验通过 |
| deploy | 2026-11-16 06:23:56—06:24:09 | PASS，仅替换 TEST Web，正式及 TEST 非 Web 保护一致 |
| 首次 verify | 2026-11-16 06:24:44 | PASS，另存 `verified-before-ui.json` |
| 线上补验后 verify | 2026-11-16 06:29:12 | PASS，来源/镜像/首页匹配，保护一致，无数据库命令 |

旧 `filter-layout-1116` 镜像备份 `old-web-image.tar` SHA256 为 `d0a21bd446d7d0daf0da3296424c80fba620f71358cac3a0832b60446334a16d`，当次配置及原始收据留在服务器证据目录。部署收据的 13 秒跨度不是精确请求中断时长。本轮没有服务器阶段失败或回退。

线上使用真实 TEST 后端与既有管理员会话，在桌面 Safari 完成以下操作，未保存业务记录：

1. **需求原生返回**：从实际需求列表打开 `REQ-20261105-0003`（ID 34）的抽屉，再通过“打开完整页面”建立 Router 历史。编辑标题，追加未保存测试文字；使用 Safari 返回出现确认框，选择“继续编辑”后恢复原详情 URL、编辑弹窗及完整测试标题。再次返回并选择“放弃修改”，正常回到 38 条需求列表。重新打开同一需求，原标题、描述、待确认状态及显示更新时间 `2026年11月5日 14:34` 均未改变。
2. **反馈导航离开**：新标签完整加载反馈新建页，填写未提交测试标题；通过实际侧栏 RouterLink 离开。选择“继续编辑”后页面 URL 和标题保留，再次离开并选择“放弃修改”，返回 23 条反馈列表。此项为真实应用内导航，未声称测试了反馈原生浏览器返回；原生哈希返回由上一项需求覆盖。
3. **反馈 Esc**：从列表打开提交反馈弹窗，填写测试标题，按一次 Esc 出现确认框；选择“放弃修改”后回到列表，仍为 23 条。没有提交、上传附件、发布或发送邮件。

需求返回确认、继续编辑保留标题及反馈导航确认等截图由 CUA 内联取证；工具没有已文档化的截图文件保存接口，因此没有导出本机 PNG，也未绕过工具另行导出。线上仅桌面 Safari；375px 证据来自本机最终镜像与 Mock API，不冒充线上手机实测。可见列表数量与重新读取字段不等于全量数据库内容/结构审计。

本机 `ui-operator-*-receipt.json`、`ui-operator-deployment-result.json` 及 `ui-online-acceptance.json` 为 UI owner 读取可见终端收据/页面后的转录，非服务器原始文件下载；主协调者已核对这些转录、冻结包和本机原始日志。服务器原始阶段输出/收据、旧 Web 与配置备份继续保留。

最终核验于北京时间 **2026-11-16 14:29:12** 通过，TEST Web 来源为 `13e2c67`。正式环境、TEST API/worker/数据库/Redis 及受保护配置均维持切换前基线；未执行数据库命令或业务提交。所有临时本机验证资源已清理，Safari 无未保存表单，临时反馈标签已关闭，宝塔终端空闲；CUA 完成摘要已调用一次并交回 owner。

状态：**TEST 部署及返回确认补验完成，等待用户验证**。本轮仅新增本部署记录，无提交、推送、合并、tag / Release 或正式部署。
