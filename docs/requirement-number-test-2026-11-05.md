# 需求编号展示与复制：TEST 部署记录

2026-11-05 用户明确授权部署本次需求编号展示与复制到保留 TEST，正式环境不动。

## 产物与范围

- 冻结源码：`ed797d69c47dae7b3a1f1b284fece506806d1287`。
- TEST：`https://sx-kc.xyz:8444`，仅 Web 更新为 `iterflow-web:req-number-ed797d6`。
- Web classic image ID：`sha256:79a8863ecf8341b4a99a39e52ab08ad97d145c742c20d82d6fd7355e9a052074`。
- API/worker 仍为 `ab8bd07c75ed85fcf7b554fa477b7b876ed72da2`，TEST 数据库仍为 `mysql57_0012`，未执行数据库命令、迁移或恢复。
- 正式源码仍为 `96ba96ef81f96a533e9bc912100651d368a6945f`，正式容器、配置保护基线一致；未推送、合并或创建 Release/tag。

## 执行与验证

1. 前端类型检查与生产构建 PASS；此前本次实现的摘要组件 7 项测试及本地浏览器复制/降级测试 PASS。
2. 复用 Web-only 控制器，更新冻结源、旧 Web/API 和首页哈希；16 项离线安全测试 PASS。linux/amd64 镜像中 153 个静态文件按运行用户读取并校验，OCI/config/layer 身份证据 PASS。
3. 通过宝塔文件管理正常上传归档，未通过网页终端传输脚本或 Base64。上传包 SHA-256：`45ed7c8fe71091dcfcd254f6eef8e9bbd59f2b1680094bfb20e28593333a7b3a`。一次终端连接尚未就绪时未执行命令，文件管理确认只有归档后重新连接并检查正常回显，再执行带防重复条件的解包与预检。
4. 服务器 `preflight.json`、`prepared.json`、`deployed.json`、`verified.json` 成功凭据均已在文件管理中观察到。各阶段检查正式基线和 TEST 非 Web 容器/配置、健康状态及 HTTPS 页面；仅更换 TEST Web 并重载 TEST 代理，旧镜像与配置已备份，未触发回退。
5. 外部 HTTPS 首页实际 SHA-256：`567e303832c87686202780a0aa22abab8334f4dcfa7cd0a36315f6ceae5d3a30`，与冻结包一致。
6. 使用既有合成账号验收；浏览器请求仅允许 TEST 同源读取和一次登录，业务写入为 0。四组在线验证 PASS：桌面详情精确复制编号、375px 详情展示/复制/无横向溢出、版本需求摘要精确复制编号、375px 摘要在剪贴板拒绝时选中准确编号并提示手动复制。

服务器证据目录：`/opt/iterflow/upgrade-evidence/req-number-ed797d6`。
本地证据目录：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-05/requirement-number`，含 manifest、镜像身份证据、控制器、测试日志、在线结果及桌面/手机截图。

## 回退与验收

如需回退，先核对上述保护基线及当前 Web 标签、镜像与 `images.env`，再按控制器中 `rollback()` 的保护步骤仅恢复原 Web `iterflow-web:req-images-ab8bd07-r2` 与备份 `images.env`，重载 TEST 代理并核验旧首页。不要执行数据库恢复。旧 Web 保留上一轮需求图片支持；控制器 CLI 不直接暴露 rollback 子命令，人工回退须按已记录函数步骤复核后执行。

用户可在需求详情标题上方、版本内的需求摘要中查看“需求编号”并点击“复制编号”，将编号直接用于提交记录。本轮无未解决阻断项或规格冲突。
