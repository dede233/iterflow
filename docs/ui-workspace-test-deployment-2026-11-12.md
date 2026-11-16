# UI 阅读与工作台 TEST 验收部署（2026-11-12）

用户授权补齐本轮 UI 测试，通过后部署保留 TEST，正式环境不动。开发范围及历史验证见 `ui-workspace-refinement-2026-11-11.md`。本轮不推送、合并或创建 tag / Release。

## 范围与执行顺序

相对已验收 TEST `af3445d`，后端、契约、部署模板和工具没有产品变更。本次只更新 TEST Web；API/worker 保留 `af3445d`，数据库沿用既有 `mysql57_0016`，不执行数据库命令、迁移、seed、GRANT 或恢复。正式镜像以本轮只读核对的 `d6cfb815d7e1` 为保护基线，不连接正式数据库。

1. 补齐此前 12 文件 140 项 E2E：136 项合成接口用例与 4 项独立临时后端主链，保留失败和修复证据；补充异步/未保存保护边界测试并复查前端门禁。
2. 冻结最终源码构建 linux/amd64 Web 镜像，核对静态产物、类型、构建与预算，以及部署控制器保护测试。
3. 通过宝塔正常上传离线包；只用短命令执行分阶段控制器。核对服务器身份/残留任务/两环境健康、配置与容器基线，备份旧 Web 镜像和 TEST 配置。
4. 仅替换 TEST Web，健康后恢复 TEST 代理；失败只进行受保护的 Web 回退，不触及数据库。
5. 使用现有合成记录验收桌面及手机工作台、列表筛选、需求阅读/编辑保护、品牌矩阵与版本覆盖；核对正式及 TEST 非 Web 容器/配置不变，保留新 Web 供用户验收。

证据目录：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-12/ui-workspace-test-deployment/`。

## 当前记录

开始时工作树干净，HEAD 为 `4231cc9`，UI 产品源码为 `8633cb3`。Safari 宝塔终端可用；只读容器核对 TEST API/worker/Web 为 `grouped-mini-test-af3445d`、正式为 `mysql57-d6cfb815d7e1`，均运行且带健康检查的应用健康。尚未切换，最终执行结果待追加。


## 用户暂停（2026-11-12）

用户要求当前子代理完成后暂停。已停止后续修复和部署：

- 当前 136 项合成 E2E 批次实际执行：115 PASS、21 FAIL、0 跳过。失败中含旧定位器不匹配、焦点断言以及页面加载/导航超时；完整归因和修复尚未执行，不视为门禁通过。
- 真实隔离后端的 4 项 `release.spec.ts` 尚未启动。仅本任务新建临时数据库执行了初始化；临时容器、卷及独立静态预览已清理，原有本机预览服务保留。
- 独立审查新增 5 条单测，相关 35 项 PASS。仅修改两份测试文件；手机全屏宽度与长筛选标签的两项 CSS 风险待实际复现，未改产品。
- 尚未冻结或上传本轮部署包，未切换 TEST，未修改正式环境。后续恢复应从 21 项失败归因、4 项真实主链与两项 UI 风险复现继续；通过后再冻结并部署。

批次证据：`changed-e2e-case-results.json`、`changed-e2e-first.json`、`paused-e2e-result.json` 及失败 trace；审查证据：`independent-ui-review.md`、`independent-ui-review-tests.log`，均位于本轮交付目录。

## 恢复执行与测试

用户恢复并授权修复、补跑和 TEST 部署。修复新建/编辑需求校验误聚焦隐藏图片 input；测试使用准确的标题文本框，避免富文本工具栏和必填星号干扰。手机全屏排除普通弹窗宽度规则，长筛选标签换行并扩大关闭触控区。

- 原 136 项合成浏览器测试在独立 Nginx 静态服务全部 PASS。
- 4 项真实后端测试在全新隔离 PostgreSQL/Redis/API/Web 全部 PASS，未连接保留数据库。
- 新增全屏编辑与长关键词手机布局 4 项 PASS。
- 76 文件、557 单测、类型/构建/契约/预算 PASS。

真实主链首轮 3 通过、1 项旧标题定位失败，修正后全新临时栈 4 项通过；中间单项续跑在已有合成数据栈遇到人员选项超时，保留证据，不宣称该超时已作产品修复。原偶发页面加载/导航超时在独立 Nginx 服务未重现，没有修改认证或导航规则。布局初轮在 Tag 进场动画尺寸为 0 时读取失败，改为等待实际尺寸稳定后通过。

最终日志：`resume-e2e.log`、`real-four-final.log`、`layout-regression-final.log`、`unit-resume.log`；失败日志保留。产品冻结为 `8b481bf`，部署阶段待完成。

## 最终部署结果

2026-11-12 已部署保留 TEST，等待用户验收。仅 Web 更新到 `8b481bf2aa59504202a196242646e0105c7eb955`；API/worker 仍为 `af3445d`，数据库沿用 `mysql57_0016`。正式 `d6cfb815d7e1` 未变。

- 产物：`iterflow-web:ui-workspace-1112`，linux/amd64；服务器镜像 ID `sha256:105f5f62959d18bd22a6d990fbe2121fd70b60091f6461ebc9c532787b271a9d`。
- 上传包 `iterflow-ui-workspace-1112.tar`，23,214,080 字节，SHA256 `0259b03db56b72e8b46e353c31feb41076712749fdaf5b4ef46fbd388ce86ba2`；服务器上传后校验一致。
- 最终镜像 Nginx 配置、非 root 用户、141 个静态文件逐一 HTTP/hash 校验及 4 项布局回归 PASS；控制器 16 项保护测试 PASS。
- `preflight / prepare / deploy / verify` 均 PASS；旧 Web 镜像及 TEST 配置备份完成。切换记录窗口为北京时间 **11:06:53–11:07:09（16 秒）**，不代表精确请求中断时长；未执行回退。
- 在线验收后的最终 verify 为 **11:10:38**，TEST 非 Web 容器身份/启动时间/环境配置及正式容器、配置、入口指纹不变。无数据库命令、迁移、权限变更或恢复；未替换数据卷或附件，未修改 SMTP。没有执行数据库全行比对，不将容器保护检查冒称全量数据校验。
- 无推送、合并、tag/Release 或远端八项 CI 执行。本次是本地测试及 TEST 部署，不是正式上线准备。

服务器收据与受保护备份位于 `/opt/iterflow/upgrade-evidence/ui-workspace-1112/`：`preflight.json`、`prepared.json`、`switch-started.json`、`deployed.json`、`verified.json`、`preserved.json`、`web-before.json`、`old-web-image.tar` 与 `*.before`。本机 `deployment-result.json` 是根据终端可见收据整理的结果摘要，不是下载的服务器原件。

## 在线 UI 验收

沿用 TEST 已登录系统管理员和既有合成数据，未创建或保存业务记录：

1. 工作台三组本人待办与既有统计正常；当前账号三组为空，非空和异步边界由隔离测试覆盖。
2. 版本 31 显示同品牌微信/支付宝发布覆盖、原有两批登记与各自时间；清单筛选展开、重置和收起正常。打开需求 38 摘要，编号、业务系统、正文与原有操作记录正常。
3. 发布补记输入草稿后取消会确认，继续编辑和放弃可用；没有保存补记或改变上线时间。
4. 375px 新建需求缺少描述时焦点准确进入可编辑描述；全屏弹窗为 `(0,0,375,812)`，收起后文字保留，关闭时提示放弃。验收草稿已放弃，需求总数仍为 38。
5. 品牌目录桌面矩阵与手机卡片正常，AppID 搜索命中双平台品牌；编辑草稿的关闭确认生效，原品牌名称未变。
6. 手机长关键词标签换行，页面宽度为 375px 无横向溢出，关闭按钮 44×44px，Enter 可移除条件。版本、品牌和编辑页面截图已保存；浏览器错误/警告日志为空，临时视口已复原。

在线自动操作在品牌子弹窗退场动画期间立即点击父弹窗关闭时再次触发未保存确认；已放弃并关闭，无业务提交。后续操作等待弹窗隐藏，避免把退场中的节点当作已卸载。此边界作为已知轻微交互限制保留，不影响正常保存或数据安全。

截图：`test-desktop-dashboard.png`、`test-version-desktop.png`、`test-version-mobile.png`、`test-editor-mobile.png`、`test-brand-desktop.png`、`test-brand-mobile.png`、`test-long-filter-mobile.png`。临时隔离栈、卷和最终镜像验证容器已定点清理，原本机预览服务保留。

## 执行异常与回退边界

- 最终镜像单独启动时因缺少 Compose 的 `api` 主机名而退出；测试启动参数增加指向本容器的临时 hosts 解析，仅用于静态文件及合成 API 浏览器验证，镜像及服务器配置未修改。配置/HTTP/布局复验通过，初次日志保留。
- 宝塔 `typeText` 丢失重定向符号，首次预检命令在参数断言处退出，未进入部署；改用短命令粘贴后预检通过，截图 `terminal-typing-failure.png` 保留。无长脚本/Base64 终端传输。
- 回退只允许恢复本次备份的旧 Web `iterflow-web:grouped-mini-test-af3445d` 和 `images.env.before`，先核对 `preserved.json`、镜像 ID、配置无其他操作漂移，再按控制器现有 `rollback()` 保护顺序执行。该函数不是公开 CLI 子命令，人工续作需受独占锁保护并加载原 manifest；不要直接输入不存在的 `deploy-web.py rollback`。
- 回退仅使用原 Compose 项目对 Web 执行 `--no-deps --no-build --pull never`，健康后 reload TEST 代理，并重查 TEST 旧首页和正式保护。禁止恢复数据库、停止 TEST 后端或覆盖其他人的新配置；保护失败时保留现场排查。
