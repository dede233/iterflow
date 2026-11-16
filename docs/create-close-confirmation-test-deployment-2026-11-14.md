# 新增反馈与需求关闭确认 TEST 部署（2026-11-14）

本轮用户授权将新增反馈与需求关闭确认修复部署到保留 TEST，正式环境不动。不推送、合并或创建 tag / Release，不执行数据库命令、迁移、seed、GRANT 或恢复，不新增或保存业务数据。

## 冻结范围

- 冻结源码为 `db4c27a7a30e085dd6454ab028d18fcfdd584521`，关闭保护产品提交为 `6823606`。通过 `git archive HEAD` 导出，未纳入用户正在进行的未提交根文档清理，也未暂存或提交该清理。
- 对已部署 TEST Web `8b481bf2aa59504202a196242646e0105c7eb955`，产品差异只在前端关闭保护与相关测试；后端、契约、部署模板和工具无产品变更。
- 本轮仅替换 TEST Web 为 `iterflow-web:close-confirm-1114`；TEST API/worker 继续 `grouped-mini-test-af3445d`，原 `images.env` 的 API `BUILD_SHA=af3445d` 保留。旧 Web 回退来源单独固定为 `8b481bf`，不混用 API 来源。
- 正式环境保护仍以既有 `mysql57-d6cfb815d7e1` 容器、配置与入口指纹为准，执行前由服务器 owner 重新核对。历史状态不是本轮实时证明。

本机交付目录：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-14/close-confirmation-test/`。本机唯一临时静态容器 owner 为 `close_test_package`，不得操作既有预览容器、数据库或其他任务资源；重型任务串行、Playwright workers=2。

## 本机准备状态

全部本机准备门禁通过，证据绑定上述冻结 HEAD，命令、实际运行时间和退出状态见 `commands.json`：

| 范围 | 实际执行 | 结果 / 原始证据 |
| --- | --- | --- |
| 单测 | `npm test` | 76 文件、558 项 PASS，`unit.log` |
| 契约生成一致性 | `npm run check:api-types` | PASS，`api-types.log` |
| 类型与构建 | `npm run build` | PASS，`build.log` |
| 产物预算 | `npm run check:bundle` | PASS，最大 JS 400.0 KiB，`bundle.log` |
| 最终镜像 | `docker build --platform linux/amd64 --label org.opencontainers.image.revision=db4c27a7a30e085dd6454ab028d18fcfdd584521 --tag iterflow-web:close-confirm-1114 .` | PASS，`image-build.log` |
| 镜像静态文件 | `python3 verify-image.py` | 141 文件 HTTP/hash 全部 PASS，镜像文件与本机冻结 dist 逐字节一致，Nginx 配置一致、非 root uid 101；`image-http.log`、`final-image-http.json` |
| 浏览器 | `ITERFLOW_WEB_URL=http://127.0.0.1:32768 npm run smoke:browser -- create-close-protection feedback-no-module rich-text --workers=2 --output=…/browser-artifacts --reporter=line` | 31 项 PASS，`browser.log` 与 `browser-artifacts/` |
| 离线镜像身份 | `python3 save-image.py`、`python3 build-image-proof.py` | PASS；核对归档每个 blob、解压层 diff ID、amd64 manifest/config 及 OCI/classic 身份，`image-save.log`、`image-proof.log` |
| 控制器 | `python3 test_controller.py` | 原 16 项加本轮 4 项，共 20 项 PASS，`controller-tests.log` |

浏览器直接访问最终待部署镜像提供的静态文件，业务 API 使用内存合成响应；覆盖桌面/375px 空表单、编辑草稿、连续 Esc、叉号/取消、继续编辑、明确放弃、再次打开、提交中/失败、待上传附件与既有反馈无模块/富文本回归。截图等待按钮可交互后取得，本机复查了 375px 新建需求和 1440px 提交反馈的确认框，无裁切或横向溢出。上述结果不代表真实后端主链或数据库验收；本轮未执行完整八项 CI、真实数据库/后端、S3 或备份恢复测试，前后端契约和后端产品均未改变。

控制器新增保护覆盖混合来源基线、Web/API 来源互换或漂移、旧 Web 镜像 ID 漂移以及 `BUILD_SHA` 必须保持 API 来源，原有正式保护没有放宽。控制器相对旧脚本的差异见 `controller-adaptation.diff`，协调者已作范围复核；本机测试、产物与截图检查为本代理自审，不能称为完整独立审查。

本机唯一临时容器 `iterflow-close-confirm-1114-static` 已定点清理。原有五个预览容器的 ID、镜像、启动时间与重启次数前后一致，证据为 `protected-local-containers-before.json`、`protected-local-containers-after.json`、`cleanup-result.json`；最终镜像与冻结源码保留。

首次源码提取因本机 Python 的 `tarfile.extractall` 不支持 `filter` 参数停止，未发生源码改动；改为验证所有归档条目无绝对路径、穿越或链接后提取本次可信 Git 归档。失败说明保留于 `freeze-initial-failure.txt`。

## 最终上传包

- 本机文件：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-14/close-confirmation-test/iterflow-close-confirm-1114.tar`，23,203,840 字节。
- 包 SHA256：`74b3d216c011c3c1b7c79bf04323416299dc3151bf9bc55e4306561c0f272b02`；manifest SHA256：`afbf89d809ff239c2b965b6debc7d505a3fcd088e8c706f6370b4b760529bb1d`。
- 包只含 `deploy-web.py`、`manifest.json`、`image-identity-proof.json` 和 `web-image.tar.gz`，已重新打开外层 tar，逐文件核对与冻结 package 一致。
- linux/amd64 镜像：`iterflow-web:close-confirm-1114`；OCI index 为 `sha256:cac7c502648df242142ca98d4f737a122a725a452c66a35b4f86edabe5e6d65f`，classic config 为 `sha256:0c8e1ff719925773610ea9aad684df309efee5239d850ce96654f50a80431fc3`。服务器载入可能显示后一 ID，控制器同时允许已证明的这两个身份，仍逐一检查架构、revision 和全部 RootFS diff ID。
- 新首页 SHA256：`27dd35834d65c73e3ba095e026f4e27125a0b53fd0ec34f349f7d0387c06591b`。本机汇总为 `local-preparation-result.json`。

上传 owner 在宝塔正常文件管理中上传到 `/opt/iterflow/upgrade-evidence/close-confirm-1114`；单独执行 `sha256sum iterflow-close-confirm-1114.tar` 并比对上述值，再解包。该目录是本次控制器固定 evidence 根目录，不能复用旧目录覆盖收据。执行时须使用控制器绝对路径 `/opt/iterflow/upgrade-evidence/close-confirm-1114/deploy-web.py`，依次调用 `preflight`、`prepare`、`deploy`、`verify`；每阶段读取对应输出及实际收据后才能继续。相对路径调用的首次失败与修正见下文，不复用该调用方式。

## 服务器执行边界

复用旧 `deploy-web.py` 的 preflight / prepare / deploy / verify 分阶段保护：服务器身份、保留环境控制状态、残留构建/部署、Compose 解析、旧 Web 镜像和来源、TEST 非 Web 与正式容器及配置、静态首页指纹均须符合。只修改 TEST `WEB_IMAGE`，使用原 Compose 对 Web 执行 `--no-deps --no-build --pull never`，健康后 reload TEST 代理。

回退只恢复本轮备份的 `iterflow-web:ui-workspace-1112` 与 `images.env.before`，要求旧镜像 ID、`preserved.json` 和配置无外部漂移；不恢复数据库，不停止或重建 TEST 后端。控制器的 `rollback()` 是失败路径内部函数，不存在公开 `rollback` CLI；人工续作须使用受独占锁保护、加载本轮 manifest 的路径。保护失败保留现场，不放宽正式保护。

## 服务器执行与首次失败

服务器重新核对为 `iZ2zehrcw9x4jxbjd1mfqaZ`，上传目录 root:root / 0700。通过宝塔正常文件上传完成，服务器包 SHA256 与上述冻结产物一致；未使用网页终端传文件或脚本数据。

| 阶段 | UTC 时间 | 实际结果 |
| --- | --- | --- |
| preflight | 2026-11-14 02:55:07 | PASS；TEST/正式入口均 HTTP 200，旧 Web/API 分别匹配来源，保护基线已建立 |
| 首次 prepare | 2026-11-14 02:55:37 | STOPPED；相对路径命令被残留进程检查识别为自身，停止在备份、镜像载入和切换之前 |
| prepare 修正重试 | 2026-11-14 02:57:00 | PASS；改为绝对路径调用原脚本，未改 manifest、脚本或放宽保护 |
| deploy | 2026-11-14 02:58:04—02:58:22 | PASS；只替换 TEST Web，记录的切换阶段为 18 秒，不等于精确请求中断时长 |
| 首次 verify | 2026-11-14 02:58:49 | PASS；新 Web 来源与镜像一致，正式及 TEST 非 Web 保护一致，未执行数据库命令 |

首次失败保留为服务器 `failure-prepare-20261114T025537Z-241369.txt`。协调者检查残留过滤逻辑后确认根因为相对路径未命中自身排除条件；重试前确认无残留命令及 prepared/switch 标志。重试使用 `python3 /opt/iterflow/upgrade-evidence/close-confirm-1114/deploy-web.py prepare > prepare-retry-output.log`，没有绕过门禁。

旧 Web 备份 `old-web-image.tar` 的 SHA256 为 `3202f95a81c433c074f7b6f46134a7c9e096dfae0024fc9fef121fbe88d0f6ef`，旧镜像 ID 为 `sha256:105f5f62959d18bd22a6d990fbe2121fd70b60091f6461ebc9c532787b271a9d`；配置备份及保留状态在服务器固定证据目录。因本轮仅替换 Web，没有数据库备份恢复、迁移或结构查询；不将容器/配置指纹不变描述为数据库全量数据比对。

准备阶段的本机收据 `ui-operator-preparation-receipt.json` 是从 Safari 可见输出转录的摘要，并非下载的服务器原始文件；其中 `deploy_executed=false` 是准备完成时的快照，不代表后续部署结果。


## 线上验收与最终结果

TEST `https://sx-kc.xyz:8444` 桌面 Safari 的新增反馈、需求均通过以下实际操作：空表单 Esc 需要确认、连续 Esc 不绕过；输入标题及描述后退出提示未保存，选择继续编辑保留输入；叉号、取消使用同样保护；明确放弃后重开表单为空。需求描述使用实际富文本控件。验收未点击提交/创建、未上传附件或保存业务数据；反馈列表前后均 23 条，需求列表前后均 38 条，所有临时输入已明确放弃，无打开草稿。

验收后最终 `verify` 于 **2026-11-14T03:02:36Z（北京时间 11:02:36）PASS**：Web 镜像 ID / revision、运行配置、健康及 TEST 首页指纹匹配；`production_unchanged=true`、`test_non_web_unchanged=true`、`database_commands=false`。保护检查包含正式及 TEST 非 Web 的容器身份、启动时间、挂载、环境指纹、重启策略、受保护配置和软链接，正式入口指纹一致。无数据库命令、迁移、seed、GRANT、恢复或回退；正式环境未变。

最终本机摘要为 `ui-operator-deployment-result.json`，逐项 UI 结果为 `online-close-confirmation-checks.json`；两者明确标为可见 UI/终端输出的人工转录，非服务器原始收据下载。服务器原始收据及日志保留于本轮固定目录。

在线验收仅桌面；375px、提交中禁止关闭、失败后草稿和附件保留由前述本机 Mock 浏览器测试覆盖，未在真实 TEST 重放，不声称完整后端主链或八项 CI 已运行。未在线上传附件或检查浏览器控制台，无全量数据库数据/结构比对。

执行分工：`close_test_package` 与 `close_test_ui` 均按工具实际配置使用 `gpt-6.1-sol / xhigh`；前者负责冻结、测试、打包，后者独占 Safari 完成上传、分阶段服务器操作及真实页面验收，协调者核对差异、产物/控制器保护与结果并集成记录。协调者复核不等于重跑全部测试或完整独立产品代码审查。

状态：**完成 TEST 部署与本轮验收，等待用户体验反馈**。Safari 保留 TEST 需求列表，宝塔终端空闲；浏览器 owner 已交还，完成摘要已发送。未推送、合并、tag/Release；用户原有文档清理保持未暂存且未覆盖。
