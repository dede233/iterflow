# 筛选栏布局 TEST 部署（2026-11-16）

## 授权、范围与冻结

用户本次授权将筛选栏布局优化部署到保留 TEST `https://sx-kc.xyz:8444`，正式 `https://sx-kc.xyz:8443` 不动。本轮仅替换 TEST Web，不授权 API/worker、数据库迁移、seed、权限、真实业务录入、公告发布或正式部署。

本地提交 `27767133a052eeffc2d9e73d76d1a0a6464f877f`（`fix: improve inline list filter layout`）只包含共享筛选面板、一个布局 E2E 与开发验证说明三个文件。未提交用户原有文档清理或前次部署记录，未推送、合并、tag/Release。开发验证和早期失败见 [布局修复记录](list-filter-layout-2026-11-16.md)。

本轮从冻结提交 `git archive` 提取源码，校验归档条目无绝对路径、穿越和链接；宿主 `node_modules` 以 APFS 克隆复用，冻结与工作区 lockfile 已逐字节核对。Docker 构建按冻结 Dockerfile 执行 `npm ci`，不复用工作区源码。

允许本机资源仅一个静态容器 `iterflow-filter-layout-1116-static` 与随机 loopback 端口；不启动/访问数据库、不发邮件。现有 18 个容器（含已退出）身份、镜像、启动时间、状态与重启次数已快照。重型构建和浏览器串行，Playwright 最多 2 workers。

| 工作 | 执行者 / 模型 | 验收 | 状态 |
| --- | --- | --- | --- |
| 冻结、构建、回归、镜像证明与打包 | `filter_test_package` / 6.1 Sol xhigh | 冻结源码、最终镜像浏览器、HTTP/hash、原控制器安全测试、上传包哈希 | 完成，本地待服务器操作 |
| 服务器实时核对、正常上传、分阶段切换与 TEST 验收 | Safari 唯一 owner，协调者分派 | 真实基线匹配、受保护环境不变、实际 TEST 页面验收 | 完成，切换、线上验收与最终 verify 均通过 |

本机证据根：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-16/filter-layout-test/`。服务器固定证据根计划为 `/opt/iterflow/upgrade-evidence/filter-layout-1116`；下述旧镜像信息只作控制器预期门禁，必须由服务器 owner 本轮实时核对后继续。

- TEST 旧 Web 预期 `iterflow-web:close-confirm-1114`，来源 `db4c27a7a30e085dd6454ab028d18fcfdd584521`，classic ID `sha256:0c8e1ff719925773610ea9aad684df309efee5239d850ce96654f50a80431fc3`，首页 `27dd35834d65c73e3ba095e026f4e27125a0b53fd0ec34f349f7d0387c06591b`。
- TEST API/worker 预期继续 `iterflow-api:grouped-mini-test-af3445d`、来源/`BUILD_SHA` 为 `af3445dc38ec64d1e4b65b7e2bb54593a49ca8df`。
- 正式预期维持 `mysql57-d6cfb815d7e1`、API `BUILD_SHA=d6cfb815d7e1a240b7e2842842cc45f25348056a`，首页 `5e35b7aa395ad244496830eec9d3459987edba8b7a9884f446950cba473321e7`；旧正式 Web OCI 标签来源为既有 `eb142eabcc0a3e282aea6f1e5592cfe773e86321`，不能把它误写成 API 的 BUILD_SHA。

## 本机准备

以下本轮执行结果均绑定冻结 SHA `27767133a052eeffc2d9e73d76d1a0a6464f877f`；完整参数、UTC 起止时间、退出码见 `commands.json`，各阶段日志保留在证据根。

| 层级 / 范围 | 实际命令 | 结果 / 证据 |
| --- | --- | --- |
| 契约生成一致性 | `npm run check:api-types` | PASS，`api-types.log` |
| 类型与构建 | `npm run build`（含 `vue-tsc --noEmit`） | PASS，`build.log` |
| 产物预算 | `npm run check:bundle` | PASS，最大 JS 400.0 KiB，`bundle.log` |
| 镜像 | 冻结源码 `docker build --platform linux/amd64 --label org.opencontainers.image.revision=27767133a052eeffc2d9e73d76d1a0a6464f877f --tag iterflow-web:filter-layout-1116 .` | PASS，`image-build.log` |
| 最终镜像静态内容 | `python3 verify-running-image.py` | PASS：全部 141 文件 HTTP/hash；冻结 dist 140 文件逐字节相同，唯一基础文件 `50x.html` 与前次固定镜像文件 hash 相同；Nginx 配置一致、非 root uid 101。`image-http-corrected.log`、`final-image-http.json` |
| 浏览器 / Mock | `ITERFLOW_WEB_URL=http://127.0.0.1:32769 npm run smoke:browser -- list-productivity list-filter-options list-filter-layout create-close-protection --workers=2 --output=<证据根>/browser-artifacts --reporter=line` | PASS，25 项列表回归 + 7 项关闭保护，共 32 项，`browser.log` |
| 浏览器 / Mock / 响应式 | `ITERFLOW_WEB_URL=http://127.0.0.1:32769 ITERFLOW_FILTER_LAYOUT_EVIDENCE_ROOT=<证据根>/gallery/screenshots npx playwright test --config=<证据根>/gallery/playwright-gallery.config.ts --output=<证据根>/gallery-artifacts --reporter=line` | PASS，反馈/需求/版本/发布记录 × 1440/900/375px，共 12 项，`gallery.log` |
| 离线镜像证明 | `python3 save-image.py`、`python3 build-image-proof.py` | PASS，核对归档各 blob、解压层 diff ID、amd64 manifest/config 和 OCI/classic 身份，`image-save.log`、`image-proof.log` |
| 控制器安全 / 离线 Mock | `python3 test_controller.py` | 原 20 项全部 PASS，`controller-tests.log`；未运行 Docker/systemd/数据库命令 |
| 资源清理 | `python3 cleanup-static.py` | PASS，仅移除本任务静态容器；原 18 容器身份、镜像、启动时间、状态、重启次数前后一致，`cleanup-result.json` 与前后快照 |

8 文件 / 75 项单测复用开发阶段先前工作区结果，本轮冻结提交未重跑；原日志在 `/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-16/list-filter-layout/unit.log`，身份与限制记录于 `reused-unit-evidence.json`，不能当作冻结 SHA 上新运行的单测。

首次静态核验在我新增的“镜像文件路径集合必须等于 dist”断言停止（退出 1）；基础 Nginx 本就有 `50x.html`，因此 image 为 141 文件、dist 为 140 文件。保留 `image-http.log`、`image-http-initial.log`、`verify-image-initial.py` 与说明。修正只把唯一基础文件明确列出并核对其 hash，同时保留全部 140 dist 内容逐字节比较和 141 HTTP/hash，使用原已创建容器继续，不增加容器。修正后通过，不是产品或控制器失败。

最终镜像截图在 `gallery/screenshots/`；执行代理实际查看 1440/900px 需求、900px 版本、375px 需求，确认左侧同排标签、搜索提示完整、自然换行、日期标签及移动抽屉无裁切。主协调者独立查看本轮最终镜像 1440px 需求截图并复核 HTTP、32 项浏览器、12 项 gallery 原始结果及控制器差异。

浏览器访问真实最终镜像静态文件，但业务 API 全部为 Playwright 内存 Mock；没有访问保留后端或数据库、上传附件或发送邮件。不代表真实后端主链、全量数据/结构、S3、备份恢复、MySQL 双矩阵或完整八项 CI 验收；本轮局部前端布局变更未运行这些无关门禁。

## 最终上传包

- 本机文件：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-16/filter-layout-test/iterflow-filter-layout-1116.tar`，23,214,080 字节。
- 包 SHA256：`544d795aef80641d3061ba33755ad72cee55adcf5a5165d462deb9a9622593b8`。
- manifest SHA256：`9831f01f8c275242908212de5bb171d0dca9badb6485f5f1c5d53180cac4ba42`；controller SHA256：`b52590d483dd15d3d18b2fa8fc41ec332e49cd93ded650273a444eda740ec537`。
- 外层仅含 `deploy-web.py`、`manifest.json`、`image-identity-proof.json`、`web-image.tar.gz` 四文件，重新打开归档并逐文件与 package 冻结内容核对。
- `linux/amd64` 镜像 `iterflow-web:filter-layout-1116`；OCI index `sha256:f20ef4c47f6373af51529b0286005b6c4805ee2b4ef16eb222c324a5b8af6705`，classic config `sha256:793a571156066b07ff9fe86b81af8885dda583dd1c52d0bdbfe4fd6e3051525a`；服务器载入可能显示后一 ID，控制器只允许已证明的两者，并检查架构、来源与全部 RootFS diff ID。
- 新首页 SHA256：`e7e670e68b7455921d3150d6c35468c5b343a4ee49ac9320a55c098d5fb0e741`。
- 完整汇总：`local-preparation-result.json`；镜像、冻结源码与证据保留；本任务临时静态容器已清理。

## 服务器执行边界

复用前次 guarded `deploy-web.py`，仅适配本轮路径、新来源/镜像、旧 Web 来源/镜像/ID/首页常量。Compose、API BUILD_SHA、正式与 TEST 非 Web、残留任务、独占锁、已执行状态和回退保护保持原逻辑。协调者已独立核对 `controller-adaptation.diff` 的变更范围；本机产物验证为执行代理自审，不能称为完整独立产品审查。

只能经宝塔正常文件管理上传打包文件；禁止网页终端传包、脚本或 Base64。上传后单独核对冻结包 SHA256，再解包；每阶段读实际输出与收据后才能推进。

控制命令必须使用绝对路径 `python3 /opt/iterflow/upgrade-evidence/filter-layout-1116/deploy-web.py <phase>`，依次 `preflight` → `prepare` → `deploy` → `verify`，stdout 重定向到本轮证据目录。上次相对路径 `prepare` 命中 residual_guard 自身，本轮沿用保护并修正调用方式，不放宽 guard。

只改 TEST `WEB_IMAGE`，Compose 限定 `web`、`--no-deps --no-build --pull never`，健康后仅 reload TEST 代理。失败路径只允许回到本轮备份的 `iterflow-web:close-confirm-1114` 与 `images.env.before`，且旧镜像、配置和保护指纹须仍一致；不恢复数据库、不停/重建后端。保护失败保留现场。

## 服务器执行与验收

宝塔登录最初失效，用户重新登录并打开终端后恢复。Safari 唯一 owner `filter_test_ui`（6.1 Sol / xhigh）实际核对服务器 hostname 为 `iZ2zehrcw9x4jxbjd1mfqaZ`，TEST Web/API/worker 与正式 Web/API/worker 镜像符合预期，TEST 数据库与 Redis 健康；本轮目录不存在，未覆盖残留。

通过正常文件管理上传 23,214,080 字节部署包，服务器完整 SHA256 与冻结包一致。控制器使用绝对路径执行。

| 阶段 | UTC 时间 | 结果 |
| --- | --- | --- |
| preflight | 2026-11-16 04:22:19 | PASS；source / manifest SHA 与冻结产物一致；旧 Web 来源 db4c27a、API 来源 af3445d；TEST 与正式均 HTTP 200，首页 hash 与上述预期一致，database_commands=false |
| prepare | 2026-11-16 04:23:22 | PASS；旧 Web 已备份，新镜像 classic ID 与冻结证明一致，141 文件核对及保护检查通过 |
| deploy | 2026-11-16 04:24:20—04:24:37 | PASS；仅切换 TEST Web，production_unchanged=true、test_non_web_unchanged=true、database_commands=false |
| 首次 verify | 2026-11-16 04:25:13 | PASS；收据另存 verified-before-ui.json 保留 |
| 线上验收后 verify | 2026-11-16 04:27:53 | PASS；源码及新镜像匹配，正式与 TEST 非 Web 保护一致，无数据库命令 |

旧 Web 备份 `old-web-image.tar` SHA256 为 `d6f34a55add0a1a4d2b5edea77918436b92bf8a7aa0bea4d408836791f05aef3`，旧镜像 `close-confirm-1114` / classic ID `0c8e1ff7…` 与基线一致。切换阶段收据跨度 17 秒，不等于精确请求中断时长。

以上为 UI owner 读取可见终端收据后转录的结果，不冒充下载的服务器原始文件；原始日志与收据保留在服务器固定证据目录。本机打包代理未操作 Safari 或服务器。

## 真实 TEST 桌面验收与交付

使用已有 TEST 登录会话，在桌面 Safari 实际操作，未保存业务记录：

- 需求原有 38 条。展开高级筛选后标签均在左侧、间距清晰，版本和参与人搜索提示完整；下拉打开及 Esc 关闭正常。临时不匹配关键词查询产生已应用筛选和 0 条结果，重置后关键词及 URL 条件清空，恢复 38 条。
- 反馈 23 条，基础条件及高级类型/紧急度显示正常，标签与提示无遮挡。
- 版本 31 条，日期范围起止文字和负责人提示完整；打开日期双月面板后 Esc 关闭，未选日期或修改业务。
- 发布记录 15 条，版本 ID、发布日期保持同排，间距及日期起止提示完整。

这些数量仅是本次可见列表结果，不是全量数据库数据审计。线上仅桌面 Safari；1440/900/375px 全视口自动化证据来自本机最终镜像 + Mock API，未将其称为线上移动端实测。没有在线真实后端主链写入测试、数据库查询/迁移/备份恢复、附件上传或邮件发送。

最终核验于北京时间 **2026-11-16 12:27:53** 通过：正式环境、TEST API/worker/数据库/Redis 容器及受保护配置维持切换前基线；TEST Web 来源 `2776713`、镜像及首页 hash 匹配冻结产物。保护检查以容器身份、启动时间、挂载、环境/配置指纹等为证，不代表全量数据库内容和结构逐项比对。

本机 UI 转录文件包括 `ui-operator-preflight-receipt.json`、`ui-operator-preparation-receipt.json`、`ui-operator-deploy-receipt.json` 以及最终汇总；这些均明确标注非服务器原始文件下载。服务器原始收据保留于固定证据目录，首次与最终 verify 分开保留。本轮服务器阶段没有失败或回退。

状态：**完成 TEST 部署与线上桌面验收，等待用户验证**。仅 TEST Web 被替换，正式环境未改动，未执行数据库命令、推送、合并或 tag/Release。Safari 保留空闲宝塔终端与 TEST 发布记录页，临时筛选条件已清空，浏览器 owner 已交回；本次 CUA 完成摘要已调用一次。
